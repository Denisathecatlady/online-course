from django.contrib import admin

from config.admin_ui import badge
from .models import HotelReservation


@admin.register(HotelReservation)
class HotelReservationAdmin(admin.ModelAdmin):
    list_display = (
        "last_name", "first_name", "email", "phone",
        "date_from", "date_to", "nights",
        "pet_type", "pet_count", "pet_name",
        "is_aggressive", "status_badge", "created_at",
    )
    list_filter = ("status", "pet_type", "is_aggressive", "date_from")
    search_fields = ("last_name", "first_name", "email", "pet_name")
    ordering = ("-created_at",)
    date_hierarchy = "date_from"

    fieldsets = (
        ("Kontakt", {
            "fields": ("first_name", "last_name", "email", "phone"),
        }),
        ("Termín", {
            "fields": ("date_from", "date_to"),
        }),
        ("Zvíře", {
            "fields": ("pet_type", "pet_count", "pet_name", "pet_breed", "is_aggressive", "aggression_notes"),
        }),
        ("Poznámky", {
            "fields": ("notes",),
        }),
        ("Stav rezervace", {
            "fields": ("status",),
        }),
    )

    readonly_fields = ("created_at",)

    actions = ["mark_confirmed", "mark_canceled"]

    STATUS_VARIANTS = {
        HotelReservation.Status.PENDING: "warning",
        HotelReservation.Status.CONFIRMED: "success",
        HotelReservation.Status.CANCELED: "muted",
    }

    @admin.display(description="Stav", ordering="status")
    def status_badge(self, obj):
        return badge(obj.get_status_display(), self.STATUS_VARIANTS.get(obj.status, "muted"))

    @admin.action(description="Označit jako potvrzeno")
    def mark_confirmed(self, request, queryset):
        queryset.update(status=HotelReservation.Status.CONFIRMED)

    @admin.action(description="Označit jako zrušeno")
    def mark_canceled(self, request, queryset):
        queryset.update(status=HotelReservation.Status.CANCELED)

    def nights(self, obj):
        return obj.nights
    nights.short_description = "Nocí"
