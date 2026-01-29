from django.shortcuts import render

# Create your views here.
from django.conf import settings
from django.urls import reverse

reset_path = reverse(
    "password_reset_confirm",
    kwargs={"uidb64": uid, "token": token}
)

reset_url = f"{settings.SITE_URL}{reset_path}"

