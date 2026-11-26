from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import EmailAuthenticationForm
from . import views


app_name = "accounts"

urlpatterns = [
    path("register/<str:role>/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            authentication_form=EmailAuthenticationForm,
            template_name="accounts/login.html",
            next_page="accounts:dashboard",
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="accounts:login"),
        name="logout",
    ),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("reset-password/", views.reset_password, name="reset_password"),
    path(
        "admin/<str:section>/",
        views.admin_section,
        name="admin_section",
    ),
    path(
        "admin/<str:section>/add/",
        views.admin_add,
        name="admin_add",
    ),
    path(
        "admin/<str:section>/<int:pk>/",
        views.admin_record,
        {"action": "view"},
        name="admin_record",
    ),
    path(
        "admin/<str:section>/<int:pk>/edit/",
        views.admin_record,
        {"action": "edit"},
        name="admin_record_edit",
    ),
    path(
        "admin/<str:section>/<int:pk>/delete/",
        views.admin_record,
        {"action": "delete"},
        name="admin_record_delete",
    ),
    path("dashboard/", views.dashboard, name="dashboard"),
]
