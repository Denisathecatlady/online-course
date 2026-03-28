from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.http import FileResponse, Http404
from .models import Order, OrderItem, CourseAccess


# ======================================
# ORDER
# ======================================

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product_variant",
        "course_plan",
        "quantity",
        "price_at_purchase",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "buyer_email",
        "status",
        "shipping_method",
        "packeta_point_name",
        "packeta_tracking_number",
        "invoice_number",
        "invoice_download",
        "created_at",
    )

    list_filter = ("status", "shipping_method")
    readonly_fields = (
        "created_at",
        "packeta_packet_id",
        "packeta_tracking_number",
        "packeta_created_at",
    )
    search_fields = (
        "buyer_email",
        "first_name",
        "last_name",
        "packeta_point_name",
        "packeta_packet_id",
        "packeta_tracking_number",
    )
    inlines = [OrderItemInline]

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


# ======================================
# ORDER ITEM
# ======================================

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "product_variant",
        "course_plan",
        "quantity",
        "price_at_purchase",
    )


# ======================================
# COURSE ACCESS
# ======================================

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
