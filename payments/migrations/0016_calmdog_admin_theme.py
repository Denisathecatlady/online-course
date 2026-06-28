from django.db import migrations


# Motiv administrace CalmDog (django-admin-interface).
# Vznikne automaticky při `migrate` na každém prostředí (i na produkci).
THEME = {
    "name": "CalmDog",
    "title": "CalmDog administrace",
    "title_visible": True,
    "active": True,
    "css_header_background_color": "#29493c",        # sage-deep
    "css_header_text_color": "#ffffff",
    "css_header_link_color": "#dfe7e1",
    "css_header_link_hover_color": "#ffffff",
    "css_module_background_color": "#5f766b",         # sage
    "css_module_background_selected_color": "#29493c",
    "css_module_text_color": "#ffffff",
    "css_module_link_color": "#ffffff",
    "css_module_link_selected_color": "#ffffff",
    "css_module_link_hover_color": "#dfe7e1",
    "css_generic_link_color": "#29493c",
    "css_generic_link_hover_color": "#5f766b",
    "css_save_button_background_color": "#5f766b",
    "css_save_button_background_hover_color": "#29493c",
    "css_save_button_text_color": "#ffffff",
    "related_modal_active": True,
    "recent_actions_visible": True,
    "language_chooser_active": False,
}


def create_theme(apps, schema_editor):
    Theme = apps.get_model("admin_interface", "Theme")
    field_names = {f.name for f in Theme._meta.get_fields()}
    data = {k: v for k, v in THEME.items() if k in field_names}
    # Necháme jediný, čistý motiv – odstraníme případný výchozí "Django".
    Theme.objects.all().delete()
    Theme.objects.create(**data)


def remove_theme(apps, schema_editor):
    Theme = apps.get_model("admin_interface", "Theme")
    Theme.objects.filter(name="CalmDog").delete()
    if not Theme.objects.exists():
        Theme.objects.create(name="Django", active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0015_alter_courseaccess_options_alter_order_options_and_more"),
        ("admin_interface", "0032_alter_theme_defaults"),
    ]

    operations = [
        migrations.RunPython(create_theme, remove_theme),
    ]
