from django.contrib import admin
from .models import CoursePlan, Order, CourseAccess
from django.urls import path
from django.utils.html import format_html
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse




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
        "user",
        "course",
        "plan",
        "status",
        "invoice_download",   # ⬅️ PŘIDÁNO
        "created_at",
        "newsletter_opt_in",
    )

    list_filter = ("status", "plan", "newsletter_opt_in")

    search_fields = (
        "user__email",
        "user__username",
        "stripe_checkout_session_id",
    )

    readonly_fields = (
        "stripe_checkout_session_id",
        "created_at",
    )

    # 🔽 ODKAZ VE SLOUPCI
    def invoice_download(self, obj):
        if not obj.invoice_pdf:
            return "—"

        url = reverse("admin:order-invoice-download", args=[obj.pk])
        return format_html('<a href="{}">Stáhnout PDF</a>', url)


    # 🔽 ADMIN URL
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

    # 🔽 VLASTNÍ ADMIN VIEW
    def download_invoice(self, request, pk):
        order = get_object_or_404(Order, pk=pk)

        if not order.invoice_pdf:
            raise Http404("Faktura neexistuje")

        return FileResponse(
            order.invoice_pdf.open("rb"),
            as_attachment=True,
            filename=f"faktura_{order.invoice_number or order.pk}.pdf",
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
