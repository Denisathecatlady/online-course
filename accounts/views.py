from django.shortcuts import render

# Create your views here.
from django.conf import settings
from django.urls import reverse

reset_url = settings.SITE_URL + reverse(
    "password_reset_confirm",
    args=[uid, token]
)
