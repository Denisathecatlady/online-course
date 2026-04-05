from django.contrib import admin
from .models import Course, CoursePlan, Module, ModuleQuizProgress


# =========================
# INLINE – PLÁNY KURZU
# =========================

class CoursePlanInline(admin.TabularInline):
    model = CoursePlan
    extra = 0


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0


# =========================
# COURSE
# =========================

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title",)
    inlines = [CoursePlanInline, ModuleInline]


# =========================
# COURSE PLAN (samostatně)
# =========================

@admin.register(CoursePlan)
class CoursePlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "course",
        "price",
        "access_duration_days",
        "is_active",
    )
    list_filter = ("is_active", "course")
    search_fields = ("name", "course__title")
    prepopulated_fields = {"code": ("name",)}
# =========================
# MODULE
# =========================

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("order", "title", "course")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(ModuleQuizProgress)
class ModuleQuizProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "module", "step", "passed", "attempts_count", "passed_at")
    list_filter = ("passed", "module__course")
    search_fields = ("user__email", "user__first_name", "module__title", "module__course__title")
