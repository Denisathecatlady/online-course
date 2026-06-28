from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.admin.sites import NotRegistered
from django.utils.html import format_html

from .models import UserProfile
from payments.models import CourseAccess


User = get_user_model()


# ======================================
# INLINE – profil zákazníka
# ======================================

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    verbose_name = "Profil zákazníka"
    verbose_name_plural = "Profil zákazníka"
    fields = (
        "role",
        "phone",
        ("street", "city", "zip_code", "country"),
        ("invoice_name", "invoice_street"),
        ("invoice_city", "invoice_zip", "invoice_country"),
    )


# ======================================
# INLINE – zakoupené kurzy (jen pro čtení)
# ======================================

class CourseAccessInline(admin.TabularInline):
    model = CourseAccess
    extra = 0
    can_delete = False
    verbose_name = "Zakoupený kurz"
    verbose_name_plural = "Zakoupené kurzy"
    fields = ("course", "plan", "is_active", "granted_at", "expires_at")
    readonly_fields = ("course", "plan", "is_active", "granted_at", "expires_at")

    def has_add_permission(self, request, obj=None):
        return False


# ======================================
# USER
# ======================================

try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline, CourseAccessInline)
    list_display = UserAdmin.list_display + ("profile_role", "courses_count")
    list_filter = UserAdmin.list_filter + ("profile__role",)

    @admin.display(description="Role")
    def profile_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return "Bez profilu"

    @admin.display(description="Zakoupených kurzů")
    def courses_count(self, obj):
        count = obj.course_accesses.count()
        if count:
            return format_html('<strong>{}</strong>', count)
        return "—"


# ======================================
# USER PROFILE (samostatně)
# ======================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "city")
    list_filter = ("role", "country")
    search_fields = ("user__username", "user__email", "phone", "city")
    autocomplete_fields = ("user",)
