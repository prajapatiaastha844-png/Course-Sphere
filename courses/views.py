from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from accounts.models import Student

from .models import Course


@login_required(login_url="accounts:login")
def course_list(request):
    if not Student.objects.filter(user=request.user).exists():
        raise PermissionDenied

    search_query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()
    selected_level = request.GET.get("level", "").strip()
    courses = Course.objects.filter(is_published=True)
    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query) | Q(category__icontains=search_query)
        )
    if selected_category:
        courses = courses.filter(category=selected_category)
    if selected_level:
        courses = courses.filter(level=selected_level)

    courses = courses.select_related("instructor")
    page_obj = Paginator(courses, 9).get_page(request.GET.get("page"))
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    return render(
        request,
        "courses/course_list.html",
        {
            "courses": page_obj,
            "page_obj": page_obj,
            "search_query": search_query,
            "categories": Course.objects.filter(is_published=True)
            .order_by("category")
            .values_list("category", flat=True)
            .distinct(),
            "levels": Course.Level.choices,
            "selected_category": selected_category,
            "selected_level": selected_level,
            "pagination_query": pagination_params.urlencode(),
        },
    )


@login_required(login_url="accounts:login")
def course_detail(request, pk):
    if not Student.objects.filter(user=request.user).exists():
        raise PermissionDenied

    course = get_object_or_404(
        Course.objects.select_related("instructor"),
        pk=pk,
        is_published=True,
    )
    return render(request, "courses/course_detail.html", {"course": course})
