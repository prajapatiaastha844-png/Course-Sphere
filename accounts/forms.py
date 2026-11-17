from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import Admin, Instructor, Student


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Email address or username",
        widget=forms.TextInput(attrs={"autofocus": True}),
    )


class AccountRegistrationForm(UserCreationForm):
    username = forms.EmailField(label="Email address")
    name = forms.CharField(max_length=150)

    class Meta(UserCreationForm.Meta):
        fields = ("username",)

    def clean_username(self):
        email = super().clean_username()
        user_model = get_user_model()
        if user_model.objects.filter(
            Q(username__iexact=email) | Q(email__iexact=email)
        ).exists() or any(
            profile_model.objects.filter(email__iexact=email).exists()
            for profile_model in (Admin, Student, Instructor)
        ):
            raise ValidationError("An account with this email address already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data["username"]
        if commit:
            user.save()
        return user


class StudentRegistrationForm(AccountRegistrationForm):
    student_id = forms.CharField(max_length=50)

    def clean_student_id(self):
        student_id = self.cleaned_data["student_id"]
        if Student.objects.filter(student_id__iexact=student_id).exists():
            raise ValidationError("A student with this ID already exists.")
        return student_id


class InstructorRegistrationForm(AccountRegistrationForm):
    employee_id = forms.CharField(max_length=50)
    specialization = forms.CharField(max_length=100)

    def clean_employee_id(self):
        employee_id = self.cleaned_data["employee_id"]
        if Instructor.objects.filter(employee_id__iexact=employee_id).exists():
            raise ValidationError("An instructor with this ID already exists.")
        return employee_id


class AdminRegistrationForm(forms.ModelForm):
    class Meta:
        model = Admin
        fields = ("name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if Admin.objects.filter(email__iexact=email).exists():
            raise ValidationError("An admin profile with this email already exists.")
        return email


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField()


class OTPPasswordResetForm(forms.Form):
    email = forms.EmailField()
    otp = forms.RegexField(
        regex=r"^\d{6}$",
        label="One-time code",
        error_messages={"invalid": "Enter the 6-digit code from your email."},
    )
    new_password1 = forms.CharField(
        label="New password",
        strip=False,
        widget=forms.PasswordInput,
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        strip=False,
        widget=forms.PasswordInput,
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            self.add_error("new_password2", "The passwords do not match.")
        return cleaned_data
