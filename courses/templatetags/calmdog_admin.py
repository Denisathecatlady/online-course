"""
Šablonové tagy administrace CalmDog.

- ``cd_icon``          – vloží inline SVG ikonu (bez externích knihoven / CDN).
- ``calmdog_nav``      – přeskupí modely do logických sekcí s ikonami (menu i dashboard).
- ``dashboard_metrics`` – spočítá KPI karty a data pro graf na úvodní stránce.

Vše je jen prezentační vrstva – žádná byznys logika, žádné zápisy do DB.
"""
from datetime import timedelta

from django import template
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()


# ---------------------------------------------------------------------------
# Ikony (Lucide-style, 24×24, stroke = currentColor)
# ---------------------------------------------------------------------------

_ICONS = {
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "cart": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/>'
            '<path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "box": '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/>'
           '<path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "cap": '<path d="M22 10 12 5 2 10l10 5 10-5Z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/><path d="M22 10v6"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
             '<path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "cog": '<circle cx="12" cy="12" r="3"/>'
           '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33'
           ' 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06'
           'a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09'
           'A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33'
           'H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06'
           'a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09'
           'a1.65 1.65 0 0 0-1.51 1z"/>',
    "receipt": '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/>'
               '<path d="M8 7h8M8 11h8M8 15h5"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "user-plus": '<path d="M14 19a6 6 0 0 0-12 0"/><circle cx="8" cy="9" r="4"/><path d="M19 8v6M22 11h-6"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
             '<path d="M12 9v4M12 17h.01"/>',
    "ticket": '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/>'
              '<path d="M13 5v2M13 17v2M13 11v2"/>',
    "graduation": '<path d="M21.42 10.92a1 1 0 0 0 0-1.84L12.83 5.18a2 2 0 0 0-1.66 0L2.58 9.08a1 1 0 0 0 0 1.84l8.59 3.9a2 2 0 0 0 1.66 0z"/>'
                  '<path d="M22 10v6M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
}


@register.simple_tag
def cd_icon(name, css_class=""):
    """Vloží inline SVG ikonu. Bezpečné (jen náš vlastní obsah)."""
    body = _ICONS.get(name)
    if not body:
        return ""
    cls = f' class="{css_class}"' if css_class else ""
    return mark_safe(
        f'<svg{cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{body}</svg>'
    )


# ---------------------------------------------------------------------------
# Navigace přeskupená do logických sekcí
# ---------------------------------------------------------------------------

# (klíč, popisek, ikona, [seznam "app_label.ObjectName" v požadovaném pořadí])
_NAV_GROUPS = [
    ("prodej", "Prodej", "cart", [
        "payments.Order", "payments.Coupon", "payments.CouponUsage",
    ]),
    ("sklad", "Sklad a produkty", "box", [
        "shop.Product", "shop.ProductVariant", "shop.Color",
    ]),
    ("akademie", "Akademie", "cap", [
        "courses.Course", "courses.CoursePlan", "courses.Module",
        "payments.CourseAccess", "courses.ModuleProgress", "courses.ModuleQuizProgress",
    ]),
    ("rezervace", "Rezervace", "calendar", [
        "trainings.TrainingReservation", "hotel.HotelReservation",
        "trainings.TrainingSlot", "trainings.AvailabilityWindow",
        "trainings.AvailabilityCalendar", "trainings.Location", "trainings.Trainer",
    ]),
    ("klienti", "Klienti", "users", [
        "auth.User", "accounts.UserProfile", "accounts.Dog", "account.EmailAddress",
    ]),
    ("marketing", "Marketing", "mail", [
        "payments.NewsletterSubscriber", "payments.WelcomeCouponClaim",
    ]),
    ("system", "Systém", "cog", [
        "payments.ShopSettings", "auth.Group",
        "socialaccount.SocialAccount", "socialaccount.SocialApp", "socialaccount.SocialToken",
        "sites.Site",
    ]),
]


@register.simple_tag(takes_context=True)
def calmdog_nav(context):
    """
    Přeskupí ``available_apps`` / ``app_list`` do sekcí v ``_NAV_GROUPS``.
    Modely mimo mapu se nezahodí – přidají se do sekce „Ostatní", takže po
    zaregistrování nového modelu se stále zobrazí.
    """
    apps = context.get("available_apps") or context.get("app_list") or []
    request = context.get("request")
    current_path = getattr(request, "path", "")

    # Rejstřík dostupných modelů podle "app_label.ObjectName"
    index = {}
    for app in apps:
        label = app.get("app_label", "")
        for model in app.get("models", []):
            key = f"{label}.{model.get('object_name', '')}"
            model = dict(model)
            admin_url = model.get("admin_url") or ""
            model["cd_active"] = bool(admin_url) and current_path.startswith(admin_url)
            index[key] = model

    used = set()
    groups = []
    for key, label, icon, members in _NAV_GROUPS:
        items = []
        for member in members:
            model = index.get(member)
            if model:
                items.append(model)
                used.add(member)
        if items:
            groups.append({"key": key, "label": label, "icon": icon, "models": items})

    # Zbývající modely (např. nově přidané) → „Ostatní"
    leftovers = [index[k] for k in index if k not in used]
    if leftovers:
        groups.append({"key": "ostatni", "label": "Ostatní", "icon": "cog", "models": leftovers})

    return groups


# ---------------------------------------------------------------------------
# Dashboard – KPI karty + graf
# ---------------------------------------------------------------------------

def _url(name, query=""):
    try:
        return reverse(name) + (f"?{query}" if query else "")
    except NoReverseMatch:
        return ""


@register.simple_tag
def dashboard_metrics():
    """Spočítá čísla pro dashboard. Odolné vůči chybám – při potížích vrátí prázdno."""
    try:
        from django.contrib.auth import get_user_model
        from payments.models import Coupon, NewsletterSubscriber, Order
        from shop.models import ProductVariant
        from trainings.models import TrainingReservation
        from hotel.models import HotelReservation

        User = get_user_model()
        now = timezone.now()
        week_ago = now - timedelta(days=7)

        paid = Order.objects.filter(status=Order.Status.PAID)
        orders_total = paid.count()
        orders_week = paid.filter(created_at__gte=week_ago).count()
        pending_orders = Order.objects.filter(status=Order.Status.PENDING).count()

        new_reservations = TrainingReservation.objects.filter(
            status=TrainingReservation.Status.CONFIRMED, created_at__gte=week_ago
        ).count()
        hotel_pending = HotelReservation.objects.filter(
            status=HotelReservation.Status.PENDING
        ).count()

        new_customers = User.objects.filter(date_joined__gte=week_ago).count()
        low_stock = ProductVariant.objects.filter(is_active=True, stock__lte=3).count()
        newsletter = NewsletterSubscriber.objects.filter(is_subscribed=True).count()
        active_coupons = Coupon.objects.filter(is_active=True).count()

        cards = [
            {"value": orders_week, "label": "Zaplacené objednávky (7 dní)",
             "icon": "receipt", "tone": "", "url": _url("admin:payments_order_changelist", "status__exact=paid"),
             "pill": f"celkem {orders_total}"},
            {"value": pending_orders, "label": "Čeká na platbu",
             "icon": "clock", "tone": "amber" if pending_orders else "",
             "url": _url("admin:payments_order_changelist", "status__exact=pending")},
            {"value": new_reservations, "label": "Nové rezervace tréninků (7 dní)",
             "icon": "calendar", "tone": "", "url": _url("admin:trainings_trainingreservation_changelist")},
            {"value": hotel_pending, "label": "Rezervace hotelu ke schválení",
             "icon": "bell", "tone": "amber" if hotel_pending else "",
             "url": _url("admin:hotel_hotelreservation_changelist", "status__exact=pending")},
            {"value": new_customers, "label": "Noví zákazníci (7 dní)",
             "icon": "user-plus", "tone": "green", "url": _url("admin:auth_user_changelist")},
            {"value": low_stock, "label": "Varianty s nízkým skladem",
             "icon": "alert", "tone": "red" if low_stock else "",
             "url": _url("admin:shop_productvariant_changelist")},
            {"value": newsletter, "label": "Odběratelé newsletteru",
             "icon": "mail", "tone": "", "url": _url("admin:payments_newslettersubscriber_changelist")},
            {"value": active_coupons, "label": "Aktivní slevové kupóny",
             "icon": "ticket", "tone": "", "url": _url("admin:payments_coupon_changelist")},
        ]

        # Graf: počet zaplacených objednávek za posledních 14 dní
        chart = []
        days_cs = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]
        today = timezone.localdate()
        for i in range(13, -1, -1):
            day = today - timedelta(days=i)
            count = paid.filter(created_at__date=day).count()
            chart.append({
                "count": count,
                "label": f"{day.day}.{day.month}.",
                "dow": days_cs[day.weekday()],
            })
        chart_max = max((c["count"] for c in chart), default=0) or 1

        return {"cards": cards, "chart": chart, "chart_max": chart_max,
                "chart_total": sum(c["count"] for c in chart)}
    except Exception:
        return {"cards": [], "chart": [], "chart_max": 1, "chart_total": 0}
