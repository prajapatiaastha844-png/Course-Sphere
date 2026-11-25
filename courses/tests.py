from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
import razorpay

from accounts.models import Instructor, Student
from .models import Cart, Course, Order


class CartModelTests(TestCase):
    def test_cart_item_links_student_and_course(self):
        student = Student.objects.create(
            name="Student Example",
            email="cart-student@example.com",
            student_id="CART-ST-001",
        )
        course = Course.objects.create(
            title="Cart Course",
            category="Technology",
            price=Decimal("10.00"),
            description="A course in the student's cart.",
        )

        cart_item = Cart.objects.create(student=student, course=course, quantity=2)

        self.assertEqual(cart_item.student, student)
        self.assertEqual(cart_item.course, course)
        self.assertEqual(cart_item.quantity, 2)
        self.assertEqual(student.cart_items.get(), cart_item)
        self.assertEqual(course.cart_items.get(), cart_item)


class CartViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cart-student@example.com",
            email="cart-student@example.com",
            password="StrongPassword-2026!",
        )
        self.student = Student.objects.create(
            user=self.user,
            name="Cart Student",
            email=self.user.email,
            student_id="CART-VIEW-ST-001",
        )
        self.course = Course.objects.create(
            title="Cart View Course",
            category="Technology",
            price=Decimal("10.00"),
            description="A published course.",
            is_published=True,
        )
        self.client.force_login(self.user)

    def test_student_can_add_course_once_and_view_cart(self):
        add_url = reverse("courses:add_to_cart", kwargs={"pk": self.course.pk})

        response = self.client.post(add_url)
        self.assertRedirects(response, reverse("courses:cart"))

        response = self.client.post(add_url)
        self.assertRedirects(response, reverse("courses:cart"))
        self.assertEqual(Cart.objects.filter(student=self.student).count(), 1)

        response = self.client.get(reverse("courses:cart"))
        self.assertContains(response, self.course.title)
        self.assertEqual(response.context["total_price"], Decimal("10.00"))

    def test_student_can_remove_course_from_cart(self):
        cart_item = Cart.objects.create(student=self.student, course=self.course)

        response = self.client.post(
            reverse("courses:remove_from_cart", kwargs={"pk": cart_item.pk})
        )

        self.assertRedirects(response, reverse("courses:cart"))
        self.assertFalse(Cart.objects.filter(pk=cart_item.pk).exists())

    def test_student_cannot_remove_another_students_cart_item(self):
        another_student = Student.objects.create(
            name="Another Student",
            email="another-cart-student@example.com",
            student_id="CART-VIEW-ST-002",
        )
        cart_item = Cart.objects.create(
            student=another_student,
            course=self.course,
        )

        response = self.client.post(
            reverse("courses:remove_from_cart", kwargs={"pk": cart_item.pk})
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Cart.objects.filter(pk=cart_item.pk).exists())

    def test_student_can_remove_course_by_course_pk(self):
        Cart.objects.create(student=self.student, course=self.course)

        response = self.client.post(
            reverse("courses:remove_course_from_cart", kwargs={"pk": self.course.pk})
        )

        self.assertRedirects(response, reverse("courses:cart"))
        self.assertFalse(Cart.objects.filter(student=self.student, course=self.course).exists())

    def test_add_and_remove_respect_safe_next_redirect(self):
        next_url = reverse("courses:course_detail", kwargs={"pk": self.course.pk})
        response = self.client.post(
            reverse("courses:add_to_cart", kwargs={"pk": self.course.pk}),
            {"next": next_url},
        )
        self.assertRedirects(response, next_url)

        response = self.client.post(
            reverse("courses:remove_course_from_cart", kwargs={"pk": self.course.pk}),
            {"next": next_url},
        )
        self.assertRedirects(response, next_url)

    def test_course_detail_and_list_reflect_cart_status(self):
        detail_url = reverse("courses:course_detail", kwargs={"pk": self.course.pk})
        list_url = reverse("courses:course_list")

        response = self.client.get(detail_url)
        self.assertFalse(response.context["in_cart"])
        self.assertContains(response, "Add to cart")

        Cart.objects.create(student=self.student, course=self.course)

        response = self.client.get(detail_url)
        self.assertTrue(response.context["in_cart"])
        self.assertContains(response, "Remove from cart")

        response = self.client.get(list_url)
        self.assertIn(self.course.pk, response.context["cart_course_ids"])
        self.assertContains(response, "In cart")


class CourseModelTests(TestCase):
    def test_course_fields_and_instructor_relationship(self):
        instructor = Instructor.objects.create(
            name="Instructor Example",
            email="instructor@example.com",
            employee_id="IN-001",
            specialization="Mathematics",
        )
        course = Course.objects.create(
            title="Algebra Basics",
            category="Mathematics",
            price=Decimal("19.99"),
            description="An introduction to algebra.",
            instructor=instructor,
        )

        self.assertEqual(str(course), "Algebra Basics")
        self.assertEqual(course.instructor, instructor)
        self.assertEqual(course.level, Course.Level.BEGINNER)
        self.assertFalse(course.is_published)

    def test_negative_price_is_rejected_by_model_validation(self):
        course = Course(
            title="Free Course",
            category="General",
            price=Decimal("-0.01"),
            description="This price should be rejected.",
        )

        with self.assertRaises(ValidationError):
            course.full_clean()


class InstructorCourseViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="instructor@example.com",
            email="instructor@example.com",
            password="StrongPassword-2026!",
        )
        self.instructor = Instructor.objects.create(
            user=self.user,
            name="Instructor Example",
            email=self.user.email,
            employee_id="IN-COURSE-001",
            specialization="Technology",
        )
        self.client.force_login(self.user)
        self.add_url = reverse("courses:add_course")
        self.course = Course.objects.create(
            title="Course to Manage",
            category="Technology",
            price=Decimal("25.00"),
            level=Course.Level.BEGINNER,
            description="A course for update and delete tests.",
            instructor=self.instructor,
        )

    def test_instructor_can_create_course_and_view_it_on_dashboard(self):
        response = self.client.post(
            self.add_url,
            {
                "title": "Python Fundamentals",
                "category": "Programming",
                "price": "49.99",
                "level": Course.Level.BEGINNER,
                "description": "Learn Python from the ground up.",
                "is_published": "on",
            },
        )

        self.assertRedirects(response, reverse("courses:instructor_dashboard"))
        course = Course.objects.get(title="Python Fundamentals")
        self.assertEqual(course.instructor, self.instructor)
        self.assertEqual(course.price, Decimal("49.99"))
        self.assertEqual(course.level, Course.Level.BEGINNER)
        self.assertTrue(course.is_published)

        dashboard = self.client.get(reverse("courses:instructor_dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, course.title)
        self.assertContains(dashboard, "Add New Course")

    def test_dashboard_displays_all_and_only_the_instructors_courses(self):
        another_course = Course.objects.create(
            title="Another Instructor Course",
            category="Technology",
            price=Decimal("10.00"),
            description="A second course belonging to this instructor.",
            instructor=self.instructor,
        )
        other_user = get_user_model().objects.create_user(
            username="dashboard-other-instructor@example.com",
            password="StrongPassword-2026!",
        )
        other_instructor = Instructor.objects.create(
            user=other_user,
            name="Other Instructor",
            email=other_user.email,
            employee_id="IN-DASHBOARD-002",
            specialization="Science",
        )
        other_course = Course.objects.create(
            title="Not This Instructors Course",
            category="Science",
            price=Decimal("20.00"),
            description="A course belonging to another instructor.",
            is_published=True,
            instructor=other_instructor,
        )

        response = self.client.get(reverse("courses:instructor_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {course.pk for course in response.context["courses"]},
            {self.course.pk, another_course.pk},
        )
        self.assertContains(response, self.course.title)
        self.assertContains(response, another_course.title)
        self.assertNotContains(response, other_course.title)

    def test_instructor_cannot_create_course_with_negative_price(self):
        response = self.client.post(
            self.add_url,
            {
                "title": "Invalid Course",
                "category": "Programming",
                "price": "-1.00",
                "level": Course.Level.BEGINNER,
                "description": "This course has an invalid price.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Course price cannot be negative.")
        self.assertFalse(Course.objects.filter(title="Invalid Course").exists())

    def test_user_without_instructor_profile_cannot_add_course(self):
        student_user = get_user_model().objects.create_user(
            username="student@example.com",
            password="StrongPassword-2026!",
        )
        self.client.force_login(student_user)

        response = self.client.get(self.add_url)

        self.assertEqual(response.status_code, 403)

    def test_instructor_can_update_their_course(self):
        response = self.client.post(
            reverse("courses:edit_course", kwargs={"pk": self.course.pk}),
            {
                "title": "Updated Course",
                "category": "Programming",
                "price": "39.99",
                "level": Course.Level.ADVANCED,
                "description": "Updated course description.",
                "is_published": "on",
            },
        )

        self.assertRedirects(response, reverse("courses:instructor_dashboard"))
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "Updated Course")
        self.assertEqual(self.course.category, "Programming")
        self.assertEqual(self.course.price, Decimal("39.99"))
        self.assertEqual(self.course.level, Course.Level.ADVANCED)
        self.assertEqual(self.course.description, "Updated course description.")
        self.assertTrue(self.course.is_published)

    def test_instructor_cannot_update_another_instructors_course(self):
        other_user = get_user_model().objects.create_user(
            username="other-instructor@example.com",
            password="StrongPassword-2026!",
        )
        other_instructor = Instructor.objects.create(
            user=other_user,
            name="Other Instructor",
            email=other_user.email,
            employee_id="IN-COURSE-002",
            specialization="Science",
        )
        other_course = Course.objects.create(
            title="Other Instructor Course",
            category="Science",
            price=Decimal("15.00"),
            description="This course belongs to another instructor.",
            instructor=other_instructor,
        )

        response = self.client.post(
            reverse("courses:edit_course", kwargs={"pk": other_course.pk}),
            {"title": "Unauthorized Update"},
        )

        self.assertEqual(response.status_code, 404)
        other_course.refresh_from_db()
        self.assertEqual(other_course.title, "Other Instructor Course")

    def test_instructor_must_confirm_before_deleting_their_course(self):
        response = self.client.get(
            reverse("courses:delete_course", kwargs={"pk": self.course.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/course_confirm_delete.html")
        self.assertContains(response, self.course.title)
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())

    def test_instructor_can_delete_their_course_with_post(self):
        response = self.client.post(
            reverse("courses:delete_course", kwargs={"pk": self.course.pk})
        )

        self.assertRedirects(response, reverse("courses:instructor_dashboard"))
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())

    def test_instructor_cannot_delete_another_instructors_course(self):
        other_user = get_user_model().objects.create_user(
            username="other-delete-instructor@example.com",
            password="StrongPassword-2026!",
        )
        other_instructor = Instructor.objects.create(
            user=other_user,
            name="Other Instructor",
            email=other_user.email,
            employee_id="IN-COURSE-003",
            specialization="Science",
        )
        other_course = Course.objects.create(
            title="Protected Course",
            category="Science",
            price=Decimal("15.00"),
            description="This course must not be deleted.",
            instructor=other_instructor,
        )

        response = self.client.post(
            reverse("courses:delete_course", kwargs={"pk": other_course.pk})
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Course.objects.filter(pk=other_course.pk).exists())


class CourseListViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="StrongPassword-2026!",
        )
        Student.objects.create(
            user=self.user,
            name="Student Example",
            email=self.user.email,
            student_id="ST-001",
        )
        self.url = reverse("courses:course_list")

    def test_student_sees_published_courses_only(self):
        Course.objects.create(
            title="Published course",
            category="Science",
            price=Decimal("10.00"),
            description="Available to students.",
            is_published=True,
        )
        Course.objects.create(
            title="Draft course",
            category="Science",
            price=Decimal("20.00"),
            description="Not yet available.",
        )
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/course_list.html")
        self.assertContains(response, "Published course")
        self.assertNotContains(response, "Draft course")

    def test_search_matches_title_or_category_without_showing_drafts(self):
        Course.objects.create(
            title="Math Foundations",
            category="Science",
            price=Decimal("10.00"),
            description="A course matching the title.",
            is_published=True,
        )
        Course.objects.create(
            title="Creative Arts",
            category="Mathematics",
            price=Decimal("20.00"),
            description="A course matching the category.",
            is_published=True,
        )
        Course.objects.create(
            title="Math Draft",
            category="Mathematics",
            price=Decimal("30.00"),
            description="An unpublished course.",
        )
        Course.objects.create(
            title="Chemistry",
            category="Science",
            price=Decimal("40.00"),
            description="Does not match the search.",
            is_published=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(self.url, {"q": "MATH"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Math Foundations")
        self.assertContains(response, "Creative Arts")
        self.assertNotContains(response, "Math Draft")
        self.assertNotContains(response, "Chemistry")
        self.assertContains(response, 'value="MATH"')

    def test_search_with_no_matches_shows_clear_search_action(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url, {"q": "No such course"})

        self.assertContains(response, "No courses match")
        self.assertContains(response, "Clear search")
        self.assertNotContains(response, "There are no published courses yet.")

    def test_category_and_level_filters_combine_with_search(self):
        matching_course = Course.objects.create(
            title="Python for Analytics",
            category="Technology",
            level=Course.Level.ADVANCED,
            price=Decimal("10.00"),
            description="Learn analytics with Python.",
            is_published=True,
        )
        Course.objects.create(
            title="Python for Beginners",
            category="Technology",
            level=Course.Level.BEGINNER,
            price=Decimal("15.00"),
            description="Start learning Python.",
            is_published=True,
        )
        Course.objects.create(
            title="Python for Analytics",
            category="Science",
            level=Course.Level.ADVANCED,
            price=Decimal("20.00"),
            description="A different category.",
            is_published=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {"q": "python", "category": "Technology", "level": "advanced"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["courses"]), [matching_course])
        self.assertContains(response, 'value="Technology" selected')
        self.assertContains(response, 'value="advanced" selected')
        self.assertContains(response, "All categories")
        self.assertContains(response, "All levels")

    def test_pagination_keeps_search_and_filter_parameters(self):
        for index in range(10):
            Course.objects.create(
                title=f"Python Course {index:02}",
                category="Technology",
                level=Course.Level.BEGINNER,
                price=Decimal("10.00"),
                description="A published Python course.",
                is_published=True,
            )
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "q": "python",
                "category": "Technology",
                "level": "beginner",
                "page": "2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(response.context["page_obj"].paginator.count, 10)
        self.assertContains(
            response,
            "q=python&amp;category=Technology&amp;level=beginner&amp;page=1",
        )
        self.assertContains(response, "Python Course 09")
        self.assertNotContains(response, "Python Course 00")

    def test_course_list_requires_student_login(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self.url}",
        )

    def test_non_student_cannot_view_course_list(self):
        non_student = get_user_model().objects.create_user(
            username="instructor@example.com",
            password="StrongPassword-2026!",
        )
        self.client.force_login(non_student)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)


class CourseDetailViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="StrongPassword-2026!",
        )
        Student.objects.create(
            user=self.user,
            name="Student Example",
            email=self.user.email,
            student_id="ST-002",
        )
        instructor = Instructor.objects.create(
            name="Instructor Example",
            email="instructor@example.com",
            employee_id="IN-002",
            specialization="Data science",
        )
        self.course = Course.objects.create(
            title="Python Analytics",
            category="Technology",
            level=Course.Level.INTERMEDIATE,
            price=Decimal("89.00"),
            description="Learn to analyze data with Python.\nBuild useful projects.",
            instructor=instructor,
            is_published=True,
        )
        self.url = reverse("courses:course_detail", kwargs={"pk": self.course.pk})

    def test_student_sees_published_course_details(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/course_detail.html")
        self.assertContains(response, "Python Analytics")
        self.assertContains(response, "Technology")
        self.assertContains(response, "Intermediate")
        self.assertContains(response, "Instructor Example")
        self.assertContains(response, "Data science")
        self.assertContains(response, "89.00")
        self.assertContains(response, "Build useful projects.")

    def test_unpublished_course_is_not_available_in_detail_view(self):
        draft = Course.objects.create(
            title="Unpublished course",
            category="Technology",
            price=Decimal("10.00"),
            description="This course is not published.",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("courses:course_detail", kwargs={"pk": draft.pk})
        )

        self.assertEqual(response.status_code, 404)

    def test_detail_view_requires_a_student_login(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self.url}",
        )

        non_student = get_user_model().objects.create_user(
            username="instructor@example.com",
            password="StrongPassword-2026!",
        )
        self.client.force_login(non_student)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)


class RazorpayCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rzp-student@example.com",
            email="rzp-student@example.com",
            password="StrongPassword-2026!",
        )
        self.student = Student.objects.create(
            user=self.user,
            name="RZP Student",
            email=self.user.email,
            student_id="RZP-ST-001",
        )
        self.course = Course.objects.create(
            title="Razorpay Masterclass",
            category="Fintech",
            price=Decimal("49.99"),
            description="Learn payment gateway integrations.",
            is_published=True,
        )
        self.client.force_login(self.user)

    def test_checkout_with_empty_cart_redirects_to_courses(self):
        response = self.client.get(reverse("courses:checkout"))
        self.assertRedirects(response, reverse("courses:course_list"))

    @patch("courses.views.get_razorpay_client")
    def test_checkout_creates_order_and_renders_page(self, mock_client_getter):
        mock_client = MagicMock()
        mock_client.order.create.return_value = {"id": "order_test_rzp123"}
        mock_client_getter.return_value = mock_client

        Cart.objects.create(student=self.student, course=self.course)

        response = self.client.get(reverse("courses:checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/checkout.html")
        self.assertContains(response, "Pay with Razorpay")
        self.assertContains(response, "order_test_rzp123")

        order = Order.objects.get(student=self.student)
        self.assertEqual(order.razorpay_order_id, "order_test_rzp123")
        self.assertEqual(order.total_amount, Decimal("49.99"))
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertIn(self.course, order.courses.all())

    @patch("courses.views.get_razorpay_client")
    def test_payment_callback_success_updates_order_and_clears_cart(self, mock_client_getter):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_client_getter.return_value = mock_client

        Cart.objects.create(student=self.student, course=self.course)
        order = Order.objects.create(
            student=self.student,
            total_amount=Decimal("49.99"),
            currency="INR",
            razorpay_order_id="order_test_success_999",
            status=Order.Status.PENDING,
        )
        order.courses.add(self.course)

        response = self.client.post(
            reverse("courses:payment_callback"),
            {
                "razorpay_order_id": "order_test_success_999",
                "razorpay_payment_id": "pay_test_payment_123",
                "razorpay_signature": "valid_signature_abc",
            },
        )

        self.assertRedirects(
            response,
            reverse("courses:order_success", kwargs={"pk": order.pk}),
        )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SUCCESS)
        self.assertEqual(order.razorpay_payment_id, "pay_test_payment_123")
        self.assertEqual(order.razorpay_signature, "valid_signature_abc")

        # Cart should be cleared of the purchased course
        self.assertFalse(Cart.objects.filter(student=self.student).exists())

    @patch("courses.views.get_razorpay_client")
    def test_payment_callback_invalid_signature_marks_order_failed(self, mock_client_getter):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.side_effect = (
            razorpay.errors.SignatureVerificationError("Signature mismatch")
        )
        mock_client_getter.return_value = mock_client

        Cart.objects.create(student=self.student, course=self.course)
        order = Order.objects.create(
            student=self.student,
            total_amount=Decimal("49.99"),
            currency="INR",
            razorpay_order_id="order_test_fail_000",
            status=Order.Status.PENDING,
        )
        order.courses.add(self.course)

        response = self.client.post(
            reverse("courses:payment_callback"),
            {
                "razorpay_order_id": "order_test_fail_000",
                "razorpay_payment_id": "pay_test_bad_123",
                "razorpay_signature": "invalid_signature",
            },
        )

        self.assertRedirects(response, reverse("courses:cart"))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.FAILED)
        # Cart item should still remain
        self.assertTrue(Cart.objects.filter(student=self.student).exists())

    def test_order_success_view_accessible_by_student(self):
        order = Order.objects.create(
            student=self.student,
            total_amount=Decimal("49.99"),
            currency="INR",
            razorpay_order_id="order_success_view_test",
            razorpay_payment_id="pay_test_view_123",
            status=Order.Status.SUCCESS,
        )
        order.courses.add(self.course)

        response = self.client.get(
            reverse("courses:order_success", kwargs={"pk": order.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/order_success.html")
        self.assertContains(response, "Payment Successful!")
        self.assertContains(response, self.course.title)
