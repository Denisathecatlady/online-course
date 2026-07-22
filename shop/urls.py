from django.urls import path
from . import views

app_name = "shop"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("heureka.xml", views.heureka_feed, name="heureka_feed"),
    path("postroj-na-miru/", views.postroj_na_miru, name="postroj_na_miru"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
]