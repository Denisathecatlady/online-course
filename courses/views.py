from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from .models import Course, Module
from payments.models import CoursePlan
from .models import Course
from django.shortcuts import render
from django.http import FileResponse
import os
from django.utils.timezone import now
from django.shortcuts import redirect, get_object_or_404
from courses.models import Module, ModuleProgress
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from courses.models import Module, ModuleProgress



@require_GET
def home(request):
    course = Course.objects.first()

    plans = (
        CoursePlan.objects
        .filter(is_active=True)
        .order_by("-id")  # nebo "price_czk" – viz níže
    )

    return render(request, "courses/home.html", {"course": course, "plans": plans})

@require_GET
def about(request):
    course = Course.objects.first()
    return render(request, "courses/about.html", {"course": course})



@login_required
@require_GET
@never_cache
def course_dashboard(request):
    course = Course.objects.first()
    modules = course.modules.all() if course else []

    total_modules = modules.count()

    completed_modules = ModuleProgress.objects.filter(
        user=request.user,
        module__in=modules,
        completed=True
    ).count()

    progress_percent = int((completed_modules / total_modules) * 100) if total_modules else 0

    return render(request, "courses/course_dashboard.html", {
        "course": course,
        "modules": modules,
        "completed_modules": completed_modules,
        "total_modules": total_modules,
        "progress_percent": progress_percent,
    })


@require_GET
@login_required
@never_cache
@xframe_options_sameorigin  # povolí iframe jen ze stejného webu (vimeo iframe je uvnitř stránky, to je ok)
def module_detail(request, slug):
    course = Course.objects.first()
    if not course:
        raise Http404("Kurz neexistuje.")

    module = get_object_or_404(Module, course=course, slug=slug)

    module_progress = ModuleProgress.objects.filter(
        user=request.user,
        module=module
    ).first()

    return render(request, "courses/module_detail.html", {
        "course": course,
        "module": module,
        "module_progress": module_progress,
    })



@require_GET
@login_required
@never_cache
def download_module_pdf(request, slug):
    course = Course.objects.first()
    if not course:
        raise Http404("Kurz neexistuje.")

    module = get_object_or_404(Module, course=course, slug=slug)

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


def gdpr(request):
    return render(request, "courses/gdpr.html")

def privacy_policy(request):
    return render(request, "courses/privacy_policy.html")

def terms(request):
    return render(request, "courses/terms.html")



def cookies_view(request):
    return render(request, "pages/cookies.html")




@login_required
@require_POST
def toggle_module_completion(request, module_id):
    module = get_object_or_404(Module, id=module_id)

    progress, created = ModuleProgress.objects.get_or_create(
        user=request.user,
        module=module
    )

    progress.completed = not progress.completed
    progress.completed_at = now() if progress.completed else None
    progress.save()

    return redirect("module_detail", slug=module.slug)
