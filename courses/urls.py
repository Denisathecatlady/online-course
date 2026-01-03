from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("o-kurzu/", views.about, name="about"),
    path("kurz/", views.course_dashboard, name="course_dashboard"),
    path("kurz/modul/<slug:slug>/", views.module_detail, name="module_detail"),
    path("kurz/modul/<slug:slug>/pdf/", views.download_module_pdf, name="download_module_pdf"),
]
