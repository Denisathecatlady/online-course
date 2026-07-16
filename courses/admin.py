from django.contrib import admin, messages
from django.utils.html import format_html

from config.admin_ui import badge as _badge

from .models import (
    Course,
    CoursePlan,
    Module,
    ModuleProgress,
    ModuleQuizProgress,
)


# =========================
# INLINE – varianty kurzu
# =========================

class CoursePlanInline(admin.TabularInline):
    model = CoursePlan
    extra = 0
    fields = ("name", "code", "price", "access_duration_days",
              "includes_certificate", "includes_consultation", "is_active")
    prepopulated_fields = {"code": ("name",)}


# =========================
# INLINE – moduly (lekce)
# =========================

class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    fields = ("order", "title", "pdf_file")
    ordering = ("order",)
    show_change_link = True


# =========================
# COURSE
# =========================

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "active_badge",
        "module_count",
        "plan_count",
        "buyer_count",
        "created_at",
    )
    list_filter = ("is_active", "coming_soon", "created_at")
    date_hierarchy = "created_at"
    search_fields = ("title",)
    ordering = ("-created_at",)
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CoursePlanInline, ModuleInline]

    fieldsets = (
        ("Základní údaje", {
            "fields": ("title", "slug", "is_active", "coming_soon", "image"),
        }),
        ("Texty kurzu", {
            "fields": ("public_intro", "about_text", "private_intro"),
        }),
    )

    @admin.display(description="Stav")
    def active_badge(self, obj):
        if obj.coming_soon:
            return _badge("Připravujeme", "warning")
        if obj.is_active:
            return _badge("Aktivní", "success")
        return _badge("Skrytý", "muted")

    @admin.display(description="Počet lekcí")
    def module_count(self, obj):
        return f"{obj.modules.count()} lekcí"

    @admin.display(description="Počet variant")
    def plan_count(self, obj):
        return obj.plans.count()

    @admin.display(description="Zakoupilo zákazníků")
    def buyer_count(self, obj):
        count = obj.accesses.count()
        return format_html('<strong>{}</strong>', count)


# =========================
# COURSE PLAN (varianta kurzu)
# =========================

@admin.register(CoursePlan)
class CoursePlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "course",
        "price",
        "access_duration_days",
        "includes_certificate",
        "includes_consultation",
        "is_active",
    )
    list_filter = ("is_active", "includes_certificate", "includes_consultation", "course")
    search_fields = ("name", "course__title")
    ordering = ("course", "name")
    autocomplete_fields = ("course",)
    prepopulated_fields = {"code": ("name",)}


# =========================
# MODULE (lekce)
# =========================

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("order", "title", "course", "content_badge")
    list_filter = ("course",)
    search_fields = ("title", "course__title")
    ordering = ("course", "order")
    autocomplete_fields = ("course",)
    prepopulated_fields = {"slug": ("title",)}

    fieldsets = (
        ("Zařazení", {
            "fields": ("course", "order", "title", "slug"),
        }),
        ("Obsah", {
            "fields": ("intro_text", "vimeo_embed_url1", "vimeo_embed_url2", "vimeo_embed_url3", "pdf_file"),
        }),
    )

    @admin.display(description="Obsah")
    def content_badge(self, obj):
        videos = sum(1 for u in (obj.vimeo_embed_url1, obj.vimeo_embed_url2, obj.vimeo_embed_url3) if u)
        parts = []
        if videos:
            parts.append(f"🎬 {videos}")
        if obj.pdf_file:
            parts.append("📄 PDF")
        return " · ".join(parts) if parts else "—"


# =========================
# MODULE PROGRESS (postup v lekcích)
# =========================

@admin.register(ModuleProgress)
class ModuleProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "module", "completed_badge", "completed_at")
    list_filter = ("completed", "module__course")
    date_hierarchy = "completed_at"
    search_fields = ("user__email", "user__username", "module__title", "module__course__title")
    autocomplete_fields = ("user", "module")

    @admin.display(description="Stav")
    def completed_badge(self, obj):
        if obj.completed:
            return _badge("Dokončeno", "success")
        return _badge("Probíhá", "muted")


# =========================
# MODULE QUIZ PROGRESS (postup v kvízech)
# =========================

@admin.register(ModuleQuizProgress)
class ModuleQuizProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "module", "step", "passed_badge", "attempts_count", "passed_at")
    list_filter = ("passed", "module__course")
    date_hierarchy = "passed_at"
    search_fields = ("user__email", "user__first_name", "module__title", "module__course__title")
    autocomplete_fields = ("user", "module")

    @admin.display(description="Výsledek")
    def passed_badge(self, obj):
        if obj.passed:
            return _badge("Splněno", "success")
        return _badge("Nesplněno", "danger")
