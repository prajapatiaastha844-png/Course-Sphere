from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Course(models.Model):
    class Level(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    description = models.TextField()
    instructor = models.ForeignKey(
        "accounts.Instructor",
        on_delete=models.SET_NULL,
        related_name="courses",
        null=True,
        blank=True,
    )
    level = models.CharField(
        max_length=12,
        choices=Level.choices,
        default=Level.BEGINNER,
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="course_price_nonnegative",
            ),
        ]

    def __str__(self):
        return self.title


class Cart(models.Model):
    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"],
                name="unique_student_course_cart_item",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="cart_quantity_at_least_one",
            ),
        ]

    def __str__(self):
        return f"{self.student} - {self.course}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="orders",
    )
    courses = models.ManyToManyField(Course, related_name="orders")
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=10, default="INR")
    razorpay_order_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} - {self.student} ({self.get_status_display()})"
