from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.core.mail import EmailMessage
from django.conf import settings
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.utils.timezone import now

import os

from .models import Course, Module, ModuleProgress, CoursePlan
from payments.models import CourseAccess


# ======================================
# ACCESS HELPER
# ======================================

def require_course_access(user, course):
    access = CourseAccess.objects.filter(
        user=user,
        course=course,
        is_active=True
    ).first()

    if not access or not access.has_access():
        raise Http404("Přístup vypršel.")

    return access


# ======================================
# PUBLIC PAGES
# ======================================

@require_GET
def home(request):
    courses = Course.objects.filter(is_active=True)

    plans = (
        CoursePlan.objects
        .filter(is_active=True)
        .select_related("course")
        .order_by("-price")
    )

    return render(request, "courses/home.html", {
        "courses": courses,
        "plans": plans,
    })


@require_GET
def course_detail_public(request, slug):
    course = get_object_or_404(
        Course,
        slug=slug,
        is_active=True
    )

    plans = course.plans.filter(is_active=True)

    return render(request, "courses/course_detail_public.html", {
        "course": course,
        "plans": plans,
    })


def about(request):
    return render(request, "courses/about.html")


def about_us(request):
    return redirect("courses:cemu_se_venujeme")


def cemu_se_venujeme(request):
    return render(request, "courses/cemu_se_venujeme.html")


def nase_filozofie(request):
    return render(request, "courses/nase_filozofie.html")


def moje_vzdelani(request):
    return render(request, "courses/moje_vzdelani.html")


def muj_pribeh(request):
    return render(request, "courses/muj_pribeh.html")


def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()

        if not all([name, email, subject, message]):
            messages.error(request, "Vyplň prosím všechna pole.")
        else:
            recipient = "info@calmdog.cz"
            body = (
                f"Jmeno: {name}\n"
                f"E-mail: {email}\n\n"
                f"Predmet: {subject}\n\n"
                f"Zprava:\n{message}"
            )

            try:
                email_message = EmailMessage(
                    subject=f"Kontakt z webu: {subject}",
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER or recipient,
                    to=[recipient],
                    reply_to=[email],
                )
                email_message.send(fail_silently=False)
                messages.success(request, "Zprava byla odeslana.")
                return redirect("courses:contact")
            except Exception:
                messages.error(request, "Zpravu se nepodarilo odeslat. Zkus prosim e-mail nebo telefon.")

    return render(request, "courses/contact.html")


def trainings(request):
    trainings_data = [
        {
            "title": "Individuální konzultace problémového chování psa",
            "summary": "Porozumění příčině problémového chování a návrh vhodného řešení na míru.",
            "image": "img/individualni-konzultace-problemove-chovani-psa.png",
            "highlights": [
                "Porozumíme příčině problémového chování a navrhneme řešení.",
                "Naučíme se komunikovat se psem.",
                "Uspokojíme potřeby psa.",
            ],
            "duration": "1 h",
            "capacity": "1 pes",
            "price": "1 500 Kč",
        },
        {
            "title": "Psí řeč: konejšivé signály, signály agrese, štěkání",
            "summary": "Trénink zaměřený na čtení psí komunikace a lepší porozumění psím potřebám.",
            "image": "img/psi-rec-konejsive-signaly-agrese-stekani.png",
            "highlights": [
                "Naučíme se pozorovat a rozumět psí komunikaci.",
                "Naučíme se komunikovat se psem.",
                "Uspokojíme psí potřeby.",
            ],
            "duration": "1 h",
            "capacity": "1 pes",
            "price": "1 500 Kč",
        },
        {
            "title": "Chůze na volném vodítku",
            "summary": "Klidnější a funkční procházky bez tahání na vodítku.",
            "image": "img/chuze-na-volnem-voditku.png",
            "highlights": [
                "Naučíme psa netahat na vodítku.",
                "Uspokojíme psí potřeby.",
                "Naučíme se psí řeč.",
            ],
            "duration": "1 h",
            "capacity": "1–4 psi",
            "price": "1 500 Kč",
        },
        {
            "title": "Komunikační / socializační procházky",
            "summary": "Podpora psů, kteří potřebují zvládnout kontakt s jinými psy klidněji.",
            "image": "img/komunikacni-socializacni-prochazky.png",
            "highlights": [
                "Pochopíme příčinu reaktivity na psy.",
                "Pomůžeme psu zvládnout kontakt s ostatními psy.",
                "Naučíme psa těšit se z přítomnosti jiných psů.",
            ],
            "duration": "1 h",
            "capacity": "2–4 psi",
            "price": "1 500 Kč",
        },
        {
            "title": "Socializační aktivity",
            "summary": "Bezpečné seznamování psa s prostředím, které mu dělá potíže.",
            "image": "img/socializacni-aktivity.png",
            "highlights": [
                "Pochopíme příčinu reaktivity a bázlivosti vašeho psa.",
                "Pomůžeme psu zvládnout kontakt s obtížným prostředím.",
                "Vyměníme strach za zvědavost.",
            ],
            "duration": "1 h",
            "capacity": "1–4 psi",
            "price": "1 500 Kč",
        },
        {
            "title": "Aktivity zvyšující sebevědomí psa / snižující stres",
            "summary": "Činnosti, které pomáhají psovi lépe zvládat tlak a budovat jistotu.",
            "image": "img/aktivity-zvysujici-sebevedomi-psa.png",
            "highlights": [
                "Budeme zvyšovat sebevědomí psa a snižovat stres.",
                "Budeme pečovat o psí pohybový aparát.",
                "Naučíme se psí řeč.",
            ],
            "duration": "1 h",
            "capacity": "1–4 psi",
            "price": "1 500 Kč",
        },
    ]

    return render(request, "courses/trainings.html", {
        "trainings": trainings_data,
    })


def gdpr(request):
    return render(request, "courses/gdpr.html")


def privacy_policy(request):
    return render(request, "courses/privacy_policy.html")


def terms(request):
    return render(request, "courses/terms.html")


def cookies_view(request):
    return render(request, "pages/cookies.html")


# ======================================
# COURSE DASHBOARD (PRIVATE)
# ======================================

@login_required
@require_GET
@never_cache
def course_dashboard(request, slug):

    course = get_object_or_404(Course, slug=slug)

    # 🔐 kontrola přístupu včetně expirace
    require_course_access(request.user, course)

    modules = course.modules.all()
    total_modules = modules.count()

    completed_modules = ModuleProgress.objects.filter(
        user=request.user,
        module__in=modules,
        completed=True
    ).count()

    progress_percent = (
        int((completed_modules / total_modules) * 100)
        if total_modules else 0
    )

    return render(request, "courses/course_dashboard.html", {
        "course": course,
        "modules": modules,
        "completed_modules": completed_modules,
        "total_modules": total_modules,
        "progress_percent": progress_percent,
    })


# ======================================
# MODULE DETAIL
# ======================================

@login_required
@require_GET
@never_cache
@xframe_options_sameorigin
def module_detail(request, course_slug, slug):

    course = get_object_or_404(Course, slug=course_slug)

    require_course_access(request.user, course)

    module = get_object_or_404(
        Module,
        course=course,
        slug=slug
    )

    module_progress = ModuleProgress.objects.filter(
        user=request.user,
        module=module
    ).first()

    return render(request, "courses/module_detail.html", {
        "course": course,
        "module": module,
        "module_progress": module_progress,
    })


# ======================================
# PDF DOWNLOAD
# ======================================

@login_required
@require_GET
@never_cache
def download_module_pdf(request, course_slug, slug):

    course = get_object_or_404(Course, slug=course_slug)

    require_course_access(request.user, course)

    module = get_object_or_404(
        Module,
        course=course,
        slug=slug
    )

    if not module.pdf_file:
        raise Http404("PDF není k dispozici.")

    pdf_path = module.pdf_file.path

    if not os.path.exists(pdf_path):
        raise Http404("Soubor nebyl nalezen.")

    return FileResponse(
        open(pdf_path, "rb"),
        as_attachment=True,
        filename=os.path.basename(pdf_path),
        content_type="application/pdf",
    )


# ======================================
# MODULE PROGRESS
# ======================================

@login_required
@require_POST
def toggle_module_completion(request, course_slug, module_id):

    course = get_object_or_404(Course, slug=course_slug)

    require_course_access(request.user, course)

    module = get_object_or_404(
        Module,
        id=module_id,
        course=course
    )

    progress, _ = ModuleProgress.objects.get_or_create(
        user=request.user,
        module=module
    )

    progress.completed = not progress.completed
    progress.completed_at = now() if progress.completed else None
    progress.save()

    return redirect(
        "courses:module_detail",
        course_slug=course.slug,
        slug=module.slug
    )
