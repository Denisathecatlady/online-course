from ..models import Order


def get_or_create_cart(request):
    """
    Vrátí košík podle:
    - přihlášeného uživatele
    - nebo session (nepřihlášený)
    """

    if request.user.is_authenticated:
        cart, created = Order.objects.get_or_create(
            user=request.user,
            status=Order.Status.CART,
        )
        return cart

    # Nepřihlášený uživatel – session košík
    cart_id = request.session.get("cart_id")

    if cart_id:
        try:
            return Order.objects.get(id=cart_id, status=Order.Status.CART)
        except Order.DoesNotExist:
            pass

    cart = Order.objects.create(status=Order.Status.CART)
    request.session["cart_id"] = cart.id

    return cart
