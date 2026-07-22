"""
Sdílené prezentační komponenty administrace CalmDog.

Jediný zdroj pravdy pro barevné štítky stavů – stejný vzhled napříč všemi
appkami (objednávky, kurzy, sklad, rezervace…). Vzhled definuje CSS třída
``.cd-badge`` v courses/static/admin/css/calmdog_admin.css.
"""
from django.utils.html import format_html

# Povolené varianty (musí odpovídat CSS třídám .cd-badge--*)
BADGE_VARIANTS = {"success", "warning", "danger", "muted", "info", "primary"}


def badge(text, variant="muted"):
    """
    Vrátí HTML barevný štítek stavu.

    ``variant``: success (zelená) | warning (oranžová) | danger (červená)
                 | muted (šedá) | info (tyrkysová) | primary (námořní modrá)
    """
    if variant not in BADGE_VARIANTS:
        variant = "muted"
    return format_html('<span class="cd-badge cd-badge--{}">{}</span>', variant, text)
