from ..models import Order


def get_or_create_cart(request):
    """
    Vrátí košík podle:
    - přihlášeného uživatele
    - nebo session (nepřihlášený)

    Používá filter().first() místo get_or_create() aby nedošlo k
    MultipleObjectsReturned v případě duplicitních košíků v DB.
    """

    if request.user.is_authenticated:
        cart = Order.objects.filter(
            user=request.user,
            status=Order.Status.CART,
        ).first()
        if cart is None:
            cart = Order.objects.create(
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
