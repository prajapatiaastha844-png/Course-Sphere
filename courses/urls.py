from django.urls import path

from . import views


app_name = "courses"

urlpatterns = [
    path("", views.course_list, name="course_list"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("payment/callback/", views.payment_callback, name="payment_callback"),
    path("order/<int:pk>/success/", views.order_success, name="order_success"),
    path("<int:pk>/add-to-cart/", views.add_to_cart, name="add_to_cart"),
    path("<int:pk>/remove-from-cart/", views.remove_course_from_cart, name="remove_course_from_cart"),
    path("cart/<int:pk>/remove/", views.remove_from_cart, name="remove_from_cart"),
    path("instructor/dashboard/", views.instructor_dashboard, name="instructor_dashboard"),
    path("add/", views.add_course, name="add_course"),
    path("<int:pk>/edit/", views.edit_course, name="edit_course"),
    path("<int:pk>/delete/", views.delete_course, name="delete_course"),
    path("<int:pk>/", views.course_detail, name="course_detail"),
]
