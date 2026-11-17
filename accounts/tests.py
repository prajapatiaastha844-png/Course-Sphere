import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from django.urls import reverse

from .models import Admin, Instructor, PasswordResetOTP, Student


class AccountRegistrationTests(TestCase):
    def test_student_registration_creates_auth_user_and_profile(self):
        response = self.client.post(
            reverse("accounts:register", kwargs={"role": "student"}),
            {
                "name": "Student Example",
                "username": "student@example.com",
                "student_id": "ST-001",
                "password1": "StrongPassword-2026!",
                "password2": "StrongPassword-2026!",
            },
        )

        self.assertRedirects(response, reverse("accounts:login"))
        user = get_user_model().objects.get(username="student@example.com")
        student = Student.objects.get(user=user)
        self.assertEqual(student.email, "student@example.com")
        self.assertTrue(user.check_password("StrongPassword-2026!"))

    def test_instructor_registration_creates_instructor_profile(self):
        response = self.client.post(
            reverse("accounts:register", kwargs={"role": "instructor"}),
            {
                "name": "Instructor Example",
                "username": "instructor@example.com",
                "employee_id": "IN-001",
                "specialization": "Mathematics",
                "password1": "StrongPassword-2026!",
                "password2": "StrongPassword-2026!",
            },
        )

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertTrue(
            Instructor.objects.filter(
                email="instructor@example.com",
                employee_id="IN-001",
                specialization="Mathematics",
            ).exists()
        )

    def test_admin_profile_registration_requires_staff_and_uses_existing_user(self):
        response = self.client.post(
            reverse("accounts:register", kwargs={"role": "admin"}),
            {"name": "Not Staff", "email": "not-staff@example.com"},
        )
        self.assertEqual(response.status_code, 302)

        regular_user = get_user_model().objects.create_user(
            username="regular@example.com",
            email="regular@example.com",
            password="StrongPassword-2026!",
        )
        self.client.force_login(regular_user)
        response = self.client.post(
            reverse("accounts:register", kwargs={"role": "admin"}),
            {"name": "Not Staff", "email": "regular@example.com"},
        )
        self.assertEqual(response.status_code, 403)

        staff_user = get_user_model().objects.create_user(
            username="staff@example.com",
            email="staff@example.com",
            password="StrongPassword-2026!",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        response = self.client.post(
            reverse("accounts:register", kwargs={"role": "admin"}),
            {"name": "Staff Admin", "email": "staff@example.com"},
        )

        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertTrue(Admin.objects.filter(user=staff_user).exists())
        self.assertEqual(get_user_model().objects.count(), 2)


class AccountAuthenticationTests(TestCase):
    def test_login_with_email_and_post_logout(self):
        get_user_model().objects.create_user(
            username="legacy-learner",
            email="learner@example.com",
            password="StrongPassword-2026!",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "learner@example.com",
                "password": "StrongPassword-2026!",
            },
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertEqual(
            self.client.get(reverse("accounts:dashboard")).status_code,
            200,
        )

        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reset@example.com",
            email="reset@example.com",
            password="OriginalPassword-2026!",
        )

    def request_code(self, email="reset@example.com"):
        return self.client.post(
            reverse("accounts:forgot_password"),
            {"email": email},
        )

    def test_reset_code_resets_password_and_cannot_be_reused(self):
        response = self.request_code()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "If an account exists")
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r"code is: (\d{6})", mail.outbox[0].body)
        self.assertIsNotNone(match)
        code = match.group(1)
        challenge = PasswordResetOTP.objects.get(user=self.user)
        self.assertNotIn(code, challenge.code_hash)

        response = self.client.post(
            reverse("accounts:reset_password"),
            {
                "email": self.user.email,
                "otp": code,
                "new_password1": "UpdatedPassword-2026!",
                "new_password2": "UpdatedPassword-2026!",
            },
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("UpdatedPassword-2026!"))

        response = self.client.post(
            reverse("accounts:reset_password"),
            {
                "email": self.user.email,
                "otp": code,
                "new_password1": "AnotherPassword-2026!",
                "new_password2": "AnotherPassword-2026!",
            },
        )
        self.assertContains(response, "code is invalid or expired")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("UpdatedPassword-2026!"))

    def test_unknown_email_gets_generic_response_without_sending_email(self):
        response = self.request_code("unknown@example.com")

        self.assertContains(response, "If an account exists")
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_code_attempts_are_limited(self):
        self.request_code()
        challenge = PasswordResetOTP.objects.get(user=self.user)
        code = re.search(r"code is: (\d{6})", mail.outbox[0].body).group(1)
        wrong_code = f"{(int(code) + 1) % 1_000_000:06d}"

        for _ in range(5):
            response = self.client.post(
                reverse("accounts:reset_password"),
                {
                    "email": self.user.email,
                    "otp": wrong_code,
                    "new_password1": "UpdatedPassword-2026!",
                    "new_password2": "UpdatedPassword-2026!",
                },
            )
        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 5)
        self.assertIsNotNone(challenge.consumed_at)
        self.assertContains(response, "code is invalid or expired")

    def test_expired_code_is_rejected_and_resend_is_throttled(self):
        self.request_code()
        challenge = PasswordResetOTP.objects.get(user=self.user)
        code = re.search(r"code is: (\d{6})", mail.outbox[0].body).group(1)
        challenge.expires_at = timezone.now() - timedelta(seconds=1)
        challenge.save(update_fields=["expires_at"])

        response = self.client.post(
            reverse("accounts:reset_password"),
            {
                "email": self.user.email,
                "otp": code,
                "new_password1": "UpdatedPassword-2026!",
                "new_password2": "UpdatedPassword-2026!",
            },
        )
        self.assertContains(response, "code is invalid or expired")

        response = self.request_code()
        self.assertContains(response, "If an account exists")
        self.assertEqual(len(mail.outbox), 1)
