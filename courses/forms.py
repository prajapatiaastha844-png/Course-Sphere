from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError

from .models import Course


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "title",
            "category",
            "price",
            "level",
            "description",
            "is_published",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Complete Full-Stack Web Development",
                    "required": True,
                }
            ),
            "category": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Web Development, Data Science, AI",
                    "required": True,
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "0.00",
                    "min": "0",
                    "step": "0.01",
                    "required": True,
                }
            ),
            "level": forms.Select(
                attrs={
                    "class": "form-control",
                    "required": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Describe what students will learn in this course...",
                    "required": True,
                }
            ),
            "is_published": forms.CheckboxInput(
                attrs={
                    "class": "form-checkbox",
                }
            ),
        }
        labels = {
            "title": "Course Title",
            "category": "Category",
            "price": "Price (₹)",
            "level": "Skill Level",
            "description": "Course Description",
            "is_published": "Publish immediately (visible to students)",
        }
        help_texts = {
            "price": "Enter 0 for a free course.",
            "is_published": "Unchecked courses remain in draft mode and won't appear in public listings.",
        }

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is not None and price < Decimal("0.00"):
            raise ValidationError("Course price cannot be negative.")
        return price
