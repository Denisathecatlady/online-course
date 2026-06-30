from .services.cart import get_or_create_cart
from .models import Order
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
            "shop_locked": settings.SHOP_LOCKED,
        }

    except Exception:
        return {
            "cart_items_count": 0,
            "app_env": settings.APP_ENV,
            "show_preview_banner": settings.SHOW_PREVIEW_BANNER,
            "shop_locked": settings.SHOP_LOCKED,
        }
