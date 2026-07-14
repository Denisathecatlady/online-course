from django.contrib import admin, messages
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from django.http import FileResponse, Http404

from django.core.files.base import ContentFile

from import_export import resources, fields
from import_export.admin import ExportMixin
from rangefilter.filters import DateRangeFilter

from .models import Order, OrderItem, CourseAccess, Coupon, CouponUsage, ShopSettings, WelcomeCouponClaim, NewsletterSubscriber
from .services.packeta import create_packet, get_packet_label_pdf, PacketaError


# ======================================
# EXPORT – přehledné sloupce pro Excel/CSV
# ======================================

class OrderResource(resources.ModelResource):
    stav = fields.Field(column_name="Stav")
    zbozi = fields.Field(column_name="Zboží (Kč)")
    sleva = fields.Field(attribute="discount_amount", column_name="Sleva (Kč)")
    doprava = fields.Field(attribute="shipping_price", column_name="Doprava (Kč)")
    celkem = fields.Field(column_name="Celkem (Kč)")
    kupon = fields.Field(column_name="Kupón")

    class Meta:
        model = Order
        fields = (
            "id", "created_at", "stav", "buyer_email", "first_name", "last_name",
            "phone", "zbozi", "sleva", "doprava", "celkem", "kupon",
            "shipping_method", "invoice_number",
        )
        export_order = fields

    def dehydrate_stav(self, obj):
        return obj.get_status_display()

    def dehydrate_zbozi(self, obj):
        return obj.items_total

    def dehydrate_celkem(self, obj):
        return obj.total_price

    def dehydrate_kupon(self, obj):
        return obj.coupon.code if obj.coupon else ""


class CourseAccessResource(resources.ModelResource):
    zakaznik = fields.Field(column_name="Zákazník")
    kurz = fields.Field(column_name="Kurz")
    varianta = fields.Field(column_name="Varianta")

    class Meta:
        model = CourseAccess
        fields = ("id", "zakaznik", "kurz", "varianta", "is_active", "granted_at", "expires_at")
        export_order = fields

    def dehydrate_zakaznik(self, obj):
        return obj.user.email if obj.user else ""

    def dehydrate_kurz(self, obj):
        return obj.course.title if obj.course else ""

    def dehydrate_varianta(self, obj):
        return obj.plan.name if obj.plan else ""


class CouponUsageResource(resources.ModelResource):
    kupon = fields.Field(column_name="Kupón")
    zakaznik = fields.Field(column_name="Zákazník")

    class Meta:
        model = CouponUsage
        fields = ("id", "kupon", "zakaznik", "order", "discount_amount", "used_at")
        export_order = fields


class NewsletterSubscriberResource(resources.ModelResource):
    class Meta:
        model = NewsletterSubscriber
        fields = ("email", "first_name", "last_name", "is_subscribed", "source", "created_at")
        export_order = fields

    def dehydrate_kupon(self, obj):
        return obj.coupon.code if obj.coupon else ""

    def dehydrate_zakaznik(self, obj):
        return obj.user.email if obj.user else ""


# ======================================
# POMOCNÉ – barevné štítky stavů
# ======================================

ORDER_STATUS_COLORS = {
    Order.Status.CART: "#9e9e9e",
    Order.Status.PENDING: "#e0a800",
    Order.Status.PAID: "#2e7d32",
    Order.Status.FAILED: "#c62828",
    Order.Status.CANCELED: "#616161",
}


def _badge(text, color):
    return format_html(
        '<span style="background:{};color:#fff;padding:2px 8px;'
        'border-radius:10px;font-size:11px;white-space:nowrap;">{}</span>',
        color,
        text,
    )


# ======================================
# ORDER – položky jako inline
# ======================================

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    verbose_name = "Položka objednávky"
    verbose_name_plural = "Položky objednávky"
    fields = ("product_variant", "course_plan", "quantity", "price_at_purchase", "subtotal_display")
    readonly_fields = (
        "product_variant",
        "course_plan",
        "quantity",
        "price_at_purchase",
        "subtotal_display",
    )

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Mezisoučet")
    def subtotal_display(self, obj):
        if obj.pk:
            return f"{obj.subtotal:.0f} Kč"
        return "—"


@admin.register(Order)
class OrderAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = OrderResource
    list_display = (
        "order_number",
        "customer_display",
        "status_badge",
        "payment_badge",
        "total_display",
        "shipping_method",
        "created_at",
        "invoice_download",
        "packeta_label_link",
    )
    list_filter = ("status", "shipping_method", ("created_at", DateRangeFilter))
    date_hierarchy = "created_at"
    search_fields = (
        "id",
        "buyer_email",
        "first_name",
        "last_name",
        "invoice_number",
        "coupon__code",
        "packeta_point_name",
        "packeta_packet_id",
        "packeta_tracking_number",
    )
    ordering = ("-created_at",)
    autocomplete_fields = ("user", "coupon")
    inlines = [OrderItemInline]
    actions = [
        "mark_as_paid",
        "mark_as_canceled",
        "retry_packeta_shipment",
        "retry_packeta_label",
    ]

    readonly_fields = (
        "created_at",
        "items_total_display",
        "discount_display",
        "total_display",
        "packeta_packet_id",
        "packeta_tracking_number",
        "packeta_created_at",
        "packeta_label_link",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "invoice_download",
    )

    fieldsets = (
        ("Stav objednávky", {
            "fields": ("status", "user", "created_at"),
        }),
        ("Souhrn ceny", {
            "fields": ("items_total_display", "coupon", "discount_display", "shipping_price", "total_display"),
        }),
        ("Kontakt", {
            "fields": ("buyer_email", "first_name", "last_name", "phone", "newsletter_opt_in"),
        }),
        ("Doručovací adresa", {
            "fields": ("street", "city", "zip_code", "country"),
        }),
        ("Fakturační adresa", {
            "classes": ("collapse",),
            "fields": ("invoice_name", "invoice_street", "invoice_city", "invoice_zip", "invoice_country"),
        }),
        ("Doprava", {
            "fields": ("shipping_method", "stock_reduced"),
        }),
        ("Zásilkovna / Packeta", {
            "classes": ("collapse",),
            "fields": (
                "packeta_point_name", "packeta_point_id",
                "packeta_packet_id", "packeta_tracking_number",
                "packeta_created_at", "packeta_label_link",
            ),
        }),
        ("Platba (Stripe)", {
            "classes": ("collapse",),
            "fields": ("stripe_checkout_session_id", "stripe_payment_intent_id"),
        }),
        ("Faktura", {
            "fields": ("invoice_number", "invoice_download"),
        }),
    )

    # ── Přehledové sloupce ─────────────────────────────────

    @admin.display(description="Objednávka", ordering="id")
    def order_number(self, obj):
        return f"#{obj.pk}"

    @admin.display(description="Zákazník")
    def customer_display(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        if name and obj.buyer_email:
            return format_html("{}<br><small style='color:#777'>{}</small>", name, obj.buyer_email)
        return obj.buyer_email or name or "—"

    @admin.display(description="Stav")
    def status_badge(self, obj):
        return _badge(obj.get_status_display(), ORDER_STATUS_COLORS.get(obj.status, "#777"))

    @admin.display(description="Platba")
    def payment_badge(self, obj):
        if obj.status == Order.Status.PAID:
            return _badge("Zaplaceno", "#2e7d32")
        if obj.status == Order.Status.PENDING:
            return _badge("Čeká na platbu", "#e0a800")
        if obj.status == Order.Status.FAILED:
            return _badge("Neúspěšná", "#c62828")
        return _badge("Nezaplaceno", "#9e9e9e")

    @admin.display(description="Mezisoučet zboží")
    def items_total_display(self, obj):
        return f"{obj.items_total:.0f} Kč"

    @admin.display(description="Sleva")
    def discount_display(self, obj):
        if obj.discount_amount and obj.discount_amount > 0:
            label = obj.coupon.code if obj.coupon else "sleva"
            return format_html('<span style="color:#2e7d32;">− {} Kč ({})</span>', f"{obj.discount_amount:.0f}", label)
        return "—"

    @admin.display(description="Celkem k úhradě")
    def total_display(self, obj):
        return format_html("<strong>{} Kč</strong>", f"{obj.total_price:.0f}")

    # ── Faktura ────────────────────────────────────────────

    @admin.display(description="Faktura")
    def invoice_download(self, obj):
        if not obj.invoice_pdf:
            return "—"
        url = reverse("admin:order-invoice-download", args=[obj.pk])
        return format_html('<a href="{}">📄 Stáhnout</a>', url)

    # ── Packeta štítek ─────────────────────────────────────

    @admin.display(description="Štítek")
    def packeta_label_link(self, obj):
        if not obj.packeta_label_pdf:
            if obj.packeta_packet_id:
                return format_html('<em style="color:#aaa">Bez štítku</em>')
            return "—"
        url = reverse("admin:order-packeta-label-download", args=[obj.pk])
        return format_html('<a href="{}">🏷 Štítek PDF</a>', url)

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
        from .services.invoice import generate_invoice_pdf

        order = self.get_object(request, pk)
        if not order:
            raise Http404("Objednávka nenalezena")

        # Soubor mohl být smazán (ephemeral filesystem na Renderu) → vygeneruj znovu
        file_missing = (
            not order.invoice_pdf
            or not order.invoice_pdf.storage.exists(order.invoice_pdf.name)
        )
        if file_missing:
            if not order.invoice_number:
                raise Http404("Faktura ještě nebyla vystavena (objednávka není zaplacena).")
            invoice_file = generate_invoice_pdf(order)
            order.invoice_pdf.save(invoice_file.name, invoice_file, save=True)

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

    # ── Akce – stav objednávky ────────────────────────────

    @admin.action(description="✅ Označit jako zaplaceno")
    def mark_as_paid(self, request, queryset):
        updated = queryset.exclude(status=Order.Status.PAID).update(status=Order.Status.PAID)
        self.message_user(
            request,
            f"Označeno jako zaplaceno: {updated}. "
            "Pozor: ruční změna stavu negeneruje fakturu, neodečítá sklad ani neuděluje přístup ke kurzu "
            "– to probíhá automaticky přes platební bránu Stripe.",
            level=messages.WARNING if updated else messages.INFO,
        )

    @admin.action(description="🚫 Označit jako zrušeno")
    def mark_as_canceled(self, request, queryset):
        updated = queryset.update(status=Order.Status.CANCELED)
        self.message_user(request, f"Zrušeno objednávek: {updated}", level=messages.SUCCESS)

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
# COURSE ACCESS – přístupy ke kurzům
# ======================================

@admin.register(CourseAccess)
class CourseAccessAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = CourseAccessResource
    list_display = (
        "user",
        "course",
        "plan",
        "access_badge",
        "granted_at",
        "expires_at",
        "bypass_module_sequencing",
    )
    list_filter = ("is_active", "bypass_module_sequencing", "course", "plan", ("granted_at", DateRangeFilter))
    date_hierarchy = "granted_at"
    search_fields = ("user__email", "user__username", "course__title")
    autocomplete_fields = ("user", "course", "plan")
    actions = ["activate_access", "deactivate_access"]

    @admin.display(description="Přístup")
    def access_badge(self, obj):
        if obj.has_access():
            return _badge("Aktivní", "#2e7d32")
        if not obj.is_active:
            return _badge("Neaktivní", "#9e9e9e")
        return _badge("Vypršel", "#c62828")

    @admin.action(description="✅ Aktivovat přístup")
    def activate_access(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Aktivováno přístupů: {updated}", level=messages.SUCCESS)

    @admin.action(description="🚫 Deaktivovat přístup")
    def deactivate_access(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deaktivováno přístupů: {updated}", level=messages.SUCCESS)


# ======================================
# COUPON – slevové kupóny
# ======================================

class CouponUsageInline(admin.TabularInline):
    model = CouponUsage
    extra = 0
    can_delete = False
    verbose_name = "Použití"
    verbose_name_plural = "Historie použití"
    fields = ("order", "user", "discount_amount", "used_at")
    readonly_fields = ("order", "user", "discount_amount", "used_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "description",
        "discount_display",
        "active_badge",
        "validity_display",
        "usage_display",
        "min_order_value",
    )
    list_filter = ("is_active", "discount_type", "valid_from", "valid_to")
    search_fields = ("code", "description", "note")
    ordering = ("-created_at",)
    autocomplete_fields = ("user", "products", "courses")
    readonly_fields = ("used_count", "created_at")
    actions = ["activate_coupons", "deactivate_coupons", "reset_usage"]

    fieldsets = (
        ("Kupón", {
            "fields": ("code", "description", "is_active", "note"),
        }),
        ("Sleva", {
            "fields": ("discount_type", "discount_value", "min_order_value"),
        }),
        ("Platnost", {
            "fields": ("valid_from", "valid_to"),
        }),
        ("Počet použití", {
            "fields": ("max_uses", "used_count", "max_uses_per_user"),
        }),
        ("Omezení", {
            "description": "Nech prázdné, pokud má kupón platit pro vše / pro každého.",
            "fields": ("products", "courses", "user"),
        }),
        ("Záznam", {
            "fields": ("created_at",),
        }),
    )

    inlines = [CouponUsageInline]

    @admin.display(description="Sleva")
    def discount_display(self, obj):
        if obj.discount_type == Coupon.DiscountType.PERCENT:
            return f"{obj.discount_value:.0f} %"
        return f"{obj.discount_value:.0f} Kč"

    @admin.display(description="Stav")
    def active_badge(self, obj):
        if obj.is_active:
            return _badge("Aktivní", "#2e7d32")
        return _badge("Neaktivní", "#9e9e9e")

    @admin.display(description="Platnost")
    def validity_display(self, obj):
        od = obj.valid_from.strftime("%d.%m.%Y") if obj.valid_from else "—"
        do = obj.valid_to.strftime("%d.%m.%Y") if obj.valid_to else "—"
        return f"{od} → {do}"

    @admin.display(description="Použití")
    def usage_display(self, obj):
        if obj.max_uses is None:
            return f"{obj.used_count}× (neomezeno)"
        color = "#c62828" if obj.used_count >= obj.max_uses else "#333"
        return format_html('<span style="color:{};">{} / {}</span>', color, obj.used_count, obj.max_uses)

    @admin.action(description="✅ Aktivovat kupóny")
    def activate_coupons(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Aktivováno kupónů: {updated}", level=messages.SUCCESS)

    @admin.action(description="🚫 Deaktivovat kupóny")
    def deactivate_coupons(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deaktivováno kupónů: {updated}", level=messages.SUCCESS)

    @admin.action(description="🔄 Vynulovat počet použití")
    def reset_usage(self, request, queryset):
        updated = queryset.update(used_count=0)
        self.message_user(request, f"Vynulováno u kupónů: {updated}", level=messages.SUCCESS)


# ======================================
# COUPON USAGE – historie použití
# ======================================

@admin.register(CouponUsage)
class CouponUsageAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = CouponUsageResource
    list_display = ("coupon", "order", "user", "discount_amount", "used_at")
    list_filter = (("used_at", DateRangeFilter), "coupon")
    date_hierarchy = "used_at"
    search_fields = ("coupon__code", "user__email", "order__id")
    autocomplete_fields = ("coupon", "order", "user")
    readonly_fields = ("coupon", "order", "user", "discount_amount", "used_at")

    def has_add_permission(self, request):
        return False


# ======================================
# SHOP SETTINGS – přepínač uzamčení
# ======================================

@admin.register(ShopSettings)
class ShopSettingsAdmin(admin.ModelAdmin):
    """
    Singleton administrace – vždy zobrazí jediný řádek nastavení.
    """
    fields = ("shop_locked",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Přesměruj seznam rovnou na editaci singleton objektu."""
        from django.shortcuts import redirect
        obj = ShopSettings.objects.get_or_create(pk=1)[0]
        return redirect(
            reverse("admin:payments_shopsettings_change", args=[obj.pk])
        )


# ======================================
# WELCOME COUPON CLAIMS
# ======================================

@admin.register(WelcomeCouponClaim)
class WelcomeCouponClaimAdmin(admin.ModelAdmin):
    list_display = ("email", "coupon_code", "created_at")
    search_fields = ("email", "coupon__code")
    readonly_fields = ("email", "coupon", "created_at")
    ordering = ("-created_at",)

    @admin.display(description="Kód kupónu")
    def coupon_code(self, obj):
        return obj.coupon.code if obj.coupon else "—"

    def has_add_permission(self, request):
        return False


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = NewsletterSubscriberResource
    list_display = ("email", "first_name", "last_name", "is_subscribed", "created_at")
    list_filter = ("is_subscribed", ("created_at", DateRangeFilter))
    search_fields = ("email", "first_name", "last_name")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    actions = ["mark_subscribed", "mark_unsubscribed"]

    @admin.action(description="Označit jako odebírající")
    def mark_subscribed(self, request, queryset):
        updated = queryset.update(is_subscribed=True)
        self.message_user(request, f"Označeno jako odebírající: {updated}", messages.SUCCESS)

    @admin.action(description="Označit jako odhlášené")
    def mark_unsubscribed(self, request, queryset):
        updated = queryset.update(is_subscribed=False)
        self.message_user(request, f"Označeno jako odhlášené: {updated}", messages.SUCCESS)
