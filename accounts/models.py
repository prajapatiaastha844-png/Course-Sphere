from django.conf import settings
from django.db import models


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_otps",
    )
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)


class Person(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_profile",
    )
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Admin(Person):
    pass


class Student(Person):
    student_id = models.CharField(max_length=50, unique=True)
    enrollment_date = models.DateField(auto_now_add=True)


class Instructor(Person):
    employee_id = models.CharField(max_length=50, unique=True)
    specialization = models.CharField(max_length=100)
