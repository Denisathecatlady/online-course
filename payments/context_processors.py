from .services.cart import get_or_create_cart
from .models import Order, ShopSettings
from django.conf import settings


def cart_context(request):
    try:
        cart = None

        if request.user.is_authenticated:
            cart = Order.objects.filter(
                user=request.user,
                status=Order.Status.CART
            ).first()
        else:
            cart_id = request.session.get("cart_id")
            if cart_id:
                cart = Order.objects.filter(
                    id=cart_id,
                    status=Order.Status.CART
                ).first()

        count = cart.items.count() if cart else 0

        return {
            "cart_items_count": count,
            "app_env": settings.APP_ENV,
            "show_preview_banner": settings.SHOW_PREVIEW_BANNER,
            "shop_locked": ShopSettings.is_locked(),
            "gtm_id": settings.GOOGLE_TAG_MANAGER_ID,
            "gsc_verification": settings.GOOGLE_SEARCH_CONSOLE_VERIFICATION,
            "cookie_consent_version": settings.COOKIE_CONSENT_VERSION,
            "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
            "recaptcha_enabled": settings.RECAPTCHA_ENABLED,
            "mapy_api_key": settings.MAPY_API_KEY,
        }

    except Exception:
        return {
            "cart_items_count": 0,
            "app_env": settings.APP_ENV,
            "show_preview_banner": settings.SHOW_PREVIEW_BANNER,
            "shop_locked": getattr(settings, "SHOP_LOCKED", False),
            "gtm_id": getattr(settings, "GOOGLE_TAG_MANAGER_ID", ""),
            "gsc_verification": getattr(settings, "GOOGLE_SEARCH_CONSOLE_VERIFICATION", ""),
            "cookie_consent_version": getattr(settings, "COOKIE_CONSENT_VERSION", "1"),
            "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
            "recaptcha_enabled": getattr(settings, "RECAPTCHA_ENABLED", False),
            "mapy_api_key": getattr(settings, "MAPY_API_KEY", ""),
        }
