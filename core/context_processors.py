def cart_count(request):
    """Makes {{ cart_count }} available in every template (navbar badge)."""
    cart = request.session.get('cart', {})
    return {'cart_count': sum(cart.values())}
