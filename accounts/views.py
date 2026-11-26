import hmac
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.crypto import salted_hmac
from django.utils import timezone

from courses.models import Course, Order

from .forms import (
    AdminCourseForm,
    AdminInstructorForm,
    AdminOrderCreateForm,
    AdminOrderForm,
    AdminRegistrationForm,
    AdminStudentForm,
    AdminUserForm,
    AdminUserCreateForm,
    ForgotPasswordForm,
    InstructorRegistrationForm,
    OTPPasswordResetForm,
    StudentRegistrationForm,
)
from .models import Admin, Enrollment, Instructor, PasswordResetOTP, Student


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


def _create_registered_profile(form, profile_model):
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


@login_required(login_url="accounts:login")
def admin_section(request, section):
    if not request.user.is_staff:
        raise PermissionDenied

    if section == "users":
        records = get_user_model().objects.order_by("-date_joined", "-pk")
        title = "User accounts"
        description = "Review all accounts registered on CourseSphere."
        search_fields = ("username", "email")
    elif section == "students":
        records = Student.objects.order_by("-enrollment_date", "-pk")
        title = "Students"
        description = "Review learner profiles and registration details."
        search_fields = ("name", "email", "student_id")
    elif section == "instructors":
        records = Instructor.objects.order_by("-pk")
        title = "Instructors"
        description = "Review instructor profiles and specializations."
        search_fields = ("name", "email", "employee_id", "specialization")
    elif section == "courses":
        records = Course.objects.select_related("instructor").order_by("-created_at")
        title = "Courses"
        description = "Review every course in the CourseSphere catalog."
        search_fields = ("title", "category", "instructor__name")
    elif section == "orders":
        records = (
            Order.objects.select_related("student")
            .prefetch_related("courses")
            .order_by("-created_at")
        )
        title = "Orders"
        description = "Review payments and course purchases."
        search_fields = (
            "student__name",
            "student__email",
            "razorpay_order_id",
            "status",
        )
    else:
        raise Http404("Unknown admin section.")

    search_query = request.GET.get("q", "").strip()
    if search_query:
        search_filter = Q(**{f"{search_fields[0]}__icontains": search_query})
        for field in search_fields[1:]:
            search_filter |= Q(**{f"{field}__icontains": search_query})
        records = records.filter(search_filter)

    page_obj = Paginator(records, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/admin_section.html",
        {
            "active_section": section,
            "add_label": {
                "users": "user",
                "students": "student",
                "instructors": "instructor",
                "courses": "course",
                "orders": "order",
            }[section],
            "page_obj": page_obj,
            "profile": Admin.objects.filter(user=request.user).first(),
            "search_query": search_query,
            "section_description": description,
            "section_title": title,
        },
    )


@login_required(login_url="accounts:login")
def admin_add(request, section):
    if not request.user.is_staff:
        raise PermissionDenied

    form_config = {
        "users": (AdminUserCreateForm, "user account"),
        "students": (StudentRegistrationForm, "student"),
        "instructors": (InstructorRegistrationForm, "instructor"),
        "courses": (AdminCourseForm, "course"),
        "orders": (AdminOrderCreateForm, "order"),
    }
    if section not in form_config:
        raise Http404("Unknown admin section.")

    form_class, record_label = form_config[section]
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if section == "users":
                form.save()
            elif section == "students":
                _create_registered_profile(form, Student)
            elif section == "instructors":
                _create_registered_profile(form, Instructor)
            else:
                form.save()
        messages.success(request, f"The {record_label} was added.")
        return redirect("accounts:admin_section", section=section)

    return render(
        request,
        "accounts/admin_record.html",
        {
            "action": "add",
            "active_section": section,
            "form": form,
            "profile": Admin.objects.filter(user=request.user).first(),
            "record_label": record_label,
            "section_title": section.title(),
        },
    )


def _get_admin_record(section, pk):
    if section == "users":
        return get_object_or_404(get_user_model(), pk=pk)
    if section == "students":
        return get_object_or_404(Student.objects.select_related("user"), pk=pk)
    if section == "instructors":
        return get_object_or_404(Instructor.objects.select_related("user"), pk=pk)
    if section == "courses":
        return get_object_or_404(Course.objects.select_related("instructor"), pk=pk)
    if section == "orders":
        return get_object_or_404(
            Order.objects.select_related("student").prefetch_related("courses"),
            pk=pk,
        )
    raise Http404("Unknown admin section.")


@login_required(login_url="accounts:login")
def admin_record(request, section, pk, action):
    if not request.user.is_staff:
        raise PermissionDenied
    if section not in {"users", "students", "instructors", "courses", "orders"}:
        raise Http404("Unknown admin section.")
    if action not in {"view", "edit", "delete"}:
        raise Http404("Unknown admin action.")
    if action == "view" and request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if action != "view" and request.method not in {"GET", "POST"}:
        return HttpResponseNotAllowed(["GET", "POST"])

    record = _get_admin_record(section, pk)
    if (
        section == "users"
        and record.is_superuser
        and not request.user.is_superuser
    ):
        raise PermissionDenied
    if (
        action == "delete"
        and section in {"students", "instructors"}
        and record.user_id == request.user.pk
    ):
        raise PermissionDenied
    if (
        action == "delete"
        and section == "users"
        and record.pk == request.user.pk
    ):
        raise PermissionDenied

    form_classes = {
        "users": AdminUserForm,
        "students": AdminStudentForm,
        "instructors": AdminInstructorForm,
        "courses": AdminCourseForm,
        "orders": AdminOrderForm,
    }
    record_labels = {
        "users": "user account",
        "students": "student",
        "instructors": "instructor",
        "courses": "course",
        "orders": "order",
    }
    delete_warnings = {
        "users": (
            "This also removes the account's role profile and related enrollments, "
            "carts, and orders. Instructor courses will remain but become unassigned."
        ),
        "students": (
            "This removes the student's login account, profile, enrollments, "
            "cart, and orders."
        ),
        "instructors": (
            "This removes the instructor's login account and profile. Their "
            "courses will remain but become unassigned."
        ),
        "courses": (
            "This removes the course and its cart/enrollment links. Existing "
            "orders remain, but will no longer list this course."
        ),
        "orders": "This permanently removes the order and its payment record.",
    }
    context = {
        "action": action,
        "active_section": section,
        "delete_warning": delete_warnings[section],
        "profile": Admin.objects.filter(user=request.user).first(),
        "record": record,
        "record_label": record_labels[section],
        "section_title": section.title(),
    }

    if action == "view":
        return render(request, "accounts/admin_record.html", context)
    if action == "delete":
        if request.method == "POST":
            record_name = str(record)
            if section in {"students", "instructors"} and record.user_id:
                record.user.delete()
            else:
                record.delete()
            messages.success(
                request,
                f"The {record_labels[section]} '{record_name}' was deleted.",
            )
            return redirect("accounts:admin_section", section=section)
        return render(request, "accounts/admin_record.html", context)

    form_class = form_classes[section]
    form = form_class(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        if (
            section == "users"
            and record.pk == request.user.pk
            and not form.cleaned_data["is_active"]
        ):
            form.add_error("is_active", "You cannot deactivate your own account.")
        else:
            with transaction.atomic():
                if section == "users":
                    form.save()
                    for profile_model in (Admin, Student, Instructor):
                        profile_model.objects.filter(user=record).update(
                            email=form.cleaned_data["email"]
                        )
                else:
                    if section in {"students", "instructors"} and record.user_id:
                        linked_user = record.user
                        linked_user.email = form.cleaned_data["email"]
                        linked_user.username = form.cleaned_data["email"]
                        linked_user.save(update_fields=["email", "username"])
                    form.save()
            messages.success(
                request,
                f"The {record_labels[section]} was updated.",
            )
            return redirect("accounts:admin_record", section=section, pk=record.pk)

    context["form"] = form
    return render(request, "accounts/admin_record.html", context)


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
                _create_registered_profile(form, profile_model)
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
    if request.user.is_staff:
        profile = Admin.objects.filter(user=request.user).first()
        role = "Admin"
    else:
        profile = None
        role = None
        for profile_model, role_name in (
            (Student, "Student"),
            (Instructor, "Instructor"),
        ):
            profile = profile_model.objects.filter(user=request.user).first()
            if profile is not None:
                role = role_name
                break

    context = {"profile": profile, "role": role}
    if isinstance(profile, Instructor):
        context["courses"] = profile.courses.all()
    elif isinstance(profile, Student):
        context["cart_items"] = profile.cart_items.select_related("course")
    elif request.user.is_staff:
        successful_orders = Order.objects.filter(status=Order.Status.SUCCESS)
        context.update(
            {
                "active_section": "overview",
                "admin_stats": {
                    "users": get_user_model().objects.count(),
                    "students": Student.objects.count(),
                    "instructors": Instructor.objects.count(),
                    "courses": Course.objects.count(),
                    "enrollments": Enrollment.objects.count(),
                    "orders": Order.objects.count(),
                    "successful_orders": successful_orders.count(),
                    "revenue": successful_orders.aggregate(
                        total=Sum("total_amount")
                    )["total"]
                    or Decimal("0.00"),
                },
                "recent_students": Student.objects.order_by("-enrollment_date", "-pk")[
                    :5
                ],
                "recent_instructors": Instructor.objects.order_by("-pk")[:5],
                "recent_courses": Course.objects.select_related("instructor").order_by(
                    "-created_at"
                )[:5],
                "recent_orders": Order.objects.select_related("student")
                .prefetch_related("courses")
                .order_by("-created_at")[:5],
            }
        )
        return render(request, "accounts/admin_dashboard.html", context)
    return render(
        request,
        "accounts/dashboard.html",
        context,
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
