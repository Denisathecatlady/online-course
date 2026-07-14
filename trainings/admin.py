"""
Administrace rezervačního systému.

Hlavní pracovní objekt trenéra je `AvailabilityWindow` (časové okno) – po uložení
se z něj automaticky vygenerují sloty (`generate_slots`). Overlap a další pravidla
hlídá `AvailabilityWindow.clean()`, které admin formulář spouští automaticky.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    AvailabilityWindow,
    Location,
    Trainer,
    TrainingReservation,
    TrainingSlot,
)
from .services import google_calendar, notifications


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "order")
    list_editable = ("is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("name", "address")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "is_active", "google_connected")
    list_filter = ("is_active", "google_connected")
    search_fields = ("name", "email")
    filter_horizontal = ("locations",)
    readonly_fields = ("google_connected", "google_connect_link")
    fieldsets = (
        ("Trenér", {
            "fields": ("name", "email", "user", "is_active", "locations"),
        }),
        ("Google Calendar (OAuth)", {
            "fields": ("google_calendar_id", "google_connected", "google_connect_link"),
            "description": (
                "Kalendář se připojuje jednorázově přes tlačítko níže. "
                "Token se ukládá automaticky – needitujte ho ručně."
            ),
        }),
    )

    @admin.display(description="Připojení Google kalendáře")
    def google_connect_link(self, obj):
        if not obj or not obj.pk:
            return "Nejprve trenéra uložte – poté se zde objeví tlačítko pro připojení."
        if not google_calendar.is_enabled():
            return "Google integrace není nakonfigurovaná (chybí OAuth klient v nastavení serveru)."
        url = reverse("trainings:google_oauth_start", args=[obj.pk])
        label = "Znovu připojit Google kalendář" if obj.google_connected else "Připojit Google kalendář"
        return format_html('<a class="button" href="{}">{}</a>', url, label)


class TrainingSlotInline(admin.TabularInline):
    model = TrainingSlot
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("start", "end", "capacity", "occupancy", "status")
    readonly_fields = ("start", "end", "capacity", "occupancy", "status")

    @admin.display(description="Obsazeno")
    def occupancy(self, obj):
        return f"{obj.spots_taken}/{obj.capacity}"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AvailabilityWindow)
class AvailabilityWindowAdmin(admin.ModelAdmin):
    list_display = (
        "location", "trainer", "date", "start_time", "end_time",
        "slot_duration_minutes", "session_type", "capacity", "is_active", "slot_count",
    )
    list_filter = ("location", "trainer", "session_type", "is_active", "date")
    search_fields = ("location__name", "trainer__name", "note")
    date_hierarchy = "date"
    inlines = [TrainingSlotInline]
    actions = ["block_windows", "unblock_windows"]

    fieldsets = (
        ("Kde a kdo", {
            "fields": ("location", "trainer"),
        }),
        ("Kdy", {
            "fields": ("date", "start_time", "end_time", "slot_duration_minutes"),
        }),
        ("Typ lekce", {
            "fields": ("session_type", "capacity"),
            "description": "Individuální = kapacita 1. Skupinová = počet míst na jeden slot.",
        }),
        ("Ostatní", {
            "fields": ("is_active", "note"),
        }),
    )

    @admin.display(description="Počet slotů")
    def slot_count(self, obj):
        return obj.slots.count()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        created = obj.generate_slots()
        if created:
            self.message_user(request, f"Vygenerováno {created} nových slotů.")

    @admin.action(description="Blokovat okna (skrýt jejich sloty klientům)")
    def block_windows(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Zablokováno {updated} oken.")

    @admin.action(description="Odblokovat okna")
    def unblock_windows(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Odblokováno {updated} oken.")


@admin.register(TrainingSlot)
class TrainingSlotAdmin(admin.ModelAdmin):
    list_display = (
        "start", "end", "location", "trainer", "session_type", "occupancy", "status",
    )
    list_filter = ("location", "trainer", "status", "session_type")
    search_fields = ("location__name", "trainer__name")
    date_hierarchy = "start"
    actions = ["block_slots", "unblock_slots", "delete_free_slots"]

    @admin.display(description="Obsazeno")
    def occupancy(self, obj):
        return f"{obj.spots_taken}/{obj.capacity}"

    @admin.action(description="Blokovat vybrané sloty")
    def block_slots(self, request, queryset):
        updated = queryset.update(status=TrainingSlot.Status.BLOCKED)
        self.message_user(request, f"Zablokováno {updated} slotů.")

    @admin.action(description="Odblokovat vybrané sloty")
    def unblock_slots(self, request, queryset):
        updated = queryset.update(status=TrainingSlot.Status.OPEN)
        self.message_user(request, f"Odblokováno {updated} slotů.")

    @admin.action(description="Smazat volné sloty (bez potvrzené rezervace)")
    def delete_free_slots(self, request, queryset):
        deletable = [s for s in queryset if not s.has_confirmed_reservations]
        skipped = queryset.count() - len(deletable)
        for slot in deletable:
            slot.delete()
        msg = f"Smazáno {len(deletable)} volných slotů."
        if skipped:
            msg += f" {skipped} přeskočeno (mají potvrzenou rezervaci)."
        self.message_user(request, msg)


@admin.register(TrainingReservation)
class TrainingReservationAdmin(admin.ModelAdmin):
    list_display = (
        "full_name", "dog_name", "slot", "location_name", "trainer_name",
        "status", "created_at",
    )
    list_filter = ("status", "slot__location", "slot__session_type", "slot__trainer")
    search_fields = ("first_name", "last_name", "email", "dog_name")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "canceled_at", "google_event_id")
    actions = ["mark_completed", "mark_canceled"]

    fieldsets = (
        ("Slot", {
            "fields": ("slot", "user"),
        }),
        ("Klient", {
            "fields": ("first_name", "last_name", "email", "phone", "dog_name", "note"),
        }),
        ("Stav", {
            "fields": ("status", "created_at", "canceled_at", "google_event_id"),
        }),
    )

    @admin.display(description="Lokalita")
    def location_name(self, obj):
        return obj.slot.location.name

    @admin.display(description="Trenér")
    def trainer_name(self, obj):
        return obj.slot.trainer.name

    @admin.action(description="Označit jako absolvováno")
    def mark_completed(self, request, queryset):
        updated = queryset.update(status=TrainingReservation.Status.COMPLETED)
        self.message_user(request, f"Označeno {updated} rezervací jako absolvováno.")

    @admin.action(
        description="Zrušit rezervaci (uvolní místo, smaže Google událost, pošle e-maily)"
    )
    def mark_canceled(self, request, queryset):
        count = 0
        for reservation in queryset.exclude(status=TrainingReservation.Status.CANCELED):
            reservation.status = TrainingReservation.Status.CANCELED
            reservation.canceled_at = timezone.now()
            reservation.save(update_fields=["status", "canceled_at"])
            google_calendar.delete_event(reservation)
            notifications.send_cancellation_emails(reservation)
            count += 1
        self.message_user(request, f"Zrušeno {count} rezervací.")
