from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from courses.models import ModuleProgress
from payments.models import CourseAccess, NewsletterSubscriber, Order
from trainings.models import TrainingReservation

from .forms import UserProfileForm, DogForm, UserNotificationsForm
from .models import UserProfile, Dog
from .breeds import DOG_BREEDS


@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    return render(request, "accounts/profile.html", {
        "profile": profile,
        "account_section": "profile",
    })


@login_required
def profile_edit(request):
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

    return render(request, "accounts/profile_edit.html", {
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


# ======================================================================
# REDESIGN 2026 – nové sekce dashboardu
# ======================================================================

def _accesses_with_progress(user):
    """Aktivní přístupy uživatele s dopočítaným průběhem studia."""
    accesses = list(
        CourseAccess.objects.filter(user=user, is_active=True)
        .select_related("course", "plan")
        .prefetch_related("course__modules")
    )
    all_module_ids = [
        module.id for access in accesses for module in access.course.modules.all()
    ]
    completed_ids = set(
        ModuleProgress.objects.filter(
            user=user, module_id__in=all_module_ids, completed=True
        ).values_list("module_id", flat=True)
    )
    for access in accesses:
        modules = list(access.course.modules.all())
        total = len(modules)
        done = sum(1 for module in modules if module.id in completed_ids)
        access.total_modules = total
        access.completed_modules = done
        access.progress_percent = int((done / total) * 100) if total else 0
        access.is_started = done > 0
        access.is_completed = total > 0 and done == total
        access.cta_label = "Pokračovat" if access.is_started else "Začít kurz"
    return accesses


def _render_placeholder(request, section, title, eyebrow="Účet", copy=None):
    """Dočasná výplň pro sekce, které se teprve implementují."""
    return render(request, "accounts/_section_placeholder.html", {
        "account_section": section,
        "section_title": title,
        "section_eyebrow": eyebrow,
        "section_copy": copy,
    })


@login_required
def overview(request):
    accesses = _accesses_with_progress(request.user)
    stats = {
        "purchased": len(accesses),
        "active": sum(1 for access in accesses if access.has_access()),
        "completed": sum(1 for access in accesses if access.is_completed),
        "orders": Order.objects.filter(
            user=request.user, status=Order.Status.PAID
        ).count(),
        "upcoming_trainings": TrainingReservation.objects.filter(
            user=request.user,
            status=TrainingReservation.Status.CONFIRMED,
            slot__start__gt=timezone.now(),
        ).count(),
    }
    return render(request, "accounts/overview.html", {
        "account_section": "overview",
        "stats": stats,
        "recent_courses": accesses[:3],
    })


def _dog_age_years(dog):
    from datetime import date

    if not dog.birth_date:
        return None
    today = date.today()
    return (
        today.year
        - dog.birth_date.year
        - ((today.month, today.day) < (dog.birth_date.month, dog.birth_date.day))
    )


@login_required
def dogs(request):
    dogs_list = list(request.user.dogs.all())
    for dog in dogs_list:
        dog.age_years = _dog_age_years(dog)
    return render(request, "accounts/dogs.html", {
        "account_section": "dogs",
        "dogs": dogs_list,
    })


@login_required
def dog_add(request):
    if request.method == "POST":
        form = DogForm(request.POST, request.FILES)
        if form.is_valid():
            dog = form.save(commit=False)
            dog.owner = request.user
            dog.save()
            return redirect("accounts:dogs")
    else:
        form = DogForm()

    return render(request, "accounts/dog_form.html", {
        "account_section": "dogs",
        "form": form,
        "dog_breeds": DOG_BREEDS,
        "is_new": True,
    })


@login_required
def dog_edit(request, pk):
    dog = get_object_or_404(Dog, pk=pk, owner=request.user)

    if request.method == "POST":
        form = DogForm(request.POST, request.FILES, instance=dog)
        if form.is_valid():
            form.save()
            return redirect("accounts:dogs")
    else:
        form = DogForm(instance=dog)

    return render(request, "accounts/dog_form.html", {
        "account_section": "dogs",
        "form": form,
        "dog_breeds": DOG_BREEDS,
        "dog": dog,
        "is_new": False,
    })


@login_required
def dog_delete(request, pk):
    dog = get_object_or_404(Dog, pk=pk, owner=request.user)

    if request.method == "POST":
        dog.delete()

    return redirect("accounts:dogs")


@login_required
def reservations(request):
    # Rezervace tréninků z appky `trainings`.
    reservations_qs = list(
        TrainingReservation.objects.filter(user=request.user).select_related(
            "slot", "slot__location", "slot__trainer"
        )
    )
    now = timezone.now()
    upcoming = sorted(
        (
            r for r in reservations_qs
            if r.status == TrainingReservation.Status.CONFIRMED and r.slot.start > now
        ),
        key=lambda r: r.slot.start,
    )
    history = sorted(
        (
            r for r in reservations_qs
            if r.slot.start <= now and r.status != TrainingReservation.Status.CANCELED
        ),
        key=lambda r: r.slot.start,
        reverse=True,
    )
    return render(request, "accounts/reservations.html", {
        "account_section": "reservations",
        "upcoming": upcoming,
        "history": history,
    })


@login_required
def courses_overview(request):
    return render(request, "accounts/courses.html", {
        "account_section": "courses",
        "accesses": _accesses_with_progress(request.user),
    })


@login_required
def invoices(request):
    orders = (
        Order.objects.filter(user=request.user, status=Order.Status.PAID)
        .exclude(invoice_pdf="")
        .exclude(invoice_pdf=None)
        .order_by("-created_at")
    )
    return render(request, "accounts/invoices.html", {
        "account_section": "invoices",
        "orders": orders,
    })


@login_required
def download_invoice(request, pk):
    from payments.services.invoice import generate_invoice_pdf

    order = get_object_or_404(Order, pk=pk, user=request.user)

    if not order.invoice_number:
        raise Http404("Faktura není k dispozici.")

    # Soubor mohl být smazán (ephemeral filesystem na Renderu) → vygeneruj znovu
    file_missing = (
        not order.invoice_pdf
        or not order.invoice_pdf.storage.exists(order.invoice_pdf.name)
    )
    if file_missing:
        invoice_file = generate_invoice_pdf(order)
        order.invoice_pdf.save(invoice_file.name, invoice_file, save=True)

    return FileResponse(
        order.invoice_pdf.open("rb"),
        as_attachment=True,
        filename=f"faktura_{order.invoice_number}.pdf",
    )


@login_required
def account_settings(request):
    # E-mail a heslo spravuje allauth (account_email / account_change_password),
    # telefon a adresy profil, oznámení a souhlasy vlastní stránka `notifications`.
    return render(request, "accounts/settings.html", {
        "account_section": "settings",
    })


def _sync_newsletter_from_consent(user, profile):
    email = (user.email or "").strip().lower()
    if not email:
        return
    if profile.marketing_consent:
        NewsletterSubscriber.objects.update_or_create(
            email=email,
            defaults={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_subscribed": True,
                "source": "account_settings",
            },
        )
    else:
        NewsletterSubscriber.objects.filter(email=email).update(is_subscribed=False)


@login_required
def notifications(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = UserNotificationsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            _sync_newsletter_from_consent(request.user, profile)
            return redirect("accounts:notifications")
    else:
        form = UserNotificationsForm(instance=profile)
    return render(request, "accounts/notifications.html", {
        "form": form,
        "profile": profile,
        "account_section": "notifications",
    })
