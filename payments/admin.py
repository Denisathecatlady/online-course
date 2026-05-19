from django.contrib import admin, messages
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from django.http import FileResponse, Http404, HttpResponse
from django.core.files.base import ContentFile

from .models import Order, OrderItem, CourseAccess
from .services.packeta import create_packet, get_packet_label_pdf, PacketaError


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
        "packeta_packet_id",
        "packeta_tracking_number",
        "packeta_label_link",
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
        "packeta_label_link",
        "invoice_download",
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
    actions = ["retry_packeta_shipment", "retry_packeta_label"]

    # ── Faktura ────────────────────────────────────────────

    def invoice_download(self, obj):
        if not obj.invoice_pdf:
            return "—"
        url = reverse("admin:order-invoice-download", args=[obj.pk])
        return format_html('<a href="{}">📄 Stáhnout</a>', url)

    invoice_download.short_description = "Faktura"

    # ── Packeta štítek ─────────────────────────────────────

    def packeta_label_link(self, obj):
        if not obj.packeta_label_pdf:
            if obj.packeta_packet_id:
                return format_html('<em style="color:#aaa">Bez štítku</em>')
            return "—"
        url = reverse("admin:order-packeta-label-download", args=[obj.pk])
        return format_html('<a href="{}">🏷 Štítek PDF</a>', url)

    packeta_label_link.short_description = "Štítek"

    # ── URL ────────────────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "invoice/<int:pk>/",
                self.admin_site.admin_view(self.download_invoice),
                name="order-invoice-download",
            ),
            path(
                "packeta-label/<int:pk>/",
                self.admin_site.admin_view(self.download_packeta_label),
                name="order-packeta-label-download",
            ),
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

    def download_packeta_label(self, request, pk):
        order = self.get_object(request, pk)
        if not order or not order.packeta_label_pdf:
            raise Http404("Štítek nenalezen")
        return FileResponse(
            order.packeta_label_pdf.open("rb"),
            as_attachment=True,
            filename=f"label_packeta_{order.id}.pdf",
        )

    # ── Akce – opakovat vytvoření zásilky ─────────────────

    @admin.action(description="🔄 Opakovat vytvoření zásilky (Packeta)")
    def retry_packeta_shipment(self, request, queryset):
        success = 0
        skipped = 0
        failed = 0

        for order in queryset:
            if order.shipping_method != Order.ShippingMethod.ZASILKOVNA:
                skipped += 1
                continue
            if order.packeta_packet_id:
                # Zásilka již existuje, přeskočíme (stačí retry_label)
                skipped += 1
                continue
            try:
                shipment = create_packet(order)
                order.packeta_packet_id = shipment["packet_id"]
                order.packeta_tracking_number = shipment["tracking_number"]
                order.packeta_created_at = timezone.now()
                order.save(update_fields=[
                    "packeta_packet_id",
                    "packeta_tracking_number",
                    "packeta_created_at",
                ])
                # Ihned stáhnout štítek
                try:
                    pdf = get_packet_label_pdf(order.packeta_packet_id)
                    order.packeta_label_pdf.save(
                        f"label_packeta_{order.id}.pdf",
                        ContentFile(pdf),
                        save=True,
                    )
                except Exception:
                    pass  # štítek se stáhne zvlášť
                success += 1
            except PacketaError as e:
                self.message_user(
                    request,
                    f"Objednávka #{order.id}: Packeta chyba [{e.code}] {e.message}",
                    level=messages.ERROR,
                )
                failed += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Objednávka #{order.id}: Neočekávaná chyba – {e}",
                    level=messages.ERROR,
                )
                failed += 1

        if success:
            self.message_user(
                request,
                f"✅ Zásilky vytvořeny: {success}",
                level=messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f"⏭ Přeskočeno (nejedná se o Zásilkovnu nebo zásilka již existuje): {skipped}",
                level=messages.WARNING,
            )

    # ── Akce – stáhnout štítek ────────────────────────────

    @admin.action(description="🏷 Stáhnout/obnovit štítek ze Zásilkovny")
    def retry_packeta_label(self, request, queryset):
        success = 0
        skipped = 0
        failed = 0

        for order in queryset:
            if not order.packeta_packet_id:
                skipped += 1
                continue
            try:
                pdf = get_packet_label_pdf(order.packeta_packet_id)
                order.packeta_label_pdf.save(
                    f"label_packeta_{order.id}.pdf",
                    ContentFile(pdf),
                    save=True,
                )
                success += 1
            except PacketaError as e:
                self.message_user(
                    request,
                    f"Objednávka #{order.id}: Packeta chyba [{e.code}] {e.message}",
                    level=messages.ERROR,
                )
                failed += 1
            except ValueError as e:
                self.message_user(
                    request,
                    f"Objednávka #{order.id}: {e}",
                    level=messages.WARNING,
                )
                skipped += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Objednávka #{order.id}: Chyba při stahování štítku – {e}",
                    level=messages.ERROR,
                )
                failed += 1

        if success:
            self.message_user(
                request,
                f"✅ Štítky staženy: {success}",
                level=messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f"⏭ Přeskočeno (chybí packet_id nebo MOCK režim): {skipped}",
                level=messages.WARNING,
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
        "bypass_module_sequencing",
        "granted_at",
    )
    list_filter = ("is_active", "bypass_module_sequencing", "plan")
    search_fields = (
        "user__email",
        "user__username",
    )
