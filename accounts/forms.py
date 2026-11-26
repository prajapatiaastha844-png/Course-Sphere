from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db.models import Q

from courses.forms import AdminCourseForm, AdminOrderCreateForm, AdminOrderForm

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


class AdminUserForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
        )

    def clean_username(self):
        username = self.cleaned_data["username"]
        conflicts = get_user_model().objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        )
        if self.instance.pk:
            conflicts = conflicts.exclude(pk=self.instance.pk)
        if conflicts.exists():
            raise ValidationError(
                "An account with this username or email address already exists."
            )
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if email:
            user_conflicts = get_user_model().objects.filter(
                Q(username__iexact=email) | Q(email__iexact=email)
            )
            if self.instance.pk:
                user_conflicts = user_conflicts.exclude(pk=self.instance.pk)
            if user_conflicts.exists():
                raise ValidationError(
                    "An account with this email address already exists."
                )

        linked_profile_exists = any(
            profile_model.objects.filter(user=self.instance).exists()
            for profile_model in (Admin, Student, Instructor)
        )
        if linked_profile_exists and not email:
            raise ValidationError(
                "Email is required for accounts with a profile."
            )
        if email:
            for profile_model in (Admin, Student, Instructor):
                if profile_model.objects.filter(
                    email__iexact=email
                ).exclude(user=self.instance).exists():
                    raise ValidationError(
                        "An account with this email address already exists."
                    )
        return email


class AdminUserCreateForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    is_staff = forms.BooleanField(required=False)
    is_active = forms.BooleanField(required=False, initial=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_active",
        )

    def clean_username(self):
        username = self.cleaned_data["username"]
        user_model = get_user_model()
        if user_model.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        ).exists() or any(
            profile_model.objects.filter(email__iexact=username).exists()
            for profile_model in (Admin, Student, Instructor)
        ):
            raise ValidationError(
                "An account with this username or email address already exists."
            )
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
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
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.is_staff = self.cleaned_data["is_staff"]
        user.is_active = self.cleaned_data["is_active"]
        if commit:
            user.save()
        return user


class PersonAdminForm(forms.ModelForm):
    def clean_email(self):
        email = self.cleaned_data["email"]
        for profile_model in (Admin, Student, Instructor):
            profiles = profile_model.objects.filter(email__iexact=email)
            if isinstance(self.instance, profile_model) and self.instance.pk:
                profiles = profiles.exclude(pk=self.instance.pk)
            if profiles.exists():
                raise ValidationError(
                    "An account with this email address already exists."
                )

        user_model = get_user_model()
        users = user_model.objects.filter(
            Q(username__iexact=email) | Q(email__iexact=email)
        )
        if self.instance.user_id:
            users = users.exclude(pk=self.instance.user_id)
        if users.exists():
            raise ValidationError(
                "An account with this email address already exists."
            )
        return email


class AdminStudentForm(PersonAdminForm):
    class Meta:
        model = Student
        fields = ("name", "email", "student_id")


class AdminInstructorForm(PersonAdminForm):
    class Meta:
        model = Instructor
        fields = ("name", "email", "employee_id", "specialization")


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
