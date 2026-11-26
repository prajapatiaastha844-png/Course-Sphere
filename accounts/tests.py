import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from django.urls import reverse

from courses.models import Course, Order

from .models import Admin, Enrollment, Instructor, PasswordResetOTP, Student


class AccountRegistrationTests(TestCase):
    def test_registration_pages_show_role_specific_copy_and_fields(self):
        student_response = self.client.get(
            reverse("accounts:register", kwargs={"role": "student"})
        )
        self.assertContains(student_response, "Make learning yours.")
        self.assertContains(student_response, 'name="student_id"')

        instructor_response = self.client.get(
            reverse("accounts:register", kwargs={"role": "instructor"})
        )
        self.assertContains(instructor_response, "Share what you know.")
        self.assertContains(instructor_response, 'name="employee_id"')
        self.assertContains(instructor_response, 'name="specialization"')

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
    def test_home_redirects_to_dashboard(self):
        response = self.client.get("/")

        self.assertRedirects(
            response,
            reverse("accounts:dashboard"),
            fetch_redirect_response=False,
        )

    def test_login_form_preserves_the_requested_destination(self):
        destination = reverse("courses:course_list")

        response = self.client.get(
            reverse("accounts:login"),
            {"next": destination},
        )

        self.assertContains(
            response,
            f'name="next" value="{destination}"',
        )

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


class DashboardViewTests(TestCase):
    def test_staff_dashboard_shows_admin_data_and_custom_section_links(self):
        user_model = get_user_model()
        admin_user = user_model.objects.create_user(
            username="admin@example.com",
            password="StrongPassword-2026!",
            is_staff=True,
            is_superuser=True,
        )
        student_user = user_model.objects.create_user(
            username="dashboard-student@example.com",
            password="StrongPassword-2026!",
        )
        student = Student.objects.create(
            user=student_user,
            name="Dashboard Student",
            email="dashboard-student@example.com",
            student_id="ST-ADMIN-1",
        )
        instructor_user = user_model.objects.create_user(
            username="dashboard-instructor@example.com",
            password="StrongPassword-2026!",
        )
        instructor = Instructor.objects.create(
            user=instructor_user,
            name="Dashboard Instructor",
            email="dashboard-instructor@example.com",
            employee_id="IN-ADMIN-1",
            specialization="Science",
        )
        course = Course.objects.create(
            title="Admin Dashboard Course",
            category="Science",
            price="25.00",
            description="Course visible in the admin dashboard.",
            instructor=instructor,
            is_published=True,
        )
        Enrollment.objects.create(student=student, course=course)
        order = Order.objects.create(
            student=student,
            total_amount="25.00",
            status=Order.Status.SUCCESS,
        )
        order.courses.add(course)
        self.client.force_login(admin_user)

        response = self.client.get(reverse("accounts:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/admin_dashboard.html")
        self.assertContains(response, "Admin dashboard")
        self.assertContains(response, "Dashboard Student")
        self.assertContains(response, "Dashboard Instructor")
        self.assertContains(response, "Admin Dashboard Course")
        self.assertContains(response, f"#{order.pk}")
        self.assertContains(
            response,
            reverse("accounts:admin_section", kwargs={"section": "users"}),
        )
        self.assertContains(
            response,
            reverse("accounts:admin_section", kwargs={"section": "orders"}),
        )
        for section, record in (
            ("orders", order),
            ("courses", course),
            ("students", student),
            ("instructors", instructor),
        ):
            self.assertContains(
                response,
                reverse(
                    "accounts:admin_record_edit",
                    kwargs={"section": section, "pk": record.pk},
                ),
            )
        self.assertNotContains(response, 'href="/admin/')
        self.assertEqual(response.context["admin_stats"]["users"], 3)
        self.assertEqual(response.context["admin_stats"]["students"], 1)
        self.assertEqual(response.context["admin_stats"]["instructors"], 1)
        self.assertEqual(response.context["admin_stats"]["courses"], 1)
        self.assertEqual(response.context["admin_stats"]["enrollments"], 1)
        self.assertEqual(response.context["admin_stats"]["orders"], 1)
        self.assertEqual(response.context["admin_stats"]["successful_orders"], 1)
        self.assertEqual(
            response.context["admin_stats"]["revenue"],
            Decimal("25.00"),
        )

        for section in ("users", "students", "instructors", "courses", "orders"):
            section_response = self.client.get(
                reverse("accounts:admin_section", kwargs={"section": section})
            )
            self.assertEqual(section_response.status_code, 200)
            self.assertTemplateUsed(
                section_response,
                "accounts/admin_section.html",
            )
            self.assertEqual(section_response.context["active_section"], section)
            self.assertNotContains(section_response, "Site administration")

        search_response = self.client.get(
            reverse(
                "accounts:admin_section",
                kwargs={"section": "students"},
            ),
            {"q": "Dashboard Student"},
        )
        self.assertContains(search_response, "Dashboard Student")
        self.assertEqual(search_response.context["page_obj"].paginator.count, 1)

    def test_non_staff_dashboard_does_not_show_admin_data(self):
        user = get_user_model().objects.create_user(
            username="regular-dashboard@example.com",
            password="StrongPassword-2026!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Admin dashboard")
        self.assertNotContains(response, "Manage CourseSphere")
        self.assertNotIn("admin_stats", response.context)
        self.assertEqual(
            self.client.get(
                reverse(
                    "accounts:admin_section",
                    kwargs={"section": "students"},
                )
            ).status_code,
            403,
        )

    def test_admin_record_view_edit_delete_actions_work_for_every_section(self):
        user_model = get_user_model()
        admin_user = user_model.objects.create_superuser(
            username="crud-admin@example.com",
            email="crud-admin@example.com",
            password="StrongPassword-2026!",
        )
        student_user = user_model.objects.create_user(
            username="crud-student@example.com",
            email="crud-student@example.com",
            password="StrongPassword-2026!",
        )
        student = Student.objects.create(
            user=student_user,
            name="CRUD Student",
            email="crud-student@example.com",
            student_id="ST-CRUD-1",
        )
        instructor_user = user_model.objects.create_user(
            username="crud-instructor@example.com",
            email="crud-instructor@example.com",
            password="StrongPassword-2026!",
        )
        instructor = Instructor.objects.create(
            user=instructor_user,
            name="CRUD Instructor",
            email="crud-instructor@example.com",
            employee_id="IN-CRUD-1",
            specialization="Science",
        )
        course = Course.objects.create(
            title="CRUD Course",
            category="Science",
            price="20.00",
            description="Course used to test admin actions.",
            instructor=instructor,
        )
        order = Order.objects.create(
            student=student,
            total_amount="20.00",
        )
        order.courses.add(course)
        target_user = user_model.objects.create_user(
            username="delete-user@example.com",
            email="delete-user@example.com",
            password="StrongPassword-2026!",
        )
        self.client.force_login(admin_user)

        records = {
            "users": target_user,
            "students": student,
            "instructors": instructor,
            "courses": course,
            "orders": order,
        }
        for section, record in records.items():
            listing = self.client.get(
                reverse("accounts:admin_section", kwargs={"section": section})
            )
            self.assertContains(listing, "View")
            self.assertContains(listing, "Edit")
            self.assertContains(listing, "Delete")
            for action, route_name in (
                ("view", "admin_record"),
                ("edit", "admin_record_edit"),
                ("delete", "admin_record_delete"),
            ):
                action_url = reverse(
                    f"accounts:{route_name}",
                    kwargs={"section": section, "pk": record.pk},
                )
                response = self.client.get(action_url)
                self.assertEqual(response.status_code, 200)
                if action == "delete":
                    self.assertContains(response, "This action cannot be undone.")

        user_edit_url = reverse(
            "accounts:admin_record_edit",
            kwargs={"section": "users", "pk": target_user.pk},
        )
        self.assertRedirects(
            self.client.post(
                user_edit_url,
                {
                    "username": "updated-user@example.com",
                    "first_name": "Updated",
                    "last_name": "User",
                    "email": "updated-user@example.com",
                    "is_active": "on",
                },
            ),
            reverse(
                "accounts:admin_record",
                kwargs={"section": "users", "pk": target_user.pk},
            ),
        )
        target_user.refresh_from_db()
        self.assertEqual(target_user.username, "updated-user@example.com")

        self.client.post(
            reverse(
                "accounts:admin_record_edit",
                kwargs={"section": "users", "pk": student_user.pk},
            ),
            {
                "username": "crud-student@example.com",
                "first_name": "",
                "last_name": "",
                "email": "student-updated-via-user@example.com",
                "is_active": "on",
            },
        )
        student.refresh_from_db()
        self.assertEqual(student.email, "student-updated-via-user@example.com")

        student_edit_url = reverse(
            "accounts:admin_record_edit",
            kwargs={"section": "students", "pk": student.pk},
        )
        self.assertRedirects(
            self.client.post(
                student_edit_url,
                {
                    "name": "Updated Student",
                    "email": "updated-student@example.com",
                    "student_id": "ST-CRUD-1",
                },
            ),
            reverse(
                "accounts:admin_record",
                kwargs={"section": "students", "pk": student.pk},
            ),
        )
        student_user.refresh_from_db()
        self.assertEqual(student_user.username, "updated-student@example.com")
        self.assertEqual(student_user.email, "updated-student@example.com")

        instructor_edit_url = reverse(
            "accounts:admin_record_edit",
            kwargs={"section": "instructors", "pk": instructor.pk},
        )
        self.assertRedirects(
            self.client.post(
                instructor_edit_url,
                {
                    "name": "Updated Instructor",
                    "email": "crud-instructor@example.com",
                    "employee_id": "IN-CRUD-1",
                    "specialization": "Mathematics",
                },
            ),
            reverse(
                "accounts:admin_record",
                kwargs={"section": "instructors", "pk": instructor.pk},
            ),
        )
        instructor.refresh_from_db()
        self.assertEqual(instructor.specialization, "Mathematics")

        course_edit_url = reverse(
            "accounts:admin_record_edit",
            kwargs={"section": "courses", "pk": course.pk},
        )
        self.assertRedirects(
            self.client.post(
                course_edit_url,
                {
                    "title": "Updated CRUD Course",
                    "category": "Science",
                    "price": "22.50",
                    "level": Course.Level.INTERMEDIATE,
                    "description": "Updated course description.",
                    "is_published": "on",
                    "instructor": str(instructor.pk),
                },
            ),
            reverse(
                "accounts:admin_record",
                kwargs={"section": "courses", "pk": course.pk},
            ),
        )
        course.refresh_from_db()
        self.assertEqual(course.title, "Updated CRUD Course")

        order_edit_url = reverse(
            "accounts:admin_record_edit",
            kwargs={"section": "orders", "pk": order.pk},
        )
        self.assertRedirects(
            self.client.post(
                order_edit_url,
                {
                    "status": Order.Status.FAILED,
                    "total_amount": "22.50",
                    "currency": "INR",
                    "courses": [str(course.pk)],
                },
            ),
            reverse(
                "accounts:admin_record",
                kwargs={"section": "orders", "pk": order.pk},
            ),
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.FAILED)

        delete_records = {
            "orders": order,
            "courses": course,
            "instructors": instructor,
            "students": student,
            "users": target_user,
        }
        for section, record in delete_records.items():
            delete_url = reverse(
                "accounts:admin_record_delete",
                kwargs={"section": section, "pk": record.pk},
            )
            self.assertEqual(self.client.post(delete_url).status_code, 302)
            if section == "students":
                self.assertFalse(user_model.objects.filter(pk=student_user.pk).exists())
            elif section == "instructors":
                self.assertFalse(
                    user_model.objects.filter(pk=instructor_user.pk).exists()
                )
            else:
                self.assertFalse(
                    {
                        "users": user_model,
                        "courses": Course,
                        "orders": Order,
                    }[section]
                    .objects.filter(pk=record.pk)
                    .exists()
                )

    def test_staff_can_add_records_from_each_custom_section(self):
        admin_user = get_user_model().objects.create_superuser(
            username="add-admin@example.com",
            email="add-admin@example.com",
            password="StrongPassword-2026!",
        )
        self.client.force_login(admin_user)

        add_sections = ("users", "students", "instructors", "courses", "orders")
        for section in add_sections:
            response = self.client.get(
                reverse("accounts:admin_add", kwargs={"section": section})
            )
            self.assertEqual(response.status_code, 200)

        user_response = self.client.post(
            reverse("accounts:admin_add", kwargs={"section": "users"}),
            {
                "username": "added-user@example.com",
                "email": "added-user@example.com",
                "first_name": "Added",
                "last_name": "User",
                "password1": "StrongPassword-2026!",
                "password2": "StrongPassword-2026!",
                "is_active": "on",
            },
        )
        self.assertEqual(user_response.status_code, 302)
        self.assertTrue(
            get_user_model().objects.filter(username="added-user@example.com").exists()
        )

        student_response = self.client.post(
            reverse("accounts:admin_add", kwargs={"section": "students"}),
            {
                "name": "Added Student",
                "username": "added-student@example.com",
                "student_id": "ST-ADD-1",
                "password1": "StrongPassword-2026!",
                "password2": "StrongPassword-2026!",
            },
        )
        self.assertEqual(student_response.status_code, 302)
        student = Student.objects.get(student_id="ST-ADD-1")

        instructor_response = self.client.post(
            reverse("accounts:admin_add", kwargs={"section": "instructors"}),
            {
                "name": "Added Instructor",
                "username": "added-instructor@example.com",
                "employee_id": "IN-ADD-1",
                "specialization": "Design",
                "password1": "StrongPassword-2026!",
                "password2": "StrongPassword-2026!",
            },
        )
        self.assertEqual(instructor_response.status_code, 302)
        instructor = Instructor.objects.get(employee_id="IN-ADD-1")

        course_response = self.client.post(
            reverse("accounts:admin_add", kwargs={"section": "courses"}),
            {
                "title": "Admin Created Course",
                "category": "Design",
                "price": "19.99",
                "level": Course.Level.BEGINNER,
                "description": "Created from the custom admin dashboard.",
                "instructor": str(instructor.pk),
            },
        )
        self.assertEqual(course_response.status_code, 302)
        course = Course.objects.get(title="Admin Created Course")

        order_response = self.client.post(
            reverse("accounts:admin_add", kwargs={"section": "orders"}),
            {
                "student": str(student.pk),
                "status": Order.Status.PENDING,
                "total_amount": "19.99",
                "currency": "INR",
                "courses": [str(course.pk)],
            },
        )
        self.assertEqual(order_response.status_code, 302)
        order = Order.objects.get(student=student)
        self.assertEqual(list(order.courses.all()), [course])

    def test_student_dashboard_shows_course_catalog_and_profile(self):
        user = get_user_model().objects.create_user(
            username="student@example.com",
            password="StrongPassword-2026!",
        )
        Student.objects.create(
            user=user,
            name="Student Example",
            email="student@example.com",
            student_id="ST-100",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student dashboard")
        self.assertContains(response, "Explore courses")
        self.assertContains(response, "ST-100")

    def test_student_dashboard_displays_cart_items(self):
        user = get_user_model().objects.create_user(
            username="student-cart@example.com",
            password="StrongPassword-2026!",
        )
        student = Student.objects.create(
            user=user,
            name="Cart Student Example",
            email="student-cart@example.com",
            student_id="ST-CART-1",
        )
        course = Course.objects.create(
            title="Cart Course Item",
            category="Design",
            price="29.99",
            description="Course in cart.",
            is_published=True,
        )
        from courses.models import Cart
        Cart.objects.create(student=student, course=course)
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your cart (1)")
        self.assertContains(response, "Cart Course Item")

    def test_instructor_dashboard_lists_assigned_courses(self):
        user = get_user_model().objects.create_user(
            username="instructor@example.com",
            password="StrongPassword-2026!",
        )
        instructor = Instructor.objects.create(
            user=user,
            name="Instructor Example",
            email="instructor@example.com",
            employee_id="IN-100",
            specialization="Mathematics",
        )
        Course.objects.create(
            title="Algebra Basics",
            category="Mathematics",
            price="15.00",
            description="An introduction to algebra.",
            instructor=instructor,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Instructor dashboard")
        self.assertContains(response, "IN-100")
        self.assertContains(response, "Algebra Basics")


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
