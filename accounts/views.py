import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.crypto import salted_hmac
from django.utils import timezone

from .forms import (
    AdminRegistrationForm,
    ForgotPasswordForm,
    InstructorRegistrationForm,
    OTPPasswordResetForm,
    StudentRegistrationForm,
)
from .models import Admin, Instructor, PasswordResetOTP, Student


REGISTRATION_FORMS = {
    "student": (StudentRegistrationForm, Student),
    "instructor": (InstructorRegistrationForm, Instructor),
}
OTP_LIFETIME = timedelta(minutes=10)
OTP_RESEND_COOLDOWN = timedelta(minutes=1)
OTP_MAX_ATTEMPTS = 5
GENERIC_RESET_MESSAGE = (
    "If an account exists for that email, a password reset code has been sent."
)
INVALID_OTP_MESSAGE = "The code is invalid or expired. Request a new code and try again."


def _otp_digest(user, code):
    return salted_hmac(
        "accounts.password_reset_otp",
        f"{user.pk}:{code}",
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def register(request, role):
    if role == "admin":
        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(), reverse("accounts:login")
            )
        if not request.user.is_staff:
            raise PermissionDenied
        if Admin.objects.filter(user=request.user).exists():
            return redirect("accounts:dashboard")
        form_class = AdminRegistrationForm
        profile_model = Admin
    else:
        try:
            form_class, profile_model = REGISTRATION_FORMS[role]
        except KeyError as exc:
            raise Http404("Unknown account role.") from exc

    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if role == "admin":
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
        else:
            with transaction.atomic():
                user = form.save(commit=False)
                user.save()
                profile_fields = {
                    "user": user,
                    "name": form.cleaned_data["name"],
                    "email": form.cleaned_data["username"],
                }
                for field in ("student_id", "employee_id", "specialization"):
                    if field in form.cleaned_data:
                        profile_fields[field] = form.cleaned_data[field]
                profile_model.objects.create(**profile_fields)
        return redirect(
            "accounts:dashboard" if role == "admin" else "accounts:login"
        )

    return render(
        request,
        "accounts/register.html",
        {"form": form, "role": role.title()},
    )


@login_required(login_url="accounts:login")
def dashboard(request):
    profile = None
    role = None
    for profile_model, role_name in (
        (Admin, "Admin"),
        (Student, "Student"),
        (Instructor, "Instructor"),
    ):
        profile = profile_model.objects.filter(user=request.user).first()
        if profile is not None:
            role = role_name
            break
    return render(
        request,
        "accounts/dashboard.html",
        {"profile": profile, "role": role},
    )


def forgot_password(request):
    form = ForgotPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        users = get_user_model()._default_manager.filter(
            email__iexact=form.cleaned_data["email"],
            is_active=True,
        )
        if users.count() == 1:
            user = users.first()
            now = timezone.now()
            recently_requested = PasswordResetOTP.objects.filter(
                user=user,
                created_at__gte=now - OTP_RESEND_COOLDOWN,
            ).exists()
            if not recently_requested:
                code = f"{secrets.randbelow(1_000_000):06d}"
                with transaction.atomic():
                    PasswordResetOTP.objects.filter(
                        user=user,
                        consumed_at__isnull=True,
                    ).update(consumed_at=now)
                    PasswordResetOTP.objects.create(
                        user=user,
                        code_hash=_otp_digest(user, code),
                        expires_at=now + OTP_LIFETIME,
                    )
                    sent_count = send_mail(
                        subject="Your CourseSphere password reset code",
                        message=(
                            f"Your CourseSphere password reset code is: {code}\n"
                            "It expires in 10 minutes. If you did not request this, "
                            "you can ignore this email."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    if sent_count != 1:
                        raise RuntimeError("The password reset email was not sent.")

        return render(
            request,
            "accounts/forgot_password.html",
            {"form": ForgotPasswordForm(), "message": GENERIC_RESET_MESSAGE},
        )

    return render(request, "accounts/forgot_password.html", {"form": form})


def reset_password(request):
    form = OTPPasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        users = get_user_model()._default_manager.filter(
            email__iexact=form.cleaned_data["email"],
            is_active=True,
        )
        reset_complete = False
        if users.count() == 1:
            user = users.first()
            now = timezone.now()
            with transaction.atomic():
                challenge = (
                    PasswordResetOTP.objects.select_for_update()
                    .filter(user=user, consumed_at__isnull=True)
                    .order_by("-created_at", "-pk")
                    .first()
                )
                if (
                    challenge is not None
                    and challenge.expires_at > now
                    and challenge.attempts < OTP_MAX_ATTEMPTS
                    and hmac.compare_digest(
                        _otp_digest(user, form.cleaned_data["otp"]),
                        challenge.code_hash,
                    )
                ):
                    try:
                        validate_password(form.cleaned_data["new_password1"], user)
                    except ValidationError as error:
                        form.add_error("new_password1", error)
                    else:
                        user.set_password(form.cleaned_data["new_password1"])
                        user.save(update_fields=["password"])
                        challenge.consumed_at = now
                        challenge.save(update_fields=["consumed_at"])
                        PasswordResetOTP.objects.filter(
                            user=user,
                            consumed_at__isnull=True,
                        ).exclude(pk=challenge.pk).update(consumed_at=now)
                        reset_complete = True
                elif challenge is not None and challenge.expires_at > now:
                    challenge.attempts += 1
                    if challenge.attempts >= OTP_MAX_ATTEMPTS:
                        challenge.consumed_at = now
                        challenge.save(update_fields=["attempts", "consumed_at"])
                    else:
                        challenge.save(update_fields=["attempts"])

        if reset_complete:
            messages.success(request, "Your password has been reset. Please log in.")
            return redirect("accounts:login")
        if not form.errors:
            form.add_error(None, INVALID_OTP_MESSAGE)

    return render(request, "accounts/reset_password.html", {"form": form})
