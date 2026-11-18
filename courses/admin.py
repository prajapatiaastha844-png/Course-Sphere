from django.contrib import admin

from .models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "instructor", "price", "level", "is_published")
    list_filter = ("category", "level", "is_published")
    search_fields = ("title", "category", "description")
