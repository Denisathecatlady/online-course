from django.urls import path
from . import views

app_name = "courses"

urlpatterns = [

    # =========================
    # VEŘEJNÉ STRÁNKY
    # =========================
    path("", views.home, name="home"),
    path("treninky/", views.trainings, name="trainings"),
    path("o-nas/", views.about_us, name="about_us"),
    path("cemu-se-venujeme/", views.cemu_se_venujeme, name="cemu_se_venujeme"),
    path("nase-filozofie/", views.nase_filozofie, name="nase_filozofie"),
    path("moje-vzdelani/", views.moje_vzdelani, name="moje_vzdelani"),
    path("muj-pribeh/", views.muj_pribeh, name="muj_pribeh"),
    path("kontakt/", views.contact, name="contact"),
    path("o-kurzu/", views.about, name="about"),

    # =========================
    # DASHBOARD (SOUKROMÉ)
    # =========================
    path(
        "kurz/<slug:slug>/dashboard/",
        views.course_dashboard,
        name="course_dashboard",
    ),

    path(
        "kurz/<slug:course_slug>/modul/<slug:slug>/",
        views.module_detail,
        name="module_detail",
    ),

    path(
        "kurz/<slug:course_slug>/modul/<slug:slug>/pdf/",
        views.download_module_pdf,
        name="download_module_pdf",
    ),

    path(
        "kurz/<slug:course_slug>/modul/<int:module_id>/hotovo/",
        views.toggle_module_completion,
        name="toggle_module_completion",
    ),

    # =========================
    # PRÁVNÍ STRÁNKY
    # =========================
    path("gdpr/", views.gdpr, name="gdpr"),
    path("ochrana-osobnich-udaju/", views.privacy_policy, name="privacy_policy"),
    path("obchodni-podminky/", views.terms, name="terms"),
    path("cookies/", views.cookies_view, name="cookies"),
]
