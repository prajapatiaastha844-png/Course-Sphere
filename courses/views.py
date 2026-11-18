from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from accounts.models import Student

from .models import Course


@login_required(login_url="accounts:login")
def course_list(request):
    if not Student.objects.filter(user=request.user).exists():
        raise PermissionDenied

    courses = Course.objects.filter(is_published=True).select_related("instructor")
    return render(request, "courses/course_list.html", {"courses": courses})
