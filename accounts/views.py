from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

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
    accesses = CourseAccess.objects.filter(
        user=request.user,
        is_active=True,
    ).select_related("course", "plan")

    return render(request, "accounts/my_courses.html", {
        "accesses": accesses,
        "account_section": "courses",
        "hide_account_sidebar": True,
    })
