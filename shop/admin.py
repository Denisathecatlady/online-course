
from django.contrib import admin
from .models import Product, ProductVariant, Color


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductVariantInline]


admin.site.register(Color)

class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "length", "type", "color", "price", "stock")
    list_editable = ("price", "stock")