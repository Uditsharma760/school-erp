from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        DIRECTOR = "DIRECTOR", "Director"
        PRINCIPAL = "PRINCIPAL", "Principal"
        TEACHER = "TEACHER", "Teacher"
        ACCOUNTANT = "ACCOUNTANT", "Accountant"
        TRANSPORT = "TRANSPORT", "Transport Manager"
        PARENT = "PARENT", "Parent / Guardian"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TEACHER)
    phone = models.CharField(max_length=20, blank=True)
    must_change_password = models.BooleanField(default=True)

    @property
    def is_management(self):
        return self.is_superuser or self.role in {self.Role.DIRECTOR, self.Role.PRINCIPAL}

    @property
    def is_school_staff(self):
        return self.is_superuser or self.role in {
            self.Role.DIRECTOR,
            self.Role.PRINCIPAL,
            self.Role.TEACHER,
            self.Role.ACCOUNTANT,
            self.Role.TRANSPORT,
        }

    @property
    def portal_home_name(self):
        return {
            self.Role.DIRECTOR: "management_dashboard",
            self.Role.PRINCIPAL: "management_dashboard",
            self.Role.TEACHER: "teacher_dashboard",
            self.Role.ACCOUNTANT: "management_dashboard",
            self.Role.TRANSPORT: "transport_dashboard",
            self.Role.PARENT: "parent_dashboard",
            self.Role.STUDENT: "student_dashboard",
        }.get(self.role, "dashboard")


class SchoolProfile(models.Model):
    school_name = models.CharField(max_length=200, default="My School")
    tagline = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    affiliation_no = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="school/", blank=True, null=True)

    def __str__(self):
        return self.school_name


class AcademicSession(models.Model):
    name = models.CharField(max_length=20, unique=True, help_text="Example: 2026-27")
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_active:
            AcademicSession.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    name = models.CharField(max_length=30, unique=True)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "School classes"

    def __str__(self):
        return self.name


class Section(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=10)
    capacity = models.PositiveIntegerField(default=40)
    class_teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="class_teacher_sections",
        limit_choices_to={"role": User.Role.TEACHER},
    )

    class Meta:
        ordering = ["school_class__order", "name"]
        constraints = [models.UniqueConstraint(fields=["school_class", "name"], name="unique_class_section")]

    def __str__(self):
        return f"{self.school_class.name} - {self.name}"

    @property
    def active_students_count(self):
        return self.students.filter(status=Student.Status.ACTIVE).count()


class Subject(models.Model):
    name = models.CharField(max_length=80)
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class TeacherAssignment(models.Model):
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="teaching_assignments",
        limit_choices_to={"role": User.Role.TEACHER},
    )
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="teacher_assignments")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="teacher_assignments")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["teacher", "section", "subject"], name="unique_teacher_assignment")]

    def __str__(self):
        return f"{self.teacher.get_full_name() or self.teacher.username} | {self.section} | {self.subject.name}"


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending approval"
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    admission_no = models.CharField(max_length=30, unique=True)
    roll_number = models.PositiveIntegerField(blank=True, null=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=Gender.choices)
    blood_group = models.CharField(max_length=10, blank=True)
    aadhaar_no = models.CharField(max_length=12, blank=True)
    photo = models.ImageField(upload_to="students/", blank=True, null=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField()
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    pincode = models.CharField(max_length=10, blank=True)

    father_name = models.CharField(max_length=120)
    mother_name = models.CharField(max_length=120, blank=True)
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_phone = models.CharField(max_length=20)
    guardian_email = models.EmailField(blank=True)
    previous_school = models.CharField(max_length=200, blank=True)

    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="students")
    session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT, related_name="students")
    admission_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    privacy_consent = models.BooleanField(default=False)
    privacy_consent_at = models.DateTimeField(blank=True, null=True)
    privacy_consent_ip = models.GenericIPAddressField(blank=True, null=True)
    portal_user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_record",
        limit_choices_to={"role": User.Role.STUDENT},
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_students")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section__school_class__order", "section__name", "roll_number", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "roll_number", "session"],
                name="unique_roll_in_section_session",
                condition=models.Q(roll_number__isnull=False),
            )
        ]

    def __str__(self):
        return f"{self.admission_no} - {self.full_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def attendance_percentage(self):
        total = self.attendance_records.count()
        if not total:
            return 0
        present = self.attendance_records.filter(status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]).count()
        return round((present / total) * 100, 1)

    @property
    def total_fee(self):
        value = FeeStructure.objects.filter(session=self.session, school_class=self.section.school_class).aggregate(v=Sum("amount"))["v"]
        return value or Decimal("0.00")

    @property
    def fee_paid(self):
        return self.fee_payments.aggregate(v=Sum("amount"))["v"] or Decimal("0.00")

    @property
    def fee_due(self):
        return max(self.total_fee - self.fee_paid, Decimal("0.00"))


class ParentStudentAccess(models.Model):
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parent_links",
        limit_choices_to={"role": User.Role.PARENT},
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="parent_links")
    relationship = models.CharField(max_length=30, default="Guardian")
    is_primary = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["parent", "student"], name="unique_parent_student_access")]

    def __str__(self):
        return f"{self.parent.get_full_name() or self.parent.username} → {self.student.full_name}"


class Exam(models.Model):
    name = models.CharField(max_length=80)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name="exams")
    start_date = models.DateField()
    published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]
        constraints = [models.UniqueConstraint(fields=["name", "session"], name="unique_exam_session")]

    def __str__(self):
        return f"{self.name} ({self.session.name})"


class Mark(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="marks")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="marks")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="marks")
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100, validators=[MinValueValidator(1)])
    obtained_marks = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    grade = models.CharField(max_length=5, blank=True)
    remarks = models.CharField(max_length=200, blank=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="entered_marks")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "exam", "subject"], name="unique_student_exam_subject")]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.obtained_marks is not None and self.max_marks is not None and self.obtained_marks > self.max_marks:
            raise ValidationError("Obtained marks cannot be greater than maximum marks.")

    def save(self, *args, **kwargs):
        if self.max_marks:
            percent = float(self.obtained_marks / self.max_marks * 100)
            self.grade = (
                "A+" if percent >= 90 else "A" if percent >= 80 else "B+" if percent >= 70 else
                "B" if percent >= 60 else "C" if percent >= 50 else "D" if percent >= 33 else "F"
            )
        self.full_clean()
        super().save(*args, **kwargs)


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "P", "Present"
        ABSENT = "A", "Absent"
        LATE = "L", "Late"
        LEAVE = "LV", "Leave"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=2, choices=Status.choices, default=Status.PRESENT)
    remarks = models.CharField(max_length=160, blank=True)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="marked_attendance")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["student", "date"], name="unique_student_attendance_date")]

    def __str__(self):
        return f"{self.student} - {self.date} - {self.get_status_display()}"


class FeeStructure(models.Model):
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name="fee_structures")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="fee_structures")
    name = models.CharField(max_length=100, help_text="Tuition, Transport, Annual fee, etc.")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "school_class", "name"], name="unique_fee_head")]

    def __str__(self):
        return f"{self.school_class} - {self.name}: ₹{self.amount}"


class FeePayment(models.Model):
    class Mode(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"
        BANK = "BANK", "Bank transfer"
        CARD = "CARD", "Card"
        CHEQUE = "CHEQUE", "Cheque"
        ONLINE = "ONLINE", "Online gateway"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="fee_payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    payment_date = models.DateField()
    mode = models.CharField(max_length=20, choices=Mode.choices)
    receipt_no = models.CharField(max_length=40, unique=True)
    reference_no = models.CharField(max_length=100, blank=True)
    gateway_payment_id = models.CharField(max_length=100, blank=True, unique=True, null=True)
    notes = models.CharField(max_length=200, blank=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_fee_payments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"{self.receipt_no} - {self.student.full_name} - ₹{self.amount}"


class PaymentOrder(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        ATTEMPTED = "ATTEMPTED", "Attempted"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="payment_orders")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3, default="INR")
    provider = models.CharField(max_length=30, default="RAZORPAY")
    gateway_order_id = models.CharField(max_length=100, unique=True)
    gateway_payment_id = models.CharField(max_length=100, blank=True)
    gateway_signature = models.CharField(max_length=200, blank=True)
    receipt_no = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_payment_orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.gateway_order_id} - {self.student.full_name} - ₹{self.amount}"


class TimetableEntry(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 1, "Monday"
        TUESDAY = 2, "Tuesday"
        WEDNESDAY = 3, "Wednesday"
        THURSDAY = 4, "Thursday"
        FRIDAY = 5, "Friday"
        SATURDAY = 6, "Saturday"
        SUNDAY = 7, "Sunday"

    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name="timetable_entries")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="timetable_entries")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    period_name = models.CharField(max_length=40, default="Period")
    start_time = models.TimeField()
    end_time = models.TimeField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="timetable_entries")
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_entries", limit_choices_to={"role": User.Role.TEACHER})
    room = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [models.UniqueConstraint(fields=["session", "section", "weekday", "start_time"], name="unique_timetable_slot")]

    def __str__(self):
        return f"{self.section} - {self.get_weekday_display()} {self.start_time} - {self.subject.name}"


class Vehicle(models.Model):
    registration_no = models.CharField(max_length=30, unique=True)
    vehicle_type = models.CharField(max_length=40, default="School Bus")
    capacity = models.PositiveIntegerField(default=40)
    driver_name = models.CharField(max_length=100)
    driver_phone = models.CharField(max_length=20)
    attendant_name = models.CharField(max_length=100, blank=True)
    attendant_phone = models.CharField(max_length=20, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.registration_no} ({self.driver_name})"


class TransportRoute(models.Model):
    name = models.CharField(max_length=100, unique=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name="routes")
    monthly_fee = models.DecimalField(max_digits=9, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class RouteStop(models.Model):
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE, related_name="stops")
    name = models.CharField(max_length=100)
    pickup_time = models.TimeField(blank=True, null=True)
    drop_time = models.TimeField(blank=True, null=True)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["route", "order", "name"]
        constraints = [models.UniqueConstraint(fields=["route", "name"], name="unique_route_stop")]

    def __str__(self):
        return f"{self.route.name} - {self.name}"


class StudentTransportAssignment(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="transport_assignment")
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name="student_assignments")
    stop = models.ForeignKey(RouteStop, on_delete=models.PROTECT, related_name="student_assignments")
    start_date = models.DateField(default=timezone.localdate)
    monthly_fee_override = models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.student.full_name} - {self.route.name} / {self.stop.name}"

    @property
    def monthly_fee(self):
        return self.monthly_fee_override if self.monthly_fee_override is not None else self.route.monthly_fee


class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    designation = models.CharField(max_length=100, blank=True)
    joining_date = models.DateField(blank=True, null=True)
    bank_account = models.CharField(max_length=40, blank=True)
    ifsc = models.CharField(max_length=20, blank=True)
    pan = models.CharField(max_length=20, blank=True)
    uan = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class SalaryStructure(models.Model):
    staff = models.OneToOneField(User, on_delete=models.CASCADE, related_name="salary_structure", limit_choices_to={"role__in": [User.Role.TEACHER, User.Role.ACCOUNTANT, User.Role.TRANSPORT, User.Role.PRINCIPAL]})
    basic = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    hra = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    effective_from = models.DateField(default=timezone.localdate)

    @property
    def gross(self):
        return self.basic + self.hra + self.allowances

    @property
    def net(self):
        return max(self.gross - self.deductions, Decimal("0.00"))

    def __str__(self):
        return f"{self.staff.get_full_name() or self.staff.username} - ₹{self.net}"


class PayrollRecord(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PAID = "PAID", "Paid"

    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payroll_records")
    month = models.DateField(help_text="Use the first day of the salary month")
    basic = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gross = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    paid_date = models.DateField(blank=True, null=True)
    payment_reference = models.CharField(max_length=80, blank=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="generated_payroll")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-month", "staff__first_name"]
        constraints = [models.UniqueConstraint(fields=["staff", "month"], name="unique_staff_payroll_month")]

    def __str__(self):
        return f"{self.staff.get_full_name() or self.staff.username} - {self.month:%B %Y}"


class CommunicationLog(models.Model):
    class Channel(models.TextChoices):
        SMS = "SMS", "SMS"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        DEMO = "DEMO", "Demo / logged only"

    channel = models.CharField(max_length=20, choices=Channel.choices)
    audience = models.CharField(max_length=100, blank=True)
    recipient_name = models.CharField(max_length=150, blank=True)
    recipient_phone = models.CharField(max_length=20)
    template_name = models.CharField(max_length=120, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_message_id = models.CharField(max_length=150, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_communications")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.channel} → {self.recipient_phone} ({self.status})"


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=80)
    model_name = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.actor or 'System'}"
