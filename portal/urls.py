from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path(
        "password/forgot/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password/forgot/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("management/login/", views.management_login, name="management_login"),
    path("teacher/login/", views.teacher_login, name="teacher_login"),
    path("parent/login/", views.parent_login, name="parent_login"),
    path("student/login/", views.student_login, name="student_login"),
    path("logout/", views.logout_view, name="logout"),
    path("password/change/", views.change_password, name="change_password"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("management/", views.management_dashboard, name="management_dashboard"),
    path("teacher/", views.teacher_dashboard, name="teacher_dashboard"),
    path("parent/", views.parent_dashboard, name="parent_dashboard"),
    path("student/", views.student_dashboard, name="student_dashboard"),
    path("transport/dashboard/", views.transport_dashboard, name="transport_dashboard"),

    path("register/", views.public_register, name="public_register"),
    path("results/", views.public_results, name="public_results"),
    path("results/<int:exam_id>/", views.public_result_detail, name="public_result_detail"),
    path("results/<int:exam_id>/pdf/", views.public_result_pdf, name="public_result_pdf"),
    path("verify/student/<str:admission_no>/", views.verify_student, name="verify_student"),

    path("students/", views.student_list, name="student_list"),
    path("students/add/", views.student_create, name="student_create"),
    path("students/<int:pk>/", views.student_detail, name="student_detail"),
    path("students/<int:pk>/edit/", views.student_edit, name="student_edit"),
    path("students/<int:pk>/approve/", views.student_approve, name="student_approve"),
    path("students/<int:student_id>/portal-accounts/", views.student_portal_accounts, name="student_portal_accounts"),
    path("students/<int:student_id>/id-card.pdf", views.id_card_pdf, name="id_card_pdf"),

    path("classes/", views.class_list, name="class_list"),
    path("sections/<int:pk>/", views.section_detail, name="section_detail"),
    path("sections/<int:section_id>/attendance/", views.attendance_mark, name="attendance_mark"),

    path("marks/", views.marks_hub, name="marks_hub"),
    path("marks/<int:exam_id>/<int:section_id>/<int:subject_id>/", views.marks_entry, name="marks_entry"),
    path("students/<int:student_id>/results/<int:exam_id>/", views.result_view, name="result_view"),
    path("students/<int:student_id>/results/<int:exam_id>/pdf/", views.result_pdf, name="result_pdf"),

    path("staff/", views.staff_list, name="staff_list"),
    path("staff/add/", views.staff_create, name="staff_create"),
    path("staff/<int:pk>/toggle/", views.staff_toggle, name="staff_toggle"),
    path("staff/<int:pk>/reset-password/", views.staff_reset_password, name="staff_reset_password"),
    path(
    "staff/<int:pk>/delete/",
    views.staff_delete,
    name="staff_delete",
    ),

    path("fees/", views.fee_list, name="fee_list"),
    path("fees/payment/add/", views.fee_payment_create, name="fee_payment_create"),
    path("fees/payment/add/<int:student_id>/", views.fee_payment_create, name="fee_payment_for_student"),
    path("fees/payment/<int:pk>/edit/", views.fee_payment_edit, name="fee_payment_edit"),
    path("fees/payment/<int:pk>/delete/", views.fee_payment_delete, name="fee_payment_delete"),
    path("fees/pay-online/", views.online_fee, name="online_fee"),
    path("fees/pay-online/<int:student_id>/", views.online_fee, name="online_fee_student"),
    path("fees/payment/verify/", views.payment_verify, name="payment_verify"),
    path("webhooks/razorpay/", views.razorpay_webhook, name="razorpay_webhook"),

    path("timetable/", views.timetable, name="timetable"),
    path("timetable/<int:pk>/delete/", views.timetable_delete, name="timetable_delete"),
    path("transport/", views.transport_center, name="transport_center"),
    path("payroll/", views.payroll_dashboard, name="payroll_dashboard"),
    path("payroll/<int:pk>/mark-paid/", views.payroll_mark_paid, name="payroll_mark_paid"),
    path("payroll/<int:pk>/payslip.pdf", views.payslip_pdf, name="payslip_pdf"),
    path("communications/", views.communications, name="communications"),
    path("audit-logs/", views.audit_logs, name="audit_logs"),

    path(
        "setup/<str:item_type>/<int:pk>/edit/",
        views.setup_item_edit,
        name="setup_item_edit",
    ),
    path(
        "setup/<str:item_type>/<int:pk>/delete/",
        views.setup_item_delete,
        name="setup_item_delete",
    ),
    path("setup/", views.setup_center, name="setup_center"),
    path("manifest.webmanifest", views.pwa_manifest, name="pwa_manifest"),
    path("service-worker.js", views.service_worker, name="service_worker"),
]
