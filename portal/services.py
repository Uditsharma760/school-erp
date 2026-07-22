import hashlib
import hmac
import io
import json
import secrets
from decimal import Decimal

import qrcode
import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import (
    AuditLog,
    CommunicationLog,
    FeePayment,
    Mark,
    ParentStudentAccess,
    PaymentOrder,
    PayrollRecord,
    SchoolProfile,
    Section,
    Student,
    TeacherAssignment,
    User,
)


def assigned_sections(user):
    if user.is_superuser or user.is_management:
        return Section.objects.all()
    if user.role != User.Role.TEACHER:
        return Section.objects.none()
    return Section.objects.filter(Q(class_teacher=user) | Q(teacher_assignments__teacher=user)).distinct()


def can_access_section(user, section, subject=None):
    if user.is_superuser or user.is_management:
        return True
    if user.role != User.Role.TEACHER:
        return False
    if section.class_teacher_id == user.id:
        return True
    qs = TeacherAssignment.objects.filter(teacher=user, section=section)
    if subject is not None:
        qs = qs.filter(subject=subject)
    return qs.exists()


def accessible_students(user):
    qs = Student.objects.select_related("section__school_class", "session")
    if user.is_superuser or user.is_management:
        return qs
    if user.role == User.Role.TEACHER:
        return qs.filter(section__in=assigned_sections(user))
    if user.role == User.Role.STUDENT:
        return qs.filter(portal_user=user)
    if user.role == User.Role.PARENT:
        return qs.filter(parent_links__parent=user).distinct()
    if user.role in {User.Role.ACCOUNTANT, User.Role.TRANSPORT}:
        return qs.filter(status=Student.Status.ACTIVE)
    return qs.none()


def can_access_student(user, student):
    if user.is_superuser or user.is_management:
        return True
    if user.role == User.Role.TEACHER:
        return can_access_section(user, student.section)
    if user.role == User.Role.STUDENT:
        return student.portal_user_id == user.id
    if user.role == User.Role.PARENT:
        return ParentStudentAccess.objects.filter(parent=user, student=student).exists()
    if user.role in {User.Role.ACCOUNTANT, User.Role.TRANSPORT}:
        return True
    return False


def generate_username(first_name, last_name, prefix=""):
    parts = f"{prefix}{first_name}.{last_name}" if last_name else f"{prefix}{first_name}"
    base = "".join(ch for ch in parts.lower() if ch.isalnum() or ch == ".").strip(".") or "user"
    username = base[:130]
    counter = 1
    while User.objects.filter(username=username).exists():
        counter += 1
        suffix = str(counter)
        username = f"{base[:150-len(suffix)]}{suffix}"
    return username


def generate_password():
    # URL-safe and sufficiently long; users must change it at first sign-in.
    return secrets.token_urlsafe(10)


def prepare_math_captcha(request):
    a, b = secrets.randbelow(8) + 1, secrets.randbelow(8) + 1
    request.session["captcha_answer"] = a + b
    return f"{a} + {b} = ?"


def validate_captcha(request):
    if settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY:
        token = request.POST.get("cf-turnstile-response", "")
        if not token:
            return False, "Please complete the CAPTCHA."
        try:
            response = requests.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": settings.TURNSTILE_SECRET_KEY,
                    "response": token,
                    "remoteip": request.META.get("REMOTE_ADDR", ""),
                },
                timeout=8,
            )
            data = response.json() if response.content else {}
            if response.ok and data.get("success"):
                allowed_hostname = getattr(settings, "TURNSTILE_EXPECTED_HOSTNAME", "")
                if not allowed_hostname or data.get("hostname") == allowed_hostname:
                    return True, ""
        except (requests.RequestException, ValueError):
            pass
        return False, "CAPTCHA verification failed. Please try again."

    expected = request.session.pop("captcha_answer", None)
    try:
        supplied = int(request.POST.get("captcha_answer", ""))
    except (TypeError, ValueError):
        supplied = None
    return supplied == expected, "" if supplied == expected else "Incorrect CAPTCHA answer."


def audit(request, action, obj=None, description=""):
    try:
        AuditLog.objects.create(
            actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            action=action,
            model_name=obj.__class__.__name__ if obj is not None else "",
            object_id=str(obj.pk) if obj is not None and getattr(obj, "pk", None) else "",
            description=description,
            ip_address=(request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")),
        )
    except Exception:
        # Auditing must not break the main ERP action.
        pass


def calculate_result(student, exam):
    marks = Mark.objects.filter(student=student, exam=exam).select_related("subject").order_by("subject__name")
    total = sum((m.obtained_marks for m in marks), Decimal("0"))
    maximum = sum((m.max_marks for m in marks), Decimal("0"))
    percentage = round(float(total / maximum * 100), 2) if maximum else 0
    grade = (
        "A+" if percentage >= 90 else "A" if percentage >= 80 else "B+" if percentage >= 70 else
        "B" if percentage >= 60 else "C" if percentage >= 50 else "D" if percentage >= 33 else "F"
    )
    passed = bool(marks) and all(m.grade != "F" for m in marks)
    return {"marks": marks, "total": total, "maximum": maximum, "percentage": percentage, "grade": grade, "passed": passed}


def result_pdf_bytes(student, exam):
    school = SchoolProfile.objects.first()
    data = calculate_result(student, exam)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    centered = ParagraphStyle("centered", parent=styles["Heading1"], alignment=TA_CENTER, spaceAfter=6)
    story = [
        Paragraph((school.school_name if school else "School ERP"), centered),
        Paragraph((school.address if school else "") or "", ParagraphStyle("address", parent=styles["Normal"], alignment=TA_CENTER)),
        Spacer(1, 8),
        Paragraph(f"<b>{exam.name} Result</b> — Session {exam.session.name}", ParagraphStyle("exam", parent=styles["Heading2"], alignment=TA_CENTER)),
        Spacer(1, 12),
    ]
    info = [
        ["Student", student.full_name, "Admission No.", student.admission_no],
        ["Class / Section", str(student.section), "Roll No.", student.roll_number or "—"],
        ["Date of Birth", student.date_of_birth.strftime("%d-%m-%Y"), "Attendance", f"{student.attendance_percentage}%"],
    ]
    info_table = Table(info, colWidths=[32 * mm, 55 * mm, 32 * mm, 45 * mm])
    info_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef2ff")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [info_table, Spacer(1, 14)]
    rows = [["Subject", "Maximum", "Obtained", "Grade", "Remarks"]]
    for mark in data["marks"]:
        rows.append([mark.subject.name, str(mark.max_marks), str(mark.obtained_marks), mark.grade, mark.remarks or "—"])
    rows.append(["TOTAL", str(data["maximum"]), str(data["total"]), data["grade"], "PASS" if data["passed"] else "FAIL"])
    table = Table(rows, repeatRows=1, colWidths=[55 * mm, 27 * mm, 30 * mm, 22 * mm, 35 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0e7ff")),
        ("ALIGN", (1, 1), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [
        table,
        Spacer(1, 12),
        Paragraph(f"Percentage: <b>{data['percentage']}%</b> &nbsp;&nbsp; Overall Grade: <b>{data['grade']}</b>", styles["Normal"]),
        Spacer(1, 28),
        Paragraph("Class Teacher Signature ____________________ &nbsp;&nbsp;&nbsp;&nbsp; Principal Signature ____________________", styles["Normal"]),
    ]
    doc.build(story)
    return buffer.getvalue()


def id_card_pdf_bytes(student, request=None):
    school = SchoolProfile.objects.first()
    buffer = io.BytesIO()
    page = landscape((86 * mm, 54 * mm))
    doc = SimpleDocTemplate(buffer, pagesize=page, rightMargin=4 * mm, leftMargin=4 * mm, topMargin=3 * mm, bottomMargin=3 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Heading2"], alignment=TA_CENTER, textColor=colors.HexColor("#1d4ed8"), fontSize=12, leading=13)
    story = [
        Paragraph((school.school_name if school else "School ERP"), title),
        Paragraph("STUDENT IDENTITY CARD", ParagraphStyle("sub", parent=styles["Normal"], alignment=TA_CENTER, fontSize=7)),
        Spacer(1, 2),
    ]

    photo = None
    if student.photo:
        try:
            # Read through Django storage so local files and S3-compatible media both work.
            student.photo.open("rb")
            photo_bytes = io.BytesIO(student.photo.read())
            student.photo.close()
            photo = Image(photo_bytes, width=19 * mm, height=24 * mm)
        except (OSError, ValueError, NotImplementedError):
            photo = None
    if photo is None:
        photo = Table([["PHOTO"]], colWidths=[19 * mm], rowHeights=[24 * mm], style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

    verify_url = ""
    if request:
        try:
            verify_url = request.build_absolute_uri(f"/verify/student/{student.admission_no}/")
        except Exception:
            verify_url = ""
    verify_text = verify_url or f"Student: {student.admission_no}\n{student.full_name}\nClass: {student.section}"
    qr = qrcode.make(verify_text)
    qr_buf = io.BytesIO()
    qr.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_img = Image(qr_buf, width=16 * mm, height=16 * mm)
    details = Paragraph(
        f"<b>{student.full_name}</b><br/>Admission: {student.admission_no}<br/>Class: {student.section}<br/>Roll: {student.roll_number or '—'}<br/>DOB: {student.date_of_birth.strftime('%d-%m-%Y')}<br/>Guardian: {student.guardian_phone}",
        ParagraphStyle("details", parent=styles["Normal"], fontSize=7.2, leading=9),
    )
    content = Table([[photo, details, qr_img]], colWidths=[21 * mm, 42 * mm, 17 * mm], rowHeights=[27 * mm])
    content.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
    ]))
    story += [content, Paragraph((school.address if school else "") or "", ParagraphStyle("footer", parent=styles["Normal"], alignment=TA_CENTER, fontSize=5.5))]
    doc.build(story)
    return buffer.getvalue()


def payslip_pdf_bytes(payroll):
    school = SchoolProfile.objects.first()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(school.school_name if school else "School ERP", ParagraphStyle("heading", parent=styles["Heading1"], alignment=TA_CENTER)),
        Paragraph((school.address if school else "") or "", ParagraphStyle("addr", parent=styles["Normal"], alignment=TA_CENTER)),
        Spacer(1, 12),
        Paragraph(f"SALARY SLIP — {payroll.month:%B %Y}", ParagraphStyle("month", parent=styles["Heading2"], alignment=TA_CENTER)),
        Spacer(1, 14),
    ]
    employee = payroll.staff.get_full_name() or payroll.staff.username
    info = [["Employee", employee, "Role", payroll.staff.get_role_display()], ["Employee ID", payroll.staff.username, "Status", payroll.get_status_display()]]
    t = Table(info, colWidths=[35 * mm, 55 * mm, 35 * mm, 45 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef2ff")), ("PADDING", (0, 0), (-1, -1), 7)]))
    story += [t, Spacer(1, 16)]
    earnings = [["Earnings", "Amount"], ["Basic", f"₹ {payroll.basic:.2f}"], ["HRA", f"₹ {payroll.hra:.2f}"], ["Other allowances", f"₹ {payroll.allowances:.2f}"], ["Gross", f"₹ {payroll.gross:.2f}"]]
    deductions = [["Deductions", "Amount"], ["Total deductions", f"₹ {payroll.deductions:.2f}"], ["Net salary", f"₹ {payroll.net:.2f}"]]
    et = Table(earnings, colWidths=[70 * mm, 45 * mm])
    dt = Table(deductions, colWidths=[70 * mm, 45 * mm])
    for table in (et, dt):
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ALIGN", (1, 1), (1, -1), "RIGHT"), ("PADDING", (0, 0), (-1, -1), 8)]))
    story += [Table([[et, dt]], colWidths=[85 * mm, 85 * mm]), Spacer(1, 18)]
    story.append(Paragraph(f"Payment reference: {payroll.payment_reference or '—'} &nbsp;&nbsp; Paid date: {payroll.paid_date.strftime('%d-%m-%Y') if payroll.paid_date else '—'}", styles["Normal"]))
    story += [Spacer(1, 35), Paragraph("Authorised Signatory ______________________________", ParagraphStyle("sign", parent=styles["Normal"], alignment=TA_RIGHT))]
    doc.build(story)
    return buffer.getvalue()


def payment_gateway_configured():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def create_razorpay_order(student, amount, created_by=None):
    if not payment_gateway_configured():
        raise ValueError("Razorpay keys are not configured.")
    amount = Decimal(amount).quantize(Decimal("0.01"))
    receipt_no = f"ONL-{timezone.now():%Y%m%d%H%M%S}-{secrets.randbelow(9000)+1000}"
    payload = {
        "amount": int(amount * 100),
        "currency": "INR",
        "receipt": receipt_no,
        "notes": {"student_id": str(student.pk), "admission_no": student.admission_no},
    }
    response = requests.post(
        "https://api.razorpay.com/v1/orders",
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return PaymentOrder.objects.create(
        student=student,
        amount=amount,
        gateway_order_id=data["id"],
        receipt_no=receipt_no,
        status=PaymentOrder.Status.CREATED,
        raw_payload=data,
        created_by=created_by,
    )


def verify_razorpay_payment_signature(order_id, payment_id, signature):
    message = f"{order_id}|{payment_id}".encode()
    digest = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def verify_razorpay_webhook_signature(raw_body, signature):
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    digest = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature or "")


@transaction.atomic
def finalize_payment(order, payment_id, signature="", raw_payload=None):
    order = PaymentOrder.objects.select_for_update().get(pk=order.pk)
    if order.status == PaymentOrder.Status.PAID:
        return order, FeePayment.objects.filter(gateway_payment_id=order.gateway_payment_id).first()
    payment, _ = FeePayment.objects.get_or_create(
        gateway_payment_id=payment_id,
        defaults={
            "student": order.student,
            "amount": order.amount,
            "payment_date": timezone.localdate(),
            "mode": FeePayment.Mode.ONLINE,
            "receipt_no": order.receipt_no,
            "reference_no": payment_id,
            "notes": "Verified online fee payment",
            "received_by": order.created_by if order.created_by and order.created_by.is_school_staff else None,
        },
    )
    order.gateway_payment_id = payment_id
    order.gateway_signature = signature
    order.status = PaymentOrder.Status.PAID
    if raw_payload:
        order.raw_payload = raw_payload
    order.save(update_fields=["gateway_payment_id", "gateway_signature", "status", "raw_payload", "updated_at"])
    return order, payment


def normalize_india_phone(phone):
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    return digits


def _send_msg91_sms(phone, message):
    if not (settings.MSG91_AUTH_KEY and settings.MSG91_TEMPLATE_ID):
        return "DEMO", {}, ""
    variable_name = settings.MSG91_MESSAGE_VARIABLE or "MESSAGE"
    payload = {
        "template_id": settings.MSG91_TEMPLATE_ID,
        "short_url": "0",
        "recipients": [{"mobiles": normalize_india_phone(phone), variable_name: message}],
    }
    response = requests.post(
        settings.MSG91_FLOW_URL,
        headers={"authkey": settings.MSG91_AUTH_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    data = response.json() if response.content else {}
    if not response.ok:
        return "FAILED", data, f"MSG91 HTTP {response.status_code}"
    return "SENT", data, ""


def _send_whatsapp_template(phone, message, template_name=""):
    required = settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID and (template_name or settings.WHATSAPP_TEMPLATE_NAME)
    if not required:
        return "DEMO", {}, ""
    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_india_phone(phone),
        "type": "template",
        "template": {
            "name": template_name or settings.WHATSAPP_TEMPLATE_NAME,
            "language": {"code": settings.WHATSAPP_TEMPLATE_LANGUAGE},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": message[:1000]}]}],
        },
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    data = response.json() if response.content else {}
    if not response.ok:
        return "FAILED", data, f"WhatsApp HTTP {response.status_code}"
    return "SENT", data, ""


def send_communication(channel, recipient_name, phone, message, sent_by=None, audience="", template_name=""):
    log = CommunicationLog.objects.create(
        channel=channel,
        audience=audience,
        recipient_name=recipient_name,
        recipient_phone=normalize_india_phone(phone),
        template_name=template_name,
        body=message,
        sent_by=sent_by,
    )
    try:
        if channel == CommunicationLog.Channel.SMS:
            status, data, error = _send_msg91_sms(phone, message)
        else:
            status, data, error = _send_whatsapp_template(phone, message, template_name)
        log.status = status
        log.provider_response = data
        log.error = error
        if data:
            log.provider_message_id = str(data.get("request_id") or (data.get("messages") or [{}])[0].get("id") or "")
        if status == "SENT":
            log.sent_at = timezone.now()
    except (requests.RequestException, ValueError, KeyError) as exc:
        log.status = CommunicationLog.Status.FAILED
        log.error = str(exc)
    log.save()
    return log
