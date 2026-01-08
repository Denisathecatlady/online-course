from django.contrib import admin
from .models import CoursePlan, Order, CourseAccess


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
        "created_at",
    )
    list_filter = ("status", "plan")
    search_fields = (
        "user__email",
        "user__username",
        "stripe_checkout_session_id",
    )
    readonly_fields = (
        "stripe_checkout_session_id",
        "created_at",
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
