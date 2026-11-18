from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Instructor, Student
from .models import Course


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
