from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

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
    StaffProfile,
    Student,
    StudentTransportAssignment,
    Subject,
    TeacherAssignment,
    TimetableEntry,
    TransportRoute,
    User,
    Vehicle,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("School role", {"fields": ("role", "phone", "must_change_password")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("School role", {"fields": ("role", "phone")}),)
    list_display = ("username", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("admission_no", "full_name", "section", "roll_number", "status", "portal_user")
    search_fields = ("admission_no", "first_name", "last_name", "guardian_phone")
    list_filter = ("status", "section__school_class", "section")


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = ("channel", "recipient_phone", "status", "sent_by", "created_at")
    list_filter = ("channel", "status")
    search_fields = ("recipient_phone", "recipient_name", "body")
    readonly_fields = ("created_at", "sent_at", "provider_response")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "model_name", "object_id")
    list_filter = ("action", "model_name")
    search_fields = ("description", "actor__username")
    readonly_fields = ("actor", "action", "model_name", "object_id", "description", "ip_address", "created_at")


for model in [
    SchoolProfile,
    AcademicSession,
    SchoolClass,
    Section,
    Subject,
    TeacherAssignment,
    ParentStudentAccess,
    Exam,
    Mark,
    Attendance,
    FeeStructure,
    FeePayment,
    PaymentOrder,
    TimetableEntry,
    Vehicle,
    TransportRoute,
    RouteStop,
    StudentTransportAssignment,
    StaffProfile,
    SalaryStructure,
    PayrollRecord,
]:
    admin.site.register(model)
