from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from .models import Course, Module
from payments.models import CoursePlan
from .models import Course


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


@require_GET
@login_required
@never_cache
def course_dashboard(request):
    course = Course.objects.first()
    modules = course.modules.all() if course else []
    return render(request, "courses/course_dashboard.html", {"course": course, "modules": modules})


@require_GET
@login_required
@never_cache
@xframe_options_sameorigin  # povolí iframe jen ze stejného webu (vimeo iframe je uvnitř stránky, to je ok)
def module_detail(request, slug):
    # Bezpečnější: modul v rámci konkrétního kurzu (když bys někdy měla víc kurzů)
    course = Course.objects.first()
    if not course:
        raise Http404("Kurz neexistuje.")

    module = get_object_or_404(Module, course=course, slug=slug)
    return render(request, "courses/module_detail.html", {"course": course, "module": module})


@require_GET
@never_cache
@login_required
def download_module_pdf(request, slug):
    course = Course.objects.first()
    if not course:
        raise Http404("Kurz neexistuje.")

    module = get_object_or_404(Module, course=course, slug=slug)

    if not module.pdf_file:
        raise Http404("PDF není k dispozici.")

    # Signed URL (krátkodobě platná), soubor je v bucketu private
    return redirect(module.pdf_file.url)




def gdpr(request):
    return render(request, "courses/gdpr.html")

def privacy_policy(request):
    return render(request, "courses/privacy_policy.html")

def terms(request):
    return render(request, "courses/terms.html")
