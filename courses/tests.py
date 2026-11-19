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
