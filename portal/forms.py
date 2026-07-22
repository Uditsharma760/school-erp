from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.utils import timezone

from .models import (
    AcademicSession,
    Exam,
    FeePayment,
    FeeStructure,
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


class StyledFormMixin:
    def apply_styles(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "User ID", "autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class StudentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Student
        exclude = ("portal_user", "created_by", "created_at", "updated_at", "privacy_consent", "privacy_consent_at", "privacy_consent_ip")
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "admission_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields["aadhaar_no"].help_text = "Optional. Store only when the school has a lawful need and proper consent."

    def clean_aadhaar_no(self):
        value = self.cleaned_data.get("aadhaar_no", "").strip()
        if value and (not value.isdigit() or len(value) != 12):
            raise forms.ValidationError("Aadhaar number must contain exactly 12 digits.")
        return value


class PublicStudentRegistrationForm(StudentForm):
    consent_confirmation = forms.BooleanField(
        label="I confirm that I am the parent/authorised guardian and consent to this information being used for admission and school administration."
    )

    class Meta(StudentForm.Meta):
        exclude = (
            "admission_no",
            "roll_number",
            "status",
            "portal_user",
            "created_by",
            "created_at",
            "updated_at",
            "privacy_consent",
            "privacy_consent_at",
            "privacy_consent_ip",
        )


class StaffForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields["role"].choices = [
            (User.Role.TEACHER, "Teacher"),
            (User.Role.ACCOUNTANT, "Accountant"),
            (User.Role.TRANSPORT, "Transport Manager"),
            (User.Role.PRINCIPAL, "Principal"),
            (User.Role.DIRECTOR, "Director"),
        ]


class CustomPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class FeePaymentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = ("student", "amount", "payment_date", "mode", "receipt_no", "reference_no", "notes")
        widgets = {"payment_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields["student"].queryset = Student.objects.filter(status=Student.Status.ACTIVE).select_related("section__school_class")


class OnlineFeeForm(StyledFormMixin, forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.none())
    amount = forms.DecimalField(min_value=1, max_digits=10, decimal_places=2)

    def __init__(self, *args, students=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields["student"].queryset = students if students is not None else Student.objects.none()

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        amount = cleaned.get("amount")
        if student and amount and amount > student.fee_due:
            self.add_error("amount", f"Amount cannot exceed current due ₹{student.fee_due}.")
        return cleaned


class ResultSearchForm(StyledFormMixin, forms.Form):
    admission_no = forms.CharField(label="Admission number")
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class SchoolProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SchoolProfile
        fields = "__all__"
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class SchoolClassForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class SectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Section
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class SubjectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Subject
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class AcademicSessionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AcademicSession
        fields = "__all__"
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class ExamForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Exam
        fields = "__all__"
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class FeeStructureForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class TeacherAssignmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TeacherAssignment
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields["teacher"].queryset = User.objects.filter(role=User.Role.TEACHER, is_active=True)


class TimetableEntryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = "__all__"
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields["teacher"].queryset = User.objects.filter(role=User.Role.TEACHER, is_active=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("start_time") and cleaned.get("end_time") and cleaned["end_time"] <= cleaned["start_time"]:
            self.add_error("end_time", "End time must be after start time.")
        return cleaned


class VehicleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class TransportRouteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TransportRoute
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class RouteStopForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RouteStop
        fields = "__all__"
        widgets = {
            "pickup_time": forms.TimeInput(attrs={"type": "time"}),
            "drop_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class StudentTransportAssignmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = StudentTransportAssignment
        fields = "__all__"
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields["student"].queryset = Student.objects.filter(status=Student.Status.ACTIVE)

    def clean(self):
        cleaned = super().clean()
        route, stop = cleaned.get("route"), cleaned.get("stop")
        if route and stop and stop.route_id != route.id:
            self.add_error("stop", "Selected stop does not belong to the selected route.")
        return cleaned


class SalaryStructureForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SalaryStructure
        fields = "__all__"
        widgets = {"effective_from": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields["staff"].queryset = User.objects.filter(
            role__in=[User.Role.TEACHER, User.Role.ACCOUNTANT, User.Role.TRANSPORT, User.Role.PRINCIPAL],
            is_active=True,
        )


class PayrollGenerateForm(StyledFormMixin, forms.Form):
    staff = forms.ModelChoiceField(queryset=User.objects.none())
    month = forms.CharField(widget=forms.TextInput(attrs={"type": "month"}), initial=timezone.localdate().strftime("%Y-%m"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["staff"].queryset = User.objects.filter(salary_structure__isnull=False, is_active=True).distinct()
        self.apply_styles()

    def clean_month(self):
        from datetime import date
        value = self.cleaned_data["month"]
        try:
            year, month = (int(part) for part in value.split("-", 1))
            return date(year, month, 1)
        except (ValueError, TypeError):
            raise forms.ValidationError("Select a valid salary month.")


class PayrollPaymentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PayrollRecord
        fields = ("paid_date", "payment_reference")
        widgets = {"paid_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class CommunicationForm(StyledFormMixin, forms.Form):
    class Audience:
        STUDENT = "STUDENT"
        SECTION = "SECTION"
        ALL = "ALL"
        STAFF = "STAFF"
        choices = ((STUDENT, "One student / guardian"), (SECTION, "All guardians in a section"), (ALL, "All active student guardians"), (STAFF, "All active staff"))

    channel = forms.ChoiceField(choices=(("SMS", "SMS"), ("WHATSAPP", "WhatsApp")))
    audience = forms.ChoiceField(choices=Audience.choices)
    student = forms.ModelChoiceField(queryset=Student.objects.filter(status=Student.Status.ACTIVE), required=False)
    section = forms.ModelChoiceField(queryset=Section.objects.all(), required=False)
    template_name = forms.CharField(required=False, help_text="WhatsApp approved template name. Leave blank to use the configured default.")
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), max_length=1000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

    def clean(self):
        cleaned = super().clean()
        audience = cleaned.get("audience")
        if audience == self.Audience.STUDENT and not cleaned.get("student"):
            self.add_error("student", "Select a student.")
        if audience == self.Audience.SECTION and not cleaned.get("section"):
            self.add_error("section", "Select a section.")
        return cleaned
