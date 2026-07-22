import json
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .decorators import roles_required
from .forms import (
    AcademicSessionForm,
    CommunicationForm,
    CustomPasswordChangeForm,
    ExamForm,
    FeePaymentForm,
    FeeStructureForm,
    LoginForm,
    OnlineFeeForm,
    PayrollGenerateForm,
    PayrollPaymentForm,
    PublicStudentRegistrationForm,
    ResultSearchForm,
    RouteStopForm,
    SalaryStructureForm,
    SchoolClassForm,
    SchoolProfileForm,
    SectionForm,
    StaffForm,
    StudentForm,
    StudentTransportAssignmentForm,
    SubjectForm,
    TeacherAssignmentForm,
    TimetableEntryForm,
    TransportRouteForm,
    VehicleForm,
)
from .models import (
    AcademicSession,
    Attendance,
    AuditLog,
    CommunicationLog,
    Exam,
    FeePayment,
    FeeStructure,
    Mark,
    ParentStudentAccess,
    PaymentOrder,
    PayrollRecord,
    RouteStop,
    SalaryStructure,
    SchoolClass,
    SchoolProfile,
    Section,
    Student,
    StudentTransportAssignment,
    Subject,
    TeacherAssignment,
    TimetableEntry,
    TransportRoute,
    User,
    Vehicle,
)
from .services import (
    accessible_students,
    assigned_sections,
    audit,
    calculate_result,
    can_access_section,
    can_access_student,
    create_razorpay_order,
    finalize_payment,
    generate_password,
    generate_username,
    id_card_pdf_bytes,
    payment_gateway_configured,
    payslip_pdf_bytes,
    prepare_math_captcha,
    result_pdf_bytes,
    send_communication,
    validate_captcha,
    verify_razorpay_payment_signature,
    verify_razorpay_webhook_signature,
)


PORTAL_ROLE_MAP = {
    "management": {User.Role.DIRECTOR, User.Role.PRINCIPAL},
    "teacher": {User.Role.TEACHER},
    "parent": {User.Role.PARENT},
    "student": {User.Role.STUDENT},
}


def home(request):
    return redirect("dashboard" if request.user.is_authenticated else "login")


def _home_for(user):
    return user.portal_home_name if user.is_authenticated else "login"


def login_view(request, portal=None):
    if request.user.is_authenticated:
        return redirect(_home_for(request.user))
    form = LoginForm(request=request, data=request.POST or None)
    if request.method == "POST":
        valid_captcha, captcha_error = validate_captcha(request)
        if not valid_captcha:
            form.add_error(None, captcha_error)
        elif form.is_valid():
            candidate = form.get_user()
            expected_roles = PORTAL_ROLE_MAP.get(portal)
            if expected_roles and not (candidate.is_superuser or candidate.role in expected_roles):
                form.add_error(None, f"This User ID cannot access the {portal.title()} portal.")
            else:
                auth_login(request, candidate)
                audit(request, "LOGIN", candidate, f"Signed in through {portal or 'general'} portal")
                next_url = request.GET.get("next", "")
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                ):
                    return redirect(next_url)
                return redirect(_home_for(candidate))
    captcha_question = "" if settings.TURNSTILE_SITE_KEY else prepare_math_captcha(request)
    portal_labels = {
        "management": "Principal / Director",
        "teacher": "Teacher",
        "parent": "Parent / Guardian",
        "student": "Student",
    }
    return render(
        request,
        "portal/login.html",
        {
            "form": form,
            "captcha_question": captcha_question,
            "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
            "portal_label": portal_labels.get(portal, "School ERP"),
            "portal": portal or "general",
        },
    )


def management_login(request):
    return login_view(request, "management")


def teacher_login(request):
    return login_view(request, "teacher")


def parent_login(request):
    return login_view(request, "parent")


def student_login(request):
    return login_view(request, "student")


@login_required
def logout_view(request):
    audit(request, "LOGOUT", request.user)
    auth_logout(request)
    return redirect("login")


@login_required
def change_password(request):
    form = CustomPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        audit(request, "PASSWORD_CHANGED", user)
        messages.success(request, "Password changed successfully.")
        return redirect("dashboard")
    return render(request, "portal/form_page.html", {"form": form, "title": "Change password", "submit_label": "Update password"})


@login_required
def dashboard(request):
    return redirect(_home_for(request.user))


def _management_context():
    today = timezone.localdate()
    students = Student.objects.filter(status=Student.Status.ACTIVE)
    sections = Section.objects.all()
    pending = Student.objects.filter(status=Student.Status.PENDING).count()
    present_today = Attendance.objects.filter(date=today, status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]).count()
    paid = FeePayment.objects.aggregate(v=Sum("amount"))["v"] or Decimal("0")
    total_fee = sum((student.total_fee for student in students.select_related("session", "section__school_class")), Decimal("0"))
    cards = {
        "students": students.count(),
        "sections": sections.count(),
        "teachers": User.objects.filter(role=User.Role.TEACHER, is_active=True).count(),
        "pending": pending,
        "present_today": present_today,
        "paid": paid,
        "due": max(total_fee - paid, Decimal("0")),
    }
    class_data = list(
        students.values("section__school_class__name", "section__school_class__order")
        .annotate(total=Count("id"))
        .order_by("section__school_class__order")
    )
    return {
        "cards": cards,
        "recent_students": students.select_related("section__school_class").order_by("-created_at")[:6],
        "chart_labels": [row["section__school_class__name"] for row in class_data],
        "chart_values": [row["total"] for row in class_data],
        "recent_payments": FeePayment.objects.select_related("student")[:5],
        "recent_audit": AuditLog.objects.select_related("actor")[:8],
    }


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL, User.Role.ACCOUNTANT)
def management_dashboard(request):
    context = _management_context()
    context["management_mode"] = True
    return render(request, "portal/dashboard.html", context)


@roles_required(User.Role.TEACHER)
def teacher_dashboard(request):
    today = timezone.localdate()
    sections = assigned_sections(request.user)
    students = Student.objects.filter(status=Student.Status.ACTIVE, section__in=sections)
    present_today = Attendance.objects.filter(student__in=students, date=today, status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]).count()
    cards = {
        "students": students.count(),
        "sections": sections.count(),
        "present_today": present_today,
        "assignments": request.user.teaching_assignments.count(),
    }
    class_data = list(students.values("section__school_class__name", "section__school_class__order").annotate(total=Count("id")).order_by("section__school_class__order"))
    return render(
        request,
        "portal/dashboard.html",
        {
            "cards": cards,
            "recent_students": students.select_related("section__school_class").order_by("-created_at")[:6],
            "chart_labels": [row["section__school_class__name"] for row in class_data],
            "chart_values": [row["total"] for row in class_data],
            "management_mode": False,
        },
    )


@roles_required(User.Role.PARENT)
def parent_dashboard(request):
    students = accessible_students(request.user).filter(status=Student.Status.ACTIVE)
    return render(
        request,
        "portal/family_dashboard.html",
        {
            "students": students,
            "is_parent": True,
            "payment_enabled": payment_gateway_configured(),
        },
    )


@roles_required(User.Role.STUDENT)
def student_dashboard(request):
    student = Student.objects.filter(portal_user=request.user).select_related("section__school_class", "session").first()
    return render(
        request,
        "portal/family_dashboard.html",
        {
            "students": [student] if student else [],
            "student": student,
            "is_parent": False,
            "payment_enabled": payment_gateway_configured(),
        },
    )


@roles_required(User.Role.TRANSPORT)
def transport_dashboard(request):
    return redirect("transport_center")


@login_required
def student_list(request):
    qs = accessible_students(request.user)
    q = request.GET.get("q", "").strip()
    class_id = request.GET.get("class")
    section_id = request.GET.get("section")
    status = request.GET.get("status")
    if q:
        qs = qs.filter(Q(admission_no__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(guardian_phone__icontains=q))
    if class_id:
        qs = qs.filter(section__school_class_id=class_id)
    if section_id:
        qs = qs.filter(section_id=section_id)
    if status:
        qs = qs.filter(status=status)
    section_ids = qs.values_list("section_id", flat=True)
    return render(
        request,
        "portal/student_list.html",
        {
            "students": qs[:500],
            "classes": SchoolClass.objects.filter(sections__id__in=section_ids).distinct(),
            "sections": Section.objects.filter(id__in=section_ids).distinct(),
            "statuses": Student.Status.choices,
        },
    )


@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related("section__school_class", "session", "portal_user"), pk=pk)
    if not can_access_student(request.user, student):
        raise Http404
    can_view_fees = request.user.is_management or request.user.role in {User.Role.ACCOUNTANT, User.Role.PARENT, User.Role.STUDENT}
    payments = student.fee_payments.all()[:10] if can_view_fees else []
    attendance = student.attendance_records.all()[:20]
    exams = Exam.objects.filter(session=student.session)
    if request.user.role in {User.Role.PARENT, User.Role.STUDENT}:
        exams = exams.filter(published=True)
    transport = StudentTransportAssignment.objects.filter(student=student).select_related("route__vehicle", "stop").first()
    return render(
        request,
        "portal/student_detail.html",
        {
            "student": student,
            "payments": payments,
            "attendance": attendance,
            "exams": exams.order_by("-start_date"),
            "transport": transport,
            "payment_enabled": payment_gateway_configured(),
        },
    )


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def student_create(request):
    form = StudentForm(
        request.POST or None,
        request.FILES or None,
        initial={
            "admission_date": timezone.localdate(),
            "session": AcademicSession.objects.filter(is_active=True).first(),
            "status": Student.Status.ACTIVE,
        },
    )
    if request.method == "POST" and form.is_valid():
        student = form.save(commit=False)
        student.created_by = request.user
        student.save()
        audit(request, "STUDENT_CREATED", student)
        messages.success(request, "Student record created.")
        return redirect("student_detail", pk=student.pk)
    return render(request, "portal/student_form.html", {"form": form, "title": "Add student"})


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentForm(request.POST or None, request.FILES or None, instance=student)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request, "STUDENT_UPDATED", student)
        messages.success(request, "Student record updated.")
        return redirect("student_detail", pk=student.pk)
    return render(request, "portal/student_form.html", {"form": form, "title": "Edit student", "student": student})


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
@require_POST
def student_approve(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.status = Student.Status.ACTIVE
    student.save(update_fields=["status"])
    audit(request, "STUDENT_APPROVED", student)
    messages.success(request, f"{student.full_name} approved.")
    return redirect("student_detail", pk=pk)


def public_register(request):
    initial = {"admission_date": timezone.localdate(), "session": AcademicSession.objects.filter(is_active=True).first()}
    form = PublicStudentRegistrationForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST":
        valid_captcha, captcha_error = validate_captcha(request)
        if not valid_captcha:
            form.add_error(None, captcha_error)
        elif form.is_valid():
            student = form.save(commit=False)
            student.admission_no = f"REG-{timezone.localdate().year}-{uuid4().hex[:6].upper()}"
            student.status = Student.Status.PENDING
            student.privacy_consent = True
            student.privacy_consent_at = timezone.now()
            student.privacy_consent_ip = request.META.get("REMOTE_ADDR") or None
            student.save()
            audit(request, "PUBLIC_REGISTRATION", student, "Parent/guardian consent checkbox accepted")
            return render(request, "portal/registration_success.html", {"student": student})
    captcha_question = "" if settings.TURNSTILE_SITE_KEY else prepare_math_captcha(request)
    return render(request, "portal/public_register.html", {"form": form, "captcha_question": captcha_question, "turnstile_site_key": settings.TURNSTILE_SITE_KEY})


@login_required
def class_list(request):
    if not (request.user.is_management or request.user.role == User.Role.TEACHER):
        return redirect("student_list")
    sections = assigned_sections(request.user).select_related("school_class", "class_teacher").annotate(student_count=Count("students", filter=Q(students__status=Student.Status.ACTIVE)))
    return render(request, "portal/class_list.html", {"sections": sections})


@login_required
def section_detail(request, pk):
    section = get_object_or_404(Section.objects.select_related("school_class", "class_teacher"), pk=pk)
    if not can_access_section(request.user, section):
        raise Http404
    students = section.students.filter(status=Student.Status.ACTIVE).order_by("roll_number", "first_name")
    assignments = section.teacher_assignments.select_related("teacher", "subject")
    return render(request, "portal/section_detail.html", {"section": section, "students": students, "assignments": assignments})


@login_required
def attendance_mark(request, section_id):
    section = get_object_or_404(Section, pk=section_id)
    if not can_access_section(request.user, section):
        raise Http404
    selected_date = request.POST.get("date") or request.GET.get("date") or timezone.localdate().isoformat()
    try:
        attendance_date = date.fromisoformat(selected_date)
    except ValueError:
        attendance_date = timezone.localdate()
    students = list(section.students.filter(status=Student.Status.ACTIVE).order_by("roll_number", "first_name"))
    existing = {item.student_id: item.status for item in Attendance.objects.filter(student__in=students, date=attendance_date)}
    if request.method == "POST":
        with transaction.atomic():
            for student in students:
                status = request.POST.get(f"status_{student.pk}", Attendance.Status.PRESENT)
                if status not in Attendance.Status.values:
                    status = Attendance.Status.PRESENT
                Attendance.objects.update_or_create(
                    student=student,
                    date=attendance_date,
                    defaults={"status": status, "marked_by": request.user},
                )
        audit(request, "ATTENDANCE_SAVED", section, f"Date {attendance_date}; {len(students)} students")
        messages.success(request, f"Attendance saved for {attendance_date.strftime('%d-%m-%Y')}.")
        return redirect(f"{request.path}?date={attendance_date.isoformat()}")
    rows = [{"student": student, "status": existing.get(student.id, Attendance.Status.PRESENT)} for student in students]
    return render(request, "portal/attendance_mark.html", {"section": section, "rows": rows, "selected_date": attendance_date, "status_choices": Attendance.Status.choices})


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL, User.Role.TEACHER)
def marks_hub(request):
    exams = Exam.objects.select_related("session").all()
    if request.user.is_management or request.user.is_superuser:
        assignments = TeacherAssignment.objects.select_related("section__school_class", "subject", "teacher")
    else:
        assignments = request.user.teaching_assignments.select_related("section__school_class", "subject")
    return render(request, "portal/marks_hub.html", {"exams": exams, "assignments": assignments})


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL, User.Role.TEACHER)
def marks_entry(request, exam_id, section_id, subject_id):
    exam = get_object_or_404(Exam, pk=exam_id)
    section = get_object_or_404(Section, pk=section_id)
    subject = get_object_or_404(Subject, pk=subject_id)
    if not can_access_section(request.user, section, subject):
        raise Http404
    students = list(section.students.filter(status=Student.Status.ACTIVE, session=exam.session).order_by("roll_number", "first_name"))
    existing = {mark.student_id: mark for mark in Mark.objects.filter(student__in=students, exam=exam, subject=subject)}
    if request.method == "POST":
        errors = []
        with transaction.atomic():
            for student in students:
                raw_obtained = request.POST.get(f"obtained_{student.pk}", "").strip()
                if raw_obtained == "":
                    continue
                try:
                    obtained = Decimal(raw_obtained)
                    maximum = Decimal(request.POST.get(f"max_{student.pk}", "100"))
                except (InvalidOperation, TypeError):
                    errors.append(f"Invalid marks for {student.full_name}")
                    continue
                if obtained < 0 or maximum <= 0 or obtained > maximum:
                    errors.append(f"Marks must be between 0 and maximum for {student.full_name}")
                    continue
                Mark.objects.update_or_create(
                    student=student,
                    exam=exam,
                    subject=subject,
                    defaults={
                        "obtained_marks": obtained,
                        "max_marks": maximum,
                        "remarks": request.POST.get(f"remarks_{student.pk}", "")[:200],
                        "entered_by": request.user,
                    },
                )
        if errors:
            for error in errors[:8]:
                messages.error(request, error)
        else:
            audit(request, "MARKS_SAVED", section, f"{exam.name} / {subject.name}")
            messages.success(request, "Marks saved successfully.")
            return redirect(request.path)
        existing = {mark.student_id: mark for mark in Mark.objects.filter(student__in=students, exam=exam, subject=subject)}
    rows = [{"student": student, "mark": existing.get(student.id)} for student in students]
    return render(request, "portal/marks_entry.html", {"exam": exam, "section": section, "subject": subject, "rows": rows})


@login_required
def result_view(request, student_id, exam_id):
    student = get_object_or_404(Student, pk=student_id)
    exam_qs = Exam.objects.filter(pk=exam_id, session=student.session)
    if request.user.role in {User.Role.PARENT, User.Role.STUDENT}:
        exam_qs = exam_qs.filter(published=True)
    exam = get_object_or_404(exam_qs)
    if not can_access_student(request.user, student):
        raise Http404
    return render(request, "portal/result.html", {"student": student, "exam": exam, **calculate_result(student, exam), "public_mode": False})


@login_required
def result_pdf(request, student_id, exam_id):
    student = get_object_or_404(Student, pk=student_id)
    exam_qs = Exam.objects.filter(pk=exam_id, session=student.session)
    if request.user.role in {User.Role.PARENT, User.Role.STUDENT}:
        exam_qs = exam_qs.filter(published=True)
    exam = get_object_or_404(exam_qs)
    if not can_access_student(request.user, student):
        raise Http404
    response = HttpResponse(result_pdf_bytes(student, exam), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="result-{student.admission_no}-{exam.id}.pdf"'
    return response


def public_results(request):
    form = ResultSearchForm(request.POST or None)
    student = None
    exams = []
    if request.method == "POST":
        valid_captcha, captcha_error = validate_captcha(request)
        if not valid_captcha:
            form.add_error(None, captcha_error)
        elif form.is_valid():
            student = Student.objects.filter(
                admission_no__iexact=form.cleaned_data["admission_no"],
                date_of_birth=form.cleaned_data["date_of_birth"],
                status=Student.Status.ACTIVE,
            ).first()
            if not student:
                form.add_error(None, "No matching active student record found.")
            else:
                request.session["public_result_student"] = student.pk
                exams = Exam.objects.filter(session=student.session, published=True)
    captcha_question = "" if settings.TURNSTILE_SITE_KEY else prepare_math_captcha(request)
    return render(request, "portal/public_results.html", {"form": form, "student": student, "exams": exams, "captcha_question": captcha_question, "turnstile_site_key": settings.TURNSTILE_SITE_KEY})


def public_result_detail(request, exam_id):
    student_id = request.session.get("public_result_student")
    if not student_id:
        return redirect("public_results")
    student = get_object_or_404(Student, pk=student_id, status=Student.Status.ACTIVE)
    exam = get_object_or_404(Exam, pk=exam_id, session=student.session, published=True)
    return render(request, "portal/result.html", {"student": student, "exam": exam, **calculate_result(student, exam), "public_mode": True})


def public_result_pdf(request, exam_id):
    student_id = request.session.get("public_result_student")
    if not student_id:
        return redirect("public_results")
    student = get_object_or_404(Student, pk=student_id, status=Student.Status.ACTIVE)
    exam = get_object_or_404(Exam, pk=exam_id, session=student.session, published=True)
    response = HttpResponse(result_pdf_bytes(student, exam), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="result-{student.admission_no}-{exam.id}.pdf"'
    return response


@login_required
def id_card_pdf(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    if not can_access_student(request.user, student):
        raise Http404
    response = HttpResponse(id_card_pdf_bytes(student, request), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="id-card-{student.admission_no}.pdf"'
    return response


def verify_student(request, admission_no):
    student = get_object_or_404(Student, admission_no=admission_no, status=Student.Status.ACTIVE)
    return render(request, "portal/student_verify.html", {"student": student})


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def student_portal_accounts(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    credentials = []
    if request.method == "POST":
        action = request.POST.get("action")
        if action in {"create_student", "reset_student"}:
            user = student.portal_user
            if user is None:
                username = generate_username(student.admission_no, "", prefix="student.")
                user = User(username=username, first_name=student.first_name, last_name=student.last_name, email=student.email, phone=student.phone, role=User.Role.STUDENT)
            password = generate_password()
            user.set_password(password)
            user.must_change_password = True
            user.is_active = True
            user.save()
            if student.portal_user_id != user.id:
                student.portal_user = user
                student.save(update_fields=["portal_user"])
            credentials.append({"name": student.full_name, "role": "Student", "username": user.username, "password": password})
            audit(request, "STUDENT_PORTAL_ACCOUNT", student)
        elif action in {"create_parent", "reset_parent"}:
            link = student.parent_links.select_related("parent").first()
            parent = link.parent if link else None
            if parent is None:
                phone = student.guardian_phone
                parent = User.objects.filter(role=User.Role.PARENT, phone=phone).first()
                if parent is None:
                    name = student.guardian_name or student.father_name or "Parent"
                    parts = name.split(maxsplit=1)
                    parent = User(
                        username=generate_username(parts[0], parts[1] if len(parts) > 1 else "", prefix="parent."),
                        first_name=parts[0],
                        last_name=parts[1] if len(parts) > 1 else "",
                        email=student.guardian_email,
                        phone=phone,
                        role=User.Role.PARENT,
                    )
            password = generate_password()
            parent.set_password(password)
            parent.must_change_password = True
            parent.is_active = True
            parent.save()
            ParentStudentAccess.objects.get_or_create(parent=parent, student=student, defaults={"relationship": "Guardian", "is_primary": True})
            credentials.append({"name": parent.get_full_name() or "Guardian", "role": "Parent", "username": parent.username, "password": password})
            audit(request, "PARENT_PORTAL_ACCOUNT", student)
        if credentials:
            messages.success(request, "Portal credentials generated. Save or print them now.")
    return render(
        request,
        "portal/portal_accounts.html",
        {
            "student": student,
            "student_user": student.portal_user,
            "parent_links": student.parent_links.select_related("parent"),
            "credentials": credentials,
        },
    )


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def staff_list(request):
    staff = User.objects.filter(is_superuser=False, role__in=[User.Role.DIRECTOR, User.Role.PRINCIPAL, User.Role.TEACHER, User.Role.ACCOUNTANT, User.Role.TRANSPORT]).order_by("role", "first_name")
    return render(request, "portal/staff_list.html", {"staff": staff})


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def staff_create(request):
    form = StaffForm(request.POST or None)
    credentials = None
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.username = generate_username(user.first_name, user.last_name)
        password = generate_password()
        user.set_password(password)
        user.must_change_password = True
        user.save()
        credentials = {"username": user.username, "password": password, "name": user.get_full_name()}
        audit(request, "STAFF_CREATED", user)
        form = StaffForm()
    return render(request, "portal/staff_form.html", {"form": form, "credentials": credentials})


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
@require_POST
def staff_toggle(request, pk):
    staff = get_object_or_404(User, pk=pk, is_superuser=False)
    if staff.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
    else:
        staff.is_active = not staff.is_active
        staff.save(update_fields=["is_active"])
        audit(request, "STAFF_STATUS_CHANGED", staff, f"Active={staff.is_active}")
        messages.success(request, "Staff account status updated.")
    return redirect("staff_list")


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def staff_reset_password(request, pk):
    staff = get_object_or_404(User, pk=pk, is_superuser=False)
    password = generate_password()
    staff.set_password(password)
    staff.must_change_password = True
    staff.save(update_fields=["password", "must_change_password"])
    audit(request, "STAFF_PASSWORD_RESET", staff)
    return render(request, "portal/credentials.html", {"credentials": {"username": staff.username, "password": password, "name": staff.get_full_name()}})


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL, User.Role.ACCOUNTANT)
def fee_list(request):
    students = Student.objects.filter(status=Student.Status.ACTIVE).select_related("section__school_class", "session")
    q = request.GET.get("q", "").strip()
    if q:
        students = students.filter(Q(admission_no__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(guardian_phone__icontains=q))
    return render(
        request,
        "portal/fee_list.html",
        {
            "students": students[:500],
            "recent_payments": FeePayment.objects.select_related("student")[:10],
            "online_orders": PaymentOrder.objects.select_related("student")[:10],
            "payment_enabled": payment_gateway_configured(),
        },
    )


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL, User.Role.ACCOUNTANT)
def fee_payment_create(request, student_id=None):
    initial = {"student": student_id, "payment_date": timezone.localdate(), "receipt_no": f"RCPT-{timezone.now().strftime('%Y%m%d%H%M%S')}"}
    form = FeePaymentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        payment = form.save(commit=False)
        payment.received_by = request.user
        payment.save()
        audit(request, "FEE_RECORDED", payment)
        messages.success(request, "Fee payment recorded.")
        return redirect("student_detail", pk=payment.student_id)
    return render(request, "portal/form_page.html", {"form": form, "title": "Record fee payment", "submit_label": "Save payment"})


@login_required
def online_fee(request, student_id=None):
    allowed = accessible_students(request.user).filter(status=Student.Status.ACTIVE)
    if request.user.role == User.Role.TEACHER:
        raise Http404
    initial = {"student": student_id}
    if student_id:
        student = get_object_or_404(allowed, pk=student_id)
        initial["amount"] = student.fee_due
    form = OnlineFeeForm(request.POST or None, initial=initial, students=allowed)
    if request.method == "POST" and form.is_valid():
        if not payment_gateway_configured():
            form.add_error(None, "Online payment gateway is not configured yet. Add Razorpay test/live keys in the server environment.")
        else:
            try:
                order = create_razorpay_order(form.cleaned_data["student"], form.cleaned_data["amount"], request.user)
            except Exception as exc:
                form.add_error(None, f"Could not create payment order: {exc}")
            else:
                audit(request, "ONLINE_PAYMENT_ORDER_CREATED", order)
                return render(
                    request,
                    "portal/payment_checkout.html",
                    {
                        "order": order,
                        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                        "school": SchoolProfile.objects.first(),
                        "amount_paise": int(order.amount * 100),
                    },
                )
    return render(
        request,
        "portal/online_fee.html",
        {
            "form": form,
            "payment_enabled": payment_gateway_configured(),
            "students": allowed,
        },
    )


@login_required
@require_POST
def payment_verify(request):
    order = get_object_or_404(PaymentOrder, gateway_order_id=request.POST.get("razorpay_order_id", ""))
    if not can_access_student(request.user, order.student):
        raise Http404
    payment_id = request.POST.get("razorpay_payment_id", "")
    signature = request.POST.get("razorpay_signature", "")
    if not verify_razorpay_payment_signature(order.gateway_order_id, payment_id, signature):
        order.status = PaymentOrder.Status.FAILED
        order.save(update_fields=["status", "updated_at"])
        messages.error(request, "Payment signature verification failed. No fee receipt was created.")
        return redirect("online_fee", student_id=order.student_id)
    order, payment = finalize_payment(order, payment_id, signature, {"source": "checkout_callback"})
    audit(request, "ONLINE_PAYMENT_VERIFIED", payment)
    return render(request, "portal/payment_success.html", {"order": order, "payment": payment})


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not verify_razorpay_webhook_signature(request.body, signature):
        return JsonResponse({"ok": False, "error": "invalid signature"}, status=400)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
    event = payload.get("event")
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = payment_entity.get("order_id")
    if order_id:
        order = PaymentOrder.objects.filter(gateway_order_id=order_id).first()
        if order and event in {"payment.captured", "order.paid"}:
            finalize_payment(order, payment_entity.get("id", ""), signature, payload)
        elif order and event == "payment.failed":
            order.status = PaymentOrder.Status.FAILED
            order.raw_payload = payload
            order.save(update_fields=["status", "raw_payload", "updated_at"])
    return JsonResponse({"ok": True})


@login_required
def timetable(request):
    entries = TimetableEntry.objects.select_related("section__school_class", "subject", "teacher", "session")
    selected_student = None
    if request.user.is_management or request.user.role == User.Role.ACCOUNTANT:
        section_id = request.GET.get("section")
        if section_id:
            entries = entries.filter(section_id=section_id)
    elif request.user.role == User.Role.TEACHER:
        entries = entries.filter(teacher=request.user)
    elif request.user.role in {User.Role.PARENT, User.Role.STUDENT}:
        students = accessible_students(request.user).filter(status=Student.Status.ACTIVE)
        student_id = request.GET.get("student")
        selected_student = get_object_or_404(students, pk=student_id) if student_id else students.first()
        entries = entries.filter(section=selected_student.section) if selected_student else entries.none()
    else:
        entries = entries.none()
    form = None
    if request.user.is_management:
        form = TimetableEntryForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            item = form.save()
            audit(request, "TIMETABLE_ENTRY_CREATED", item)
            messages.success(request, "Timetable entry saved.")
            return redirect("timetable")
    days = []
    for value, label in TimetableEntry.Weekday.choices:
        day_entries = list(entries.filter(weekday=value).order_by("start_time"))
        if day_entries or request.user.is_management:
            days.append({"value": value, "label": label, "entries": day_entries})
    return render(
        request,
        "portal/timetable.html",
        {
            "days": days,
            "form": form,
            "sections": Section.objects.all(),
            "family_students": accessible_students(request.user) if request.user.role in {User.Role.PARENT, User.Role.STUDENT} else [],
            "selected_student": selected_student,
        },
    )


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
@require_POST
def timetable_delete(request, pk):
    item = get_object_or_404(TimetableEntry, pk=pk)
    audit(request, "TIMETABLE_ENTRY_DELETED", item)
    item.delete()
    messages.success(request, "Timetable entry deleted.")
    return redirect("timetable")


@login_required
def transport_center(request):
    staff_mode = request.user.is_management or request.user.role == User.Role.TRANSPORT
    family_students = accessible_students(request.user).filter(status=Student.Status.ACTIVE) if request.user.role in {User.Role.PARENT, User.Role.STUDENT} else Student.objects.none()
    forms = {}
    if staff_mode:
        form_map = {
            "vehicle": VehicleForm,
            "route": TransportRouteForm,
            "stop": RouteStopForm,
            "assignment": StudentTransportAssignmentForm,
        }
        forms = {key: cls(prefix=key) for key, cls in form_map.items()}
        if request.method == "POST":
            action = request.POST.get("action")
            cls = form_map.get(action)
            if cls:
                form = cls(request.POST, prefix=action)
                forms[action] = form
                if form.is_valid():
                    if action == "assignment":
                        obj = form.save(commit=False)
                        obj, _ = StudentTransportAssignment.objects.update_or_create(
                            student=obj.student,
                            defaults={
                                "route": obj.route,
                                "stop": obj.stop,
                                "start_date": obj.start_date,
                                "monthly_fee_override": obj.monthly_fee_override,
                                "active": obj.active,
                            },
                        )
                    else:
                        obj = form.save()
                    audit(request, f"TRANSPORT_{action.upper()}_SAVED", obj)
                    messages.success(request, f"Transport {action} saved.")
                    return redirect("transport_center")
    assignments = StudentTransportAssignment.objects.select_related("student__section__school_class", "route__vehicle", "stop")
    if not staff_mode:
        assignments = assignments.filter(student__in=family_students)
    return render(
        request,
        "portal/transport.html",
        {
            "staff_mode": staff_mode,
            "forms": forms,
            "vehicles": Vehicle.objects.all(),
            "routes": TransportRoute.objects.prefetch_related("stops"),
            "assignments": assignments,
        },
    )


@login_required
def payroll_dashboard(request):
    manage = request.user.is_management
    if not manage and request.user.role not in {User.Role.TEACHER, User.Role.ACCOUNTANT, User.Role.TRANSPORT}:
        raise Http404
    salary_form = SalaryStructureForm(prefix="salary") if manage else None
    payroll_form = PayrollGenerateForm(prefix="payroll") if manage else None
    if manage and request.method == "POST":
        action = request.POST.get("action")
        if action == "salary":
            salary_form = SalaryStructureForm(request.POST, prefix="salary")
            if salary_form.is_valid():
                data = salary_form.cleaned_data
                structure, _ = SalaryStructure.objects.update_or_create(
                    staff=data["staff"],
                    defaults={
                        "basic": data["basic"],
                        "hra": data["hra"],
                        "allowances": data["allowances"],
                        "deductions": data["deductions"],
                        "effective_from": data["effective_from"],
                    },
                )
                audit(request, "SALARY_STRUCTURE_SAVED", structure)
                messages.success(request, "Salary structure saved.")
                return redirect("payroll_dashboard")
        elif action == "payroll":
            payroll_form = PayrollGenerateForm(request.POST, prefix="payroll")
            if payroll_form.is_valid():
                staff = payroll_form.cleaned_data["staff"]
                month = payroll_form.cleaned_data["month"]
                structure = staff.salary_structure
                record, created = PayrollRecord.objects.update_or_create(
                    staff=staff,
                    month=month,
                    defaults={
                        "basic": structure.basic,
                        "hra": structure.hra,
                        "allowances": structure.allowances,
                        "deductions": structure.deductions,
                        "gross": structure.gross,
                        "net": structure.net,
                        "generated_by": request.user,
                    },
                )
                audit(request, "PAYROLL_GENERATED", record)
                messages.success(request, "Payroll generated." if created else "Payroll refreshed from current salary structure.")
                return redirect("payroll_dashboard")
    records = PayrollRecord.objects.select_related("staff") if manage else PayrollRecord.objects.filter(staff=request.user)
    return render(
        request,
        "portal/payroll.html",
        {
            "manage": manage,
            "salary_form": salary_form,
            "payroll_form": payroll_form,
            "structures": SalaryStructure.objects.select_related("staff") if manage else SalaryStructure.objects.filter(staff=request.user),
            "records": records,
        },
    )


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def payroll_mark_paid(request, pk):
    record = get_object_or_404(PayrollRecord, pk=pk)
    form = PayrollPaymentForm(request.POST or None, instance=record, initial={"paid_date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.status = PayrollRecord.Status.PAID
        record.save()
        audit(request, "PAYROLL_MARKED_PAID", record)
        messages.success(request, "Payroll marked as paid.")
        return redirect("payroll_dashboard")
    return render(request, "portal/form_page.html", {"form": form, "title": f"Mark payroll paid — {record}", "submit_label": "Confirm paid"})


@login_required
def payslip_pdf(request, pk):
    record = get_object_or_404(PayrollRecord.objects.select_related("staff"), pk=pk)
    if not request.user.is_management and record.staff_id != request.user.id:
        raise Http404
    response = HttpResponse(payslip_pdf_bytes(record), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="payslip-{record.staff.username}-{record.month:%Y-%m}.pdf"'
    return response


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def communications(request):
    form = CommunicationForm(request.POST or None)
    sent_count = 0
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        recipients = []
        audience = data["audience"]
        if audience == CommunicationForm.Audience.STUDENT:
            student = data["student"]
            recipients = [(student.full_name, student.guardian_phone)]
        elif audience == CommunicationForm.Audience.SECTION:
            recipients = list(
                data["section"].students.filter(status=Student.Status.ACTIVE).values_list("first_name", "guardian_phone")
            )
        elif audience == CommunicationForm.Audience.ALL:
            recipients = list(Student.objects.filter(status=Student.Status.ACTIVE).values_list("first_name", "guardian_phone"))
        elif audience == CommunicationForm.Audience.STAFF:
            recipients = list(User.objects.filter(is_active=True, role__in=[User.Role.TEACHER, User.Role.ACCOUNTANT, User.Role.TRANSPORT, User.Role.PRINCIPAL]).exclude(phone="").values_list("first_name", "phone"))
        seen = set()
        for name, phone in recipients[:500]:
            digits = "".join(ch for ch in (phone or "") if ch.isdigit())
            if not digits or digits in seen:
                continue
            seen.add(digits)
            send_communication(
                data["channel"],
                name,
                phone,
                data["message"],
                sent_by=request.user,
                audience=audience,
                template_name=data.get("template_name", ""),
            )
            sent_count += 1
        audit(request, "COMMUNICATION_BATCH", description=f"{data['channel']} to {sent_count} recipients")
        messages.success(request, f"{sent_count} message records processed. Check delivery status below.")
        return redirect("communications")
    return render(
        request,
        "portal/communications.html",
        {
            "form": form,
            "logs": CommunicationLog.objects.select_related("sent_by")[:100],
            "sms_configured": bool(settings.MSG91_AUTH_KEY and settings.MSG91_TEMPLATE_ID),
            "whatsapp_configured": bool(settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_TEMPLATE_NAME),
            "sent_count": sent_count,
        },
    )


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def audit_logs(request):
    return render(request, "portal/audit_logs.html", {"logs": AuditLog.objects.select_related("actor")[:500]})


@roles_required(User.Role.DIRECTOR, User.Role.PRINCIPAL)
def setup_center(request):
    profile = SchoolProfile.objects.first() or SchoolProfile()
    form_map = {
        "profile": (SchoolProfileForm, {"instance": profile}),
        "session": (AcademicSessionForm, {}),
        "class": (SchoolClassForm, {}),
        "section": (SectionForm, {}),
        "subject": (SubjectForm, {}),
        "exam": (ExamForm, {}),
        "fee": (FeeStructureForm, {}),
        "assignment": (TeacherAssignmentForm, {}),
    }
    forms = {key: cls(prefix=key, **kwargs) for key, (cls, kwargs) in form_map.items()}
    if request.method == "POST":
        action = request.POST.get("action")
        if action in form_map:
            cls, kwargs = form_map[action]
            form = cls(request.POST, request.FILES, prefix=action, **kwargs)
            forms[action] = form
            if form.is_valid():
                obj = form.save()
                audit(request, f"SETUP_{action.upper()}_SAVED", obj)
                messages.success(request, f"{action.title()} saved successfully.")
                return redirect("setup_center")
    return render(
        request,
        "portal/setup_center.html",
        {
            "forms": forms,
            "sessions": AcademicSession.objects.all(),
            "classes": SchoolClass.objects.all(),
            "sections": Section.objects.select_related("school_class", "class_teacher"),
            "subjects": Subject.objects.all(),
            "exams": Exam.objects.select_related("session"),
            "fees": FeeStructure.objects.select_related("session", "school_class"),
            "assignments": TeacherAssignment.objects.select_related("teacher", "section__school_class", "subject"),
        },
    )


def pwa_manifest(request):
    school = SchoolProfile.objects.first()
    name = school.school_name if school else "School ERP"
    return JsonResponse(
        {
            "name": f"{name} ERP",
            "short_name": "School ERP",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#f4f7fb",
            "theme_color": "#1d4ed8",
            "icons": [
                {"src": "/static/portal/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/portal/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        },
        content_type="application/manifest+json",
    )


def service_worker(request):
    # The PWA intentionally does not cache authenticated ERP pages or student data.
    script = """
const VERSION='school-erp-pwa-v3';
self.addEventListener('install', event => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  // Keep private school records network-only. The service worker exists for
  // installability and never persists authenticated HTML/API responses.
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request));
});
"""
    response = HttpResponse(script, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
