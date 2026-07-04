from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from courses.models import ModuleProgress
from payments.models import CourseAccess, Order

from .forms import UserProfileForm
from .models import UserProfile


@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = UserProfileForm(
            request.POST,
            instance=profile,
            user=request.user,
        )
        if form.is_valid():
            form.save()
            return redirect("accounts:profile")
    else:
        form = UserProfileForm(
            instance=profile,
            user=request.user,
        )

    return render(request, "accounts/profile.html", {
        "form": form,
        "account_section": "profile",
    })


@login_required
def order_history(request):
    orders = Order.objects.filter(
        user=request.user,
        status=Order.Status.PAID,
    ).order_by("-created_at")

    # Označíme objednávky, u kterých ještě běží 14denní lhůta pro vrácení
    cutoff = timezone.now() - timedelta(days=14)
    for order in orders:
        paid_date = order.paid_at or order.created_at
        order.can_withdraw = paid_date >= cutoff

    return render(request, "accounts/order_history.html", {
        "orders": orders,
        "account_section": "orders",
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order,
        pk=pk,
        user=request.user,
    )

    return render(request, "accounts/order_detail.html", {
        "order": order,
        "account_section": "orders",
    })


@login_required
def my_courses(request):
    accesses = list(CourseAccess.objects.filter(
        user=request.user,
        is_active=True,
    ).select_related("course", "plan").prefetch_related("course__modules"))

    course_module_map = {
        access.course_id: list(access.course.modules.all())
        for access in accesses
    }
    all_module_ids = [
        module.id
        for modules in course_module_map.values()
        for module in modules
    ]
    completed_progresses = list(
        ModuleProgress.objects.filter(
            user=request.user,
            module_id__in=all_module_ids,
            completed=True,
        ).select_related("module")
    )
    progress_by_module_id = {
        progress.module_id: progress
        for progress in completed_progresses
    }
    progress_by_course_id = defaultdict(list)
    for progress in completed_progresses:
        progress_by_course_id[progress.module.course_id].append(progress)

    for access in accesses:
        modules = course_module_map.get(access.course_id, [])

        completed_modules = sum(1 for module in modules if progress_by_module_id.get(module.id))
        total_modules = len(modules)
        access.completed_modules = completed_modules
        access.total_modules = total_modules
        access.progress_percent = int((completed_modules / total_modules) * 100) if total_modules else 0
        access.is_started = completed_modules > 0
        access.cta_label = "Pokračovat" if access.is_started else "Začít kurz"
        access.plan_label = access.plan.name if access.plan else "Původní přístup"
        access.duration_weeks = (
            max(1, access.plan.access_duration_days // 7)
            if access.plan and access.plan.access_duration_days
            else None
        )

        last_completed = None
        for module_progress in progress_by_course_id.get(access.course_id, []):
            if last_completed is None or module_progress.completed_at > last_completed.completed_at:
                last_completed = module_progress

        if last_completed:
            last_module = next((module for module in modules if module.id == last_completed.module_id), None)
            access.status_text = (
                f"Poslední: Lekce {last_module.order} — {last_module.title}"
                if last_module else "Pokračujete v kurzu"
            )
        else:
            access.status_text = "Nezahájeno"

    return render(request, "accounts/my_courses.html", {
        "accesses": accesses,
        "account_section": "courses",
        "hide_account_sidebar": True,
        "hide_site_navbar": True,
        "hide_site_footer": True,
    })
