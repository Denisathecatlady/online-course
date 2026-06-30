from django.contrib import admin, messages
from django.utils.html import format_html

from import_export.admin import ImportExportModelAdmin
from rangefilter.filters import NumericRangeFilter

from .models import Product, ProductVariant, Color


# ======================================
# INLINE – varianty produktu
# ======================================

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ("length", "type", "color", "price", "stock", "is_active")
    autocomplete_fields = ("color",)


# ======================================
# PRODUCT
# ======================================

@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display = ("name", "variant_count", "is_active", "is_sale_locked", "created_at")
    list_editable = ("is_active", "is_sale_locked")
    list_filter = ("is_active", "is_sale_locked", "created_at")
    search_fields = ("name", "description")
    ordering = ("-created_at",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductVariantInline]

    fieldsets = (
        ("Produkt", {
            "fields": ("name", "slug", "is_active", "is_sale_locked"),
        }),
        ("Popis a obrázek", {
            "fields": ("description", "image"),
        }),
    )

    @admin.display(description="Počet variant")
    def variant_count(self, obj):
        return obj.variants.count()


# ======================================
# COLOR
# ======================================

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ("name", "color_swatch", "hex_code")
    search_fields = ("name",)

    @admin.display(description="Náhled")
    def color_swatch(self, obj):
        if not obj.hex_code:
            return "—"
        return format_html(
            '<span style="display:inline-block;width:18px;height:18px;'
            'border:1px solid #ccc;border-radius:3px;background:{};"></span>',
            obj.hex_code,
        )


# ======================================
# PRODUCT VARIANT
# ======================================

@admin.register(ProductVariant)
class ProductVariantAdmin(ImportExportModelAdmin):
    list_display = ("product", "length", "type", "color", "price", "stock", "stock_badge", "is_active")
    list_editable = ("price", "stock", "is_active")
    list_filter = ("is_active", "length", "type", "product", ("price", NumericRangeFilter))
    search_fields = ("product__name", "color__name")
    ordering = ("product", "length", "type")
    autocomplete_fields = ("product", "color")
    actions = ["activate_variants", "deactivate_variants"]

    @admin.display(description="Skladem")
    def stock_badge(self, obj):
        if obj.stock <= 0:
            return format_html('<span style="color:#c62828;font-weight:600;">Vyprodáno</span>')
        if obj.stock <= 3:
            return format_html('<span style="color:#e0a800;font-weight:600;">Málo ({})</span>', obj.stock)
        return format_html('<span style="color:#2e7d32;">Skladem ({})</span>', obj.stock)

    @admin.action(description="✅ Aktivovat varianty")
    def activate_variants(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Aktivováno variant: {updated}", level=messages.SUCCESS)

    @admin.action(description="🚫 Deaktivovat varianty")
    def deactivate_variants(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deaktivováno variant: {updated}", level=messages.SUCCESS)
