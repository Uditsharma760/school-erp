from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    AcademicSession,
    CommunicationLog,
    ParentStudentAccess,
    PayrollRecord,
    SchoolClass,
    Section,
    Student,
    User,
)


class ERPAccessTests(TestCase):
    def setUp(self):
        self.session = AcademicSession.objects.create(
            name="2026-27",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.school_class = SchoolClass.objects.create(name="Class 1", order=1)
        self.teacher = User.objects.create_user(
            username="teacher", password="pass12345", role=User.Role.TEACHER
        )
        self.other_teacher = User.objects.create_user(
            username="other", password="pass12345", role=User.Role.TEACHER
        )
        self.principal = User.objects.create_user(
            username="principal", password="pass12345", role=User.Role.PRINCIPAL
        )
        self.parent = User.objects.create_user(
            username="parent", password="pass12345", role=User.Role.PARENT
        )
        self.student_user = User.objects.create_user(
            username="student", password="pass12345", role=User.Role.STUDENT
        )
        self.section = Section.objects.create(
            school_class=self.school_class, name="A", class_teacher=self.teacher
        )
        self.student = Student.objects.create(
            admission_no="A001",
            first_name="Aarav",
            date_of_birth=date(2019, 1, 1),
            gender=Student.Gender.MALE,
            address="X",
            father_name="Father",
            guardian_phone="9999999999",
            section=self.section,
            session=self.session,
            admission_date=date(2026, 4, 1),
            status=Student.Status.ACTIVE,
            portal_user=self.student_user,
        )
        self.other_student = Student.objects.create(
            admission_no="A002",
            first_name="Diya",
            date_of_birth=date(2019, 2, 1),
            gender=Student.Gender.FEMALE,
            address="Y",
            father_name="Other Father",
            guardian_phone="8888888888",
            section=self.section,
            session=self.session,
            admission_date=date(2026, 4, 1),
            status=Student.Status.ACTIVE,
        )
        ParentStudentAccess.objects.create(parent=self.parent, student=self.student)

    def test_teacher_can_open_assigned_student(self):
        self.client.login(username="teacher", password="pass12345")
        response = self.client.get(reverse("student_detail", args=[self.student.pk]))
        self.assertEqual(response.status_code, 200)

    def test_other_teacher_cannot_open_student(self):
        self.client.login(username="other", password="pass12345")
        response = self.client.get(reverse("student_detail", args=[self.student.pk]))
        self.assertEqual(response.status_code, 404)

    def test_parent_can_only_open_linked_student(self):
        self.client.login(username="parent", password="pass12345")
        self.assertEqual(self.client.get(reverse("student_detail", args=[self.student.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("student_detail", args=[self.other_student.pk])).status_code, 404)

    def test_student_can_only_open_own_record(self):
        self.client.login(username="student", password="pass12345")
        self.assertEqual(self.client.get(reverse("student_detail", args=[self.student.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("student_detail", args=[self.other_student.pk])).status_code, 404)

    def test_management_can_open_fee_page(self):
        self.client.login(username="principal", password="pass12345")
        self.assertEqual(self.client.get(reverse("fee_list")).status_code, 200)

    def test_id_card_is_pdf(self):
        self.client.login(username="principal", password="pass12345")
        response = self.client.get(reverse("id_card_pdf", args=[self.student.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_principal_can_generate_parent_and_student_accounts(self):
        # Remove the pre-linked accounts and verify the UI can create fresh credentials.
        ParentStudentAccess.objects.all().delete()
        self.student.portal_user = None
        self.student.save(update_fields=["portal_user"])
        self.client.login(username="principal", password="pass12345")
        response = self.client.post(
            reverse("student_portal_accounts", args=[self.student.pk]),
            {"action": "create_student"},
        )
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertIsNotNone(self.student.portal_user_id)
        response = self.client.post(
            reverse("student_portal_accounts", args=[self.student.pk]),
            {"action": "create_parent"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.student.parent_links.exists())

    @override_settings(MSG91_AUTH_KEY="", MSG91_TEMPLATE_ID="")
    def test_sms_without_keys_is_logged_in_demo_mode(self):
        self.client.login(username="principal", password="pass12345")
        response = self.client.post(
            reverse("communications"),
            {
                "channel": "SMS",
                "audience": "STUDENT",
                "student": self.student.pk,
                "section": "",
                "template_name": "",
                "message": "School notice",
            },
        )
        self.assertRedirects(response, reverse("communications"))
        log = CommunicationLog.objects.latest("created_at")
        self.assertEqual(log.status, CommunicationLog.Status.DEMO)

    def test_pwa_manifest_and_service_worker_do_not_cache_private_pages(self):
        manifest = self.client.get(reverse("pwa_manifest"))
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest["Content-Type"], "application/manifest+json")
        self.assertEqual(manifest.json()["display"], "standalone")
        worker = self.client.get(reverse("service_worker"))
        self.assertEqual(worker.status_code, 200)
        self.assertIn(b"never persists authenticated", worker.content)
        self.assertNotIn(b"caches.open", worker.content)


    def test_public_registration_records_guardian_consent(self):
        session = self.client.session
        session["captcha_answer"] = 7
        session.save()
        response = self.client.post(
            reverse("public_register"),
            {
                "first_name": "Kabir",
                "last_name": "Kumar",
                "date_of_birth": "2019-03-05",
                "gender": Student.Gender.MALE,
                "blood_group": "",
                "aadhaar_no": "",
                "email": "",
                "phone": "",
                "address": "Demo address",
                "city": "Unnao",
                "state": "Uttar Pradesh",
                "pincode": "209801",
                "father_name": "Demo Guardian",
                "mother_name": "",
                "guardian_name": "Demo Guardian",
                "guardian_phone": "9876543200",
                "guardian_email": "guardian@example.com",
                "previous_school": "",
                "section": self.section.pk,
                "session": self.session.pk,
                "admission_date": "2026-07-19",
                "consent_confirmation": "on",
                "captcha_answer": "7",
            },
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(response.status_code, 200)
        registered = Student.objects.get(first_name="Kabir")
        self.assertTrue(registered.privacy_consent)
        self.assertIsNotNone(registered.privacy_consent_at)
        self.assertEqual(registered.privacy_consent_ip, "127.0.0.1")
        self.assertEqual(registered.status, Student.Status.PENDING)

    def test_staff_can_only_download_own_payslip(self):
        mine = PayrollRecord.objects.create(
            staff=self.teacher,
            month=date(2026, 7, 1),
            basic=10000,
            hra=1000,
            allowances=500,
            deductions=200,
            gross=11500,
            net=11300,
            generated_by=self.principal,
        )
        other = PayrollRecord.objects.create(
            staff=self.other_teacher,
            month=date(2026, 7, 1),
            basic=9000,
            hra=900,
            allowances=300,
            deductions=100,
            gross=10200,
            net=10100,
            generated_by=self.principal,
        )
        self.client.login(username="teacher", password="pass12345")
        self.assertEqual(self.client.get(reverse("payslip_pdf", args=[mine.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("payslip_pdf", args=[other.pk])).status_code, 404)
