from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError

from .models import Course, CourseContent, Order


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


class CourseContentForm(forms.ModelForm):
    content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 5}),
    )

    class Meta:
        model = CourseContent
        fields = ["title", "content", "notes_file", "video_url", "position"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "notes_file": forms.FileInput(
                attrs={"class": "form-control", "accept": ".pdf,.doc,.docx,.txt"}
            ),
            "video_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://"}
            ),
            "position": forms.NumberInput(
                attrs={"class": "form-control", "min": "0"}
            ),
        }
        labels = {
            "content": "Notes",
            "notes_file": "Notes file (PDF, DOC, DOCX, or TXT)",
            "video_url": "Video URL",
            "position": "Lesson position",
        }

    def clean(self):
        cleaned_data = super().clean()
        if not any(
            (
                cleaned_data.get("content"),
                cleaned_data.get("notes_file"),
                cleaned_data.get("video_url"),
            )
        ):
            raise ValidationError("Add notes, upload a notes file, or provide a video URL.")
        return cleaned_data

    def clean_notes_file(self):
        notes_file = self.cleaned_data.get("notes_file")
        if notes_file and notes_file.size > 10 * 1024 * 1024:
            raise ValidationError("Notes file must be 10 MB or smaller.")
        return notes_file


class AdminCourseForm(CourseForm):
    class Meta(CourseForm.Meta):
        fields = (*CourseForm.Meta.fields, "instructor")


class AdminOrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ("status", "total_amount", "currency", "courses")


class AdminOrderCreateForm(AdminOrderForm):
    class Meta(AdminOrderForm.Meta):
        fields = ("student", *AdminOrderForm.Meta.fields)
