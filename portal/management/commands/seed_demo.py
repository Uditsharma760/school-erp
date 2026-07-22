from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from portal.models import (
    AcademicSession,
    Attendance,
    Exam,
    FeePayment,
    FeeStructure,
    Mark,
    ParentStudentAccess,
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


class Command(BaseCommand):
    help = "Create demo school ERP data"

    def ensure_user(self, username, password, **defaults):
        user, created = User.objects.get_or_create(username=username, defaults=defaults)
        if created:
            user.set_password(password)
            user.save()
        return user

    def handle(self, *args, **options):
        SchoolProfile.objects.get_or_create(
            pk=1,
            defaults={
                "school_name": "Sunrise Public School",
                "tagline": "Knowledge · Character · Excellence",
                "address": "Unnao, Uttar Pradesh, India",
                "phone": "+91 98765 43210",
                "email": "school@example.com",
            },
        )
        session, _ = AcademicSession.objects.get_or_create(
            name="2026-27",
            defaults={"start_date": date(2026, 4, 1), "end_date": date(2027, 3, 31), "is_active": True},
        )
        if not session.is_active:
            session.is_active = True
            session.save()

        director = self.ensure_user("director", "Director@123", first_name="Demo", last_name="Director", email="director@example.com", role=User.Role.DIRECTOR, must_change_password=False)
        principal = self.ensure_user("principal", "Principal@123", first_name="Demo", last_name="Principal", email="principal@example.com", role=User.Role.PRINCIPAL, must_change_password=False)
        teacher = self.ensure_user("teacher", "Teacher@123", first_name="Anita", last_name="Sharma", email="teacher@example.com", phone="9876500001", role=User.Role.TEACHER, must_change_password=False)
        accountant = self.ensure_user("accountant", "Accountant@123", first_name="Demo", last_name="Accountant", email="accounts@example.com", phone="9876500002", role=User.Role.ACCOUNTANT, must_change_password=False)
        transport_manager = self.ensure_user("transport", "Transport@123", first_name="Demo", last_name="Transport", email="transport@example.com", phone="9876500003", role=User.Role.TRANSPORT, must_change_password=False)

        classes = []
        for order, name in enumerate(["Class 1", "Class 2", "Class 3"], 1):
            obj, _ = SchoolClass.objects.get_or_create(name=name, defaults={"order": order})
            classes.append(obj)
        sections = []
        for school_class in classes:
            for section_name in ["A", "B"]:
                section, _ = Section.objects.get_or_create(
                    school_class=school_class,
                    name=section_name,
                    defaults={"capacity": 40, "class_teacher": teacher if school_class == classes[0] and section_name == "A" else None},
                )
                sections.append(section)
        subjects = []
        for name, code in [("English", "ENG"), ("Mathematics", "MATH"), ("Science", "SCI"), ("Hindi", "HIN")]:
            subject, _ = Subject.objects.get_or_create(code=code, defaults={"name": name})
            subjects.append(subject)
        for subject in subjects:
            TeacherAssignment.objects.get_or_create(teacher=teacher, section=sections[0], subject=subject)
        exam, _ = Exam.objects.get_or_create(name="Unit Test 1", session=session, defaults={"start_date": date(2026, 7, 10), "published": True})
        FeeStructure.objects.get_or_create(session=session, school_class=classes[0], name="Annual & Tuition Fee", defaults={"amount": Decimal("24000")})

        demo_students = [
            ("SPS26001", 1, "Aarav", "Verma", "Rajesh Verma", "9876543210", "M"),
            ("SPS26002", 2, "Ananya", "Singh", "Vikas Singh", "9876543211", "F"),
            ("SPS26003", 3, "Vivaan", "Mishra", "Suresh Mishra", "9876543212", "M"),
            ("SPS26004", 4, "Diya", "Gupta", "Manoj Gupta", "9876543213", "F"),
        ]
        students = []
        for admission_no, roll, first, last, father, phone, gender in demo_students:
            student, _ = Student.objects.get_or_create(
                admission_no=admission_no,
                defaults={
                    "roll_number": roll,
                    "first_name": first,
                    "last_name": last,
                    "date_of_birth": date(2019, 1, min(roll + 4, 28)),
                    "gender": gender,
                    "address": "Demo Address, Unnao",
                    "city": "Unnao",
                    "state": "Uttar Pradesh",
                    "pincode": "209801",
                    "father_name": father,
                    "mother_name": "Demo Mother",
                    "guardian_name": father,
                    "guardian_phone": phone,
                    "section": sections[0],
                    "session": session,
                    "admission_date": date(2026, 4, 1),
                    "status": Student.Status.ACTIVE,
                    "created_by": principal,
                },
            )
            students.append(student)

        student_user = self.ensure_user("studentdemo", "Student@123", first_name=students[0].first_name, last_name=students[0].last_name, role=User.Role.STUDENT, must_change_password=False)
        if students[0].portal_user_id != student_user.id:
            students[0].portal_user = student_user
            students[0].save(update_fields=["portal_user"])
        parent_user = self.ensure_user("parentdemo", "Parent@123", first_name="Rajesh", last_name="Verma", phone=students[0].guardian_phone, role=User.Role.PARENT, must_change_password=False)
        ParentStudentAccess.objects.get_or_create(parent=parent_user, student=students[0], defaults={"relationship": "Father", "is_primary": True})

        for student_index, student in enumerate(students):
            for subject_index, subject in enumerate(subjects):
                Mark.objects.get_or_create(
                    student=student,
                    exam=exam,
                    subject=subject,
                    defaults={"max_marks": 100, "obtained_marks": Decimal(str(72 + student_index * 3 + subject_index * 2)), "entered_by": teacher},
                )
            for days_ago in range(12):
                day = timezone.localdate() - timedelta(days=days_ago)
                if day.weekday() < 6:
                    Attendance.objects.get_or_create(
                        student=student,
                        date=day,
                        defaults={"status": Attendance.Status.ABSENT if (student_index + days_ago) % 9 == 0 else Attendance.Status.PRESENT, "marked_by": teacher},
                    )
        FeePayment.objects.get_or_create(
            receipt_no="RCPT-DEMO-001",
            defaults={"student": students[0], "amount": Decimal("12000"), "payment_date": date(2026, 5, 1), "mode": FeePayment.Mode.UPI, "received_by": principal},
        )

        timetable_slots = [
            (1, "Period 1", time(8, 30), time(9, 10), subjects[0]),
            (1, "Period 2", time(9, 10), time(9, 50), subjects[1]),
            (2, "Period 1", time(8, 30), time(9, 10), subjects[2]),
            (2, "Period 2", time(9, 10), time(9, 50), subjects[3]),
        ]
        for weekday, period, start, end, subject in timetable_slots:
            TimetableEntry.objects.get_or_create(session=session, section=sections[0], weekday=weekday, start_time=start, defaults={"period_name": period, "end_time": end, "subject": subject, "teacher": teacher, "room": "101"})

        vehicle, _ = Vehicle.objects.get_or_create(registration_no="UP35-AB-1234", defaults={"capacity": 40, "driver_name": "Ramesh Kumar", "driver_phone": "9876501111", "active": True})
        route, _ = TransportRoute.objects.get_or_create(name="City Route 1", defaults={"vehicle": vehicle, "monthly_fee": Decimal("1200"), "active": True})
        stop, _ = RouteStop.objects.get_or_create(route=route, name="Main Market", defaults={"pickup_time": time(7, 35), "drop_time": time(14, 40), "order": 1})
        StudentTransportAssignment.objects.get_or_create(student=students[0], defaults={"route": route, "stop": stop, "start_date": date(2026, 4, 1), "active": True})

        salary, _ = SalaryStructure.objects.get_or_create(staff=teacher, defaults={"basic": Decimal("25000"), "hra": Decimal("5000"), "allowances": Decimal("2500"), "deductions": Decimal("1500"), "effective_from": date(2026, 4, 1)})
        PayrollRecord.objects.get_or_create(staff=teacher, month=date(2026, 7, 1), defaults={"basic": salary.basic, "hra": salary.hra, "allowances": salary.allowances, "deductions": salary.deductions, "gross": salary.gross, "net": salary.net, "status": PayrollRecord.Status.DRAFT, "generated_by": principal})

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        for label, username, password in [
            ("Director", "director", "Director@123"),
            ("Principal", "principal", "Principal@123"),
            ("Teacher", "teacher", "Teacher@123"),
            ("Accountant", "accountant", "Accountant@123"),
            ("Transport", "transport", "Transport@123"),
            ("Parent", "parentdemo", "Parent@123"),
            ("Student", "studentdemo", "Student@123"),
        ]:
            self.stdout.write(f"{label}: {username} / {password}")
