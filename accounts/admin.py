from django.contrib import admin

from .models import Admin, Instructor, PasswordResetOTP, Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "student_id", "enrollment_date")
    search_fields = ("name", "email", "student_id")


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "employee_id", "specialization")
    search_fields = ("name", "email", "employee_id", "specialization")


@admin.register(Admin)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "email")
    search_fields = ("name", "email")


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "attempts", "consumed_at")
    list_filter = ("attempts", "created_at")
    search_fields = ("user__username", "user__email")
