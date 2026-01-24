from .models import CoursePlan, Order, CourseAccess
from django.urls import path
from django.utils.html import format_html
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from .models import Order



@admin.register(CoursePlan)
class CoursePlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price_czk",
        "includes_consultation",
        "includes_certificate",
        "is_active",
    )
    list_filter = (
        "is_active",
        "includes_consultation",
        "includes_certificate",
    )
    search_fields = ("name", "code")
    prepopulated_fields = {"code": ("name",)}


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "buyer_email",
        "status",
        "invoice_number",
        "invoice_download",
        "created_at",
    )

    readonly_fields = ("created_at",)

    def invoice_download(self, obj):
        if not obj.invoice_pdf:
            return "—"

        url = reverse("admin:order-invoice-download", args=[obj.pk])
        return format_html('<a href="{}">Stáhnout PDF</a>', url)

    invoice_download.short_description = "Faktura"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "invoice/<int:pk>/",
                self.admin_site.admin_view(self.download_invoice),
                name="order-invoice-download",
            )
        ]
        return custom_urls + urls

    def download_invoice(self, request, pk):
        order = self.get_object(request, pk)

        if not order or not order.invoice_pdf:
            raise Http404("Faktura nenalezena")

        return FileResponse(
            order.invoice_pdf.open("rb"),
            as_attachment=True,
            filename=f"faktura_{order.invoice_number}.pdf",
        )


@admin.register(CourseAccess)
class CourseAccessAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "course",
        "plan",
        "is_active",
        "granted_at",
    )
    list_filter = ("is_active", "plan")
    search_fields = (
        "user__email",
        "user__username",
    )
