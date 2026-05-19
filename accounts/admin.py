from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.admin.sites import NotRegistered

from .models import UserProfile


User = get_user_model()


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    fields = (
        "role",
        "phone",
        "street",
        "city",
        "zip_code",
        "country",
        "invoice_name",
        "invoice_street",
        "invoice_city",
        "invoice_zip",
        "invoice_country",
    )


try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = UserAdmin.list_display + ("profile_role",)
    list_filter = UserAdmin.list_filter + ("profile__role",)

    @admin.display(description="Role")
    def profile_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return "Bez profilu"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "city")
    list_filter = ("role", "country")
    search_fields = ("user__username", "user__email", "phone", "city")
