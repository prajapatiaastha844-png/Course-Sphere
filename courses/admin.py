from django.contrib import admin

from .models import Cart, Course, Order


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "instructor", "price", "level", "is_published")
    list_filter = ("category", "level", "is_published")
    search_fields = ("title", "category", "description")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "quantity")
    list_filter = ("course",)
    search_fields = ("student__name", "student__email", "course__title")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "total_amount", "currency", "status", "razorpay_order_id", "created_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("student__name", "student__email", "razorpay_order_id", "razorpay_payment_id")
