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
