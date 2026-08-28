from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.core import signing
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from .models import Category, MenuItem, Order, OrderItem, Reservation, RestaurantTable, Review


# ---------------------------------------------------------------
# Pages
# ---------------------------------------------------------------
def home(request):
    featured = MenuItem.objects.filter(is_available=True).select_related('category')[:4]
    recent_reviews = (
        Review.objects.select_related('customer', 'menu_item')
        .order_by('-created_at')[:6]
    )
    return render(request, 'home.html', {'featured': featured, 'recent_reviews': recent_reviews})


def menu(request):
    from django.db.models import Avg, Count

    categories = Category.objects.all()
    items = (
        MenuItem.objects.filter(is_available=True)
        .select_related('category')
        .prefetch_related('reviews__customer')
        .annotate(avg_rating=Avg('reviews__rating'), review_count=Count('reviews'))
    )
    return render(request, 'menu.html', {'categories': categories, 'items': items})


def reservation(request):
    tables = RestaurantTable.objects.all()
    my_reservations = []
    if request.user.is_authenticated:
        my_reservations = Reservation.objects.filter(customer=request.user).select_related('table')[:5]
    return render(request, 'reservation.html', {'tables': tables, 'my_reservations': my_reservations})


def order_tracking(request):
    orders = []
    my_reviews = {}
    if request.user.is_authenticated:
        orders = (
            Order.objects.filter(customer=request.user)
            .prefetch_related('items__menu_item')
            .order_by('-created_at')[:5]
        )
        my_reviews = {
            r.menu_item_id: r.id
            for r in Review.objects.filter(customer=request.user)
        }
    return render(request, 'order_tracking.html', {
        'orders': orders,
        'reviewed_item_ids': set(my_reviews.keys()),
        'my_reviews': my_reviews,
    })


def submit_review(request):
    if request.method != 'POST':
        return redirect('order_tracking')

    if not request.user.is_authenticated:
        messages.info(request, "Please login first to leave a review.")
        return redirect('login')

    item_id = request.POST.get('menu_item_id')
    rating = request.POST.get('rating')
    comment = request.POST.get('comment', '').strip()

    try:
        rating = int(rating)
        assert 1 <= rating <= 5
    except (TypeError, ValueError, AssertionError):
        messages.error(request, "Please choose a rating between 1 and 5 stars.")
        return redirect('order_tracking')

    menu_item = MenuItem.objects.filter(id=item_id).first()
    if not menu_item:
        messages.error(request, "That menu item could not be found.")
        return redirect('order_tracking')

    Review.objects.update_or_create(
        customer=request.user,
        menu_item=menu_item,
        defaults={'rating': rating, 'comment': comment},
    )
    messages.success(request, f"Thanks for reviewing {menu_item.name}!")
    return redirect('order_tracking')


def delete_review(request, review_id):
    if request.method != 'POST':
        return redirect('order_tracking')
    if not request.user.is_authenticated:
        return redirect('login')

    review = Review.objects.filter(id=review_id, customer=request.user).first()
    if review:
        item_name = review.menu_item.name
        review.delete()
        messages.success(request, f"Your review for {item_name} has been removed.")
    else:
        messages.error(request, "That review could not be found.")
    return redirect('order_tracking')


# ---------------------------------------------------------------
# Cart (stored in the session as {menu_item_id: quantity})
# ---------------------------------------------------------------
def cart_view(request):
    cart = request.session.get('cart', {})
    ids = [int(i) for i in cart.keys()]
    menu_items = MenuItem.objects.filter(id__in=ids)

    cart_items = []
    subtotal = Decimal('0')
    for mi in menu_items:
        qty = cart[str(mi.id)]
        line_total = mi.price * qty
        subtotal += line_total
        cart_items.append({'item': mi, 'qty': qty, 'line_total': line_total})

    delivery_fee = Decimal('40') if cart_items else Decimal('0')
    total = subtotal + delivery_fee

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'delivery_fee': delivery_fee,
        'total': total,
    })


def add_to_cart(request, item_id):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        key = str(item_id)
        cart[key] = cart.get(key, 0) + 1
        request.session['cart'] = cart
        request.session.modified = True
        messages.success(request, "Added to cart.")
    return redirect(request.POST.get('next') or 'cart')


def decrease_cart_item(request, item_id):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        key = str(item_id)
        if key in cart:
            cart[key] -= 1
            if cart[key] <= 0:
                cart.pop(key)
        request.session['cart'] = cart
        request.session.modified = True
    return redirect('cart')


def remove_from_cart(request, item_id):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        cart.pop(str(item_id), None)
        request.session['cart'] = cart
        request.session.modified = True
    return redirect('cart')


def checkout(request):
    if request.method != 'POST':
        return redirect('cart')

    if not request.user.is_authenticated:
        messages.info(
            request,
            "Please login first to place your order."
        )
        return redirect('login')

    cart = request.session.get('cart', {})

    if not cart:
        messages.error(
            request,
            "Your cart is empty."
        )
        return redirect('cart')

    payment_method = request.POST.get(
        'payment_method',
        'cod'
    )

    # -------------------------------------------------------
    # 1. CREATE ORDER
    # -------------------------------------------------------

    order = Order.objects.create(
        customer=request.user,
        payment_method=payment_method
    )

    # -------------------------------------------------------
    # 2. CREATE ORDER ITEMS
    # -------------------------------------------------------

    ids = [int(i) for i in cart.keys()]

    for mi in MenuItem.objects.filter(id__in=ids):

        OrderItem.objects.create(
            order=order,
            menu_item=mi,
            quantity=cart[str(mi.id)],
            unit_price=mi.price,
        )

    # -------------------------------------------------------
    # 3. CLEAR CART
    # -------------------------------------------------------

    request.session['cart'] = {}
    request.session.modified = True

    # -------------------------------------------------------
    # 4. SEND ORDER EMAIL
    # -------------------------------------------------------

    if request.user.email:

        order_items = (
            order.items
            .select_related('menu_item')
            .all()
        )

        item_lines = ""

        for item in order_items:

            item_lines += (
                f"{item.menu_item.name} "
                f"x{item.quantity} "
                f"— Tk {item.line_total:.0f}\n"
            )

        email_message = (
            f"Hi {request.user.first_name or request.user.username},\n\n"

            f"Thank you for ordering from DineSmart!\n\n"

            f"Your order has been received successfully.\n\n"

            f"Order ID: #DS-{order.id}\n"
            f"Payment Method: "
            f"{order.get_payment_method_display()}\n"
            f"Status: {order.get_status_display()}\n\n"

            f"ORDER ITEMS\n"
            f"--------------------\n"
            f"{item_lines}\n"

            f"Delivery Fee: "
            f"Tk {order.delivery_fee:.0f}\n"

            f"Total: "
            f"Tk {order.total:.0f}\n\n"

            f"You can track your order from "
            f"your DineSmart account.\n\n"

            f"Thank you for choosing DineSmart!\n\n"

            f"— DineSmart Team"
        )

        send_mail(
            subject=f"DineSmart — Order #{order.id} Received",

            message=email_message,

            from_email=settings.DEFAULT_FROM_EMAIL,

            recipient_list=[request.user.email],

            fail_silently=False,
        )

    # -------------------------------------------------------
    # 5. COD ORDER
    # -------------------------------------------------------

    if payment_method == 'cod':

        messages.success(
            request,
            f"Order #{order.id} received successfully! "
            f"A confirmation email has been sent."
        )

        return redirect('order_tracking')

    # -------------------------------------------------------
    # 6. ONLINE PAYMENT
    # -------------------------------------------------------

    return redirect(
        'payment_simulate',
        order_id=order.id
    )


# ===============================================================
# CUSTOMER ORDER CANCELLATION
# ===============================================================

@login_required
@require_POST
def cancel_order(request, order_id):

    order = get_object_or_404(
        Order,
        id=order_id,
        customer=request.user,
    )

    # Customer can cancel only pending orders
    if order.status != "pending":

        messages.error(
            request,
            "This order can no longer be cancelled."
        )

        return redirect("order_tracking")

    # Change order status
    order.status = "cancelled"

    order.save(
        update_fields=["status"]
    )

    messages.success(
        request,
        f"Order #{order.id} has been cancelled successfully."
    )

    return redirect("order_tracking")
# ---------------------------------------------------------------
# Payment simulation
#
# Real bKash/Nagad/Rocket/card integrations require a registered
# merchant account and sandbox API credentials from each provider —
# not something a student project can get instantly. This screen
# mimics that checkout step (enter phone/PIN or card details) so the
# full user flow works end-to-end. Swap in the real gateway SDK here
# later without changing anything else in the app.
# ---------------------------------------------------------------
def payment_simulate(request, order_id):
    order = Order.objects.filter(
        id=order_id,
        customer=request.user
    ).first()

    if not order:
        messages.error(request, "Order not found.")
        return redirect('cart')

    if order.is_paid or order.status == 'cancelled':
        return redirect('order_tracking')

    if request.method == 'POST':

        action = request.POST.get('action')

        # =====================================================
        # PAYMENT SUCCESS
        # =====================================================

        if action == 'pay':

            import random
            from django.utils import timezone

            # -------------------------------------------------
            # Generate transaction ID
            # -------------------------------------------------

            transaction_id = (
                f"TXN{random.randint(10**9, 10**10 - 1)}"
            )

            # -------------------------------------------------
            # Update payment/order status
            # -------------------------------------------------

            order.is_paid = True
            order.status = 'confirmed'
            order.transaction_id = transaction_id
            order.paid_at = timezone.now()

            order.save(
                update_fields=[
                    'is_paid',
                    'status',
                    'transaction_id',
                    'paid_at',
                    'updated_at'
                ]
            )

            # =================================================
            # SEND REAL ORDER CONFIRMATION EMAIL
            # =================================================

            if request.user.email:

                order_items = (
                    order.items
                    .select_related('menu_item')
                    .all()
                )

                item_lines = ""

                for item in order_items:

                    item_lines += (
                        f"{item.menu_item.name} "
                        f"x{item.quantity} "
                        f"— Tk {item.line_total:.0f}\n"
                    )

                email_message = (
                    f"Hi {request.user.first_name or request.user.username},\n\n"

                    f"Thank you for ordering from DineSmart!\n\n"

                    f"Your payment was successful and your order "
                    f"has been confirmed.\n\n"

                    f"Order ID: #DS-{order.id}\n"
                    f"Payment Method: "
                    f"{order.get_payment_method_display()}\n"
                    f"Payment Status: Paid\n"
                    f"Order Status: Confirmed\n"
                    f"Transaction ID: {order.transaction_id}\n"
                    f"Paid At: "
                    f"{order.paid_at.strftime('%d %B %Y, %I:%M %p')}\n\n"

                    f"ORDER ITEMS\n"
                    f"--------------------\n"
                    f"{item_lines}\n"

                    f"Delivery Fee: "
                    f"Tk {order.delivery_fee:.0f}\n"

                    f"Total Paid: "
                    f"Tk {order.total:.0f}\n\n"

                    f"You can track your order from your "
                    f"DineSmart account.\n\n"

                    f"Thank you for choosing DineSmart!\n\n"

                    f"— DineSmart Team"
                )

                send_mail(
                    subject=(
                        f"DineSmart — Payment Successful "
                        f"for Order #{order.id}"
                    ),

                    message=email_message,

                    from_email=settings.DEFAULT_FROM_EMAIL,

                    recipient_list=[
                        request.user.email
                    ],

                    fail_silently=False,
                )

            # -------------------------------------------------
            # Success message
            # -------------------------------------------------

            messages.success(
                request,
                f"Payment received via "
                f"{order.get_payment_method_display()}! "
                f"Order #{order.id} confirmed. "
                f"Transaction ID: {order.transaction_id}"
            )

            return redirect('order_tracking')

        # =====================================================
        # PAYMENT CANCELLED
        # =====================================================

        else:

            order.status = 'cancelled'

            order.save(
                update_fields=[
                    'status',
                    'updated_at'
                ]
            )

            messages.info(
                request,
                "Payment cancelled — your order was not placed."
            )

            return redirect('cart')

    # =========================================================
    # PAYMENT PAGE
    # =========================================================

    BRANDS = {
        'bkash': {
            'name': 'bKash',
            'color': '#E2136E'
        },

        'nagad': {
            'name': 'Nagad',
            'color': '#F6921E'
        },

        'rocket': {
            'name': 'Rocket',
            'color': '#8C3494'
        },
    }

    brand = BRANDS.get(order.payment_method)

    return render(
        request,
        'payment_simulate.html',
        {
            'order': order,
            'brand': brand
        }
    )

# ---------------------------------------------------------------
# Table reservation — conflict-free booking
# ---------------------------------------------------------------
def book_reservation(request):
    if request.method != 'POST':
        return redirect('reservation')

    if not request.user.is_authenticated:
        messages.info(request, "Please login first to book a table.")
        return redirect('login')

    table_id = request.POST.get('table_id')
    date = request.POST.get('date')
    slot_start = request.POST.get('slot_start')
    slot_end = request.POST.get('slot_end')
    party_size = request.POST.get('party_size') or 2

    if not (table_id and date and slot_start and slot_end):
        messages.error(request, "Please pick a date and time slot before booking.")
        return redirect('reservation')

    try:
        with transaction.atomic():
            # Lock the table row so no other request can book it at the same
            # instant — this is what makes the booking conflict-free.
            table = RestaurantTable.objects.select_for_update().get(id=table_id)

            already_booked = Reservation.objects.select_for_update().filter(
                table=table, date=date, slot_start=slot_start, status__in=['pending', 'confirmed']
            ).exists()

            if already_booked:
                messages.error(
                    request,
                    f"Sorry — {table.label} was just booked for that slot by someone else. "
                    f"Please pick another slot or table."
                )
                return redirect('reservation')

            Reservation.objects.create(
                customer=request.user,
                table=table,
                date=date,
                slot_start=slot_start,
                slot_end=slot_end,
                party_size=party_size,
            )
            _notify_customer(
    request.user,
    f"DineSmart — Booking request received for {table.label}",
    f"Hi {request.user.first_name or request.user.username},\n\n"
    f"We've received your table booking request:\n"
    f"{table.label} on {date} at {slot_start} for {party_size} people.\n\n"
    f"Status: Pending — our staff will confirm it shortly.\n\n"
    f"— DineSmart",
)
            messages.success(
                request,
                f"Booking request sent for {table.label} on {date} at {slot_start}. "
                f"You'll see it as Pending until the restaurant confirms it."
            )
    except RestaurantTable.DoesNotExist:
        messages.error(request, "Selected table was not found.")

    return redirect('reservation')
@login_required
@require_POST
def cancel_reservation(request, reservation_id):
    reservation = get_object_or_404(
        Reservation,
        id=reservation_id,
        customer=request.user,
    )

    # Customer can cancel only pending or confirmed reservations
    if reservation.status not in ["pending", "confirmed"]:
        messages.error(
            request,
            "This reservation can no longer be cancelled."
        )
        return redirect("reservation")

    reservation.status = "cancelled"
    reservation.save(update_fields=["status"])

    # Send cancellation email
    _notify_customer(
        request.user,
        f"DineSmart — Reservation #{reservation.id} Cancelled",
        f"Hi {request.user.first_name or request.user.username},\n\n"
        f"Your table reservation has been cancelled successfully.\n\n"
        f"Table: {reservation.table.label}\n"
        f"Date: {reservation.date}\n"
        f"Time: {reservation.slot_start.strftime('%I:%M %p')}\n"
        f"Guests: {reservation.party_size}\n\n"
        f"— DineSmart",
    )

    messages.success(
        request,
        f"Your reservation for {reservation.table.label} has been cancelled."
    )

    return redirect("reservation")

# ---------------------------------------------------------------
# Auth
# ---------------------------------------------------------------
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = None
        try:
            username = User.objects.get(email__iexact=email).username
            user = authenticate(request, username=username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect('home')
        messages.error(request, "Invalid email or password.")

    return render(request, 'login.html')


def register_view(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if password != password2:
            messages.error(request, "Passwords do not match.")
        elif User.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email already exists.")
        else:
            user = User.objects.create_user(
                username=email, email=email, password=password, first_name=full_name
            )
            auth_login(request, user)
            messages.success(request, f"Welcome to DineSmart, {full_name}!")
            return redirect('home')

    return render(request, 'register.html')


def logout_view(request):
    auth_logout(request)
    return redirect('home')


# ---------------------------------------------------------------
# AI Chatbot endpoint (called via fetch() from the widget in base.html)
# ---------------------------------------------------------------
def chatbot_ask(request):
    if request.method != 'POST':
        return JsonResponse({'reply': 'Use POST.'}, status=405)

    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        data = request.POST

    message = (data.get('message') or '').strip()
    if not message:
        return JsonResponse({'reply': "Please type a question first."})

    from .chatbot import ask_chatbot
    try:
        reply = ask_chatbot(message, user=request.user)
    except Exception as e:
        reply = f"Sorry, the AI assistant hit an error: {e}"

    return JsonResponse({'reply': reply})


# ---------------------------------------------------------------
# Staff dashboard — custom DineSmart-styled admin panel
# (separate from the generic Django /admin/) for accepting orders
# and confirming table reservations.
# ---------------------------------------------------------------
def staff_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('staff_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            auth_login(request, user)
            return redirect('staff_dashboard')
        messages.error(request, "Invalid staff credentials.")

    return render(request, 'staff_login.html')


def _staff_required(request):
    return request.user.is_authenticated and request.user.is_staff


def staff_dashboard(request):
    if not _staff_required(request):
        messages.info(request, "Please login with a staff account first.")
        return redirect('staff_login')

    pending_orders = (
        Order.objects.filter(status='pending')
        .select_related('customer')
        .prefetch_related('items__menu_item')
        .order_by('created_at')
    )
    active_orders = (
        Order.objects.filter(status__in=['preparing', 'ready'])
        .select_related('customer')
        .prefetch_related('items__menu_item')
        .order_by('created_at')
    )
    pending_reservations = (
        Reservation.objects.filter(status='pending')
        .select_related('customer', 'table')
        .order_by('date', 'slot_start')
    )
    upcoming_reservations = (
        Reservation.objects.filter(status='confirmed')
        .select_related('customer', 'table')
        .order_by('date', 'slot_start')[:10]
    )
    menu_items = MenuItem.objects.select_related('category').order_by('category__name', 'name')

    return render(request, 'staff_dashboard.html', {
        'pending_orders': pending_orders,
        'active_orders': active_orders,
        'pending_reservations': pending_reservations,
        'upcoming_reservations': upcoming_reservations,
        'menu_items': menu_items,
    })


def admin_menu_form(request, item_id=None):
    if not _staff_required(request):
        return redirect('staff_login')

    item = MenuItem.objects.filter(id=item_id).first() if item_id else None
    categories = Category.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        description = request.POST.get('description', '').strip()
        spice_level = request.POST.get('spice_level', '')
        is_available = bool(request.POST.get('is_available'))
        image_url = request.POST.get('image_url', '').strip()
        uploaded_image = request.FILES.get('image')

        if not name or not category_id or not price:
            messages.error(request, "Name, category, and price are required.")
        else:
            if item is None:
                item = MenuItem(category_id=category_id)
            else:
                item.category_id = category_id
            item.name = name
            item.price = price
            item.description = description
            item.spice_level = spice_level
            item.is_available = is_available
            item.image_url = image_url
            if uploaded_image:
                item.image = uploaded_image
            item.save()
            messages.success(request, f"'{item.name}' saved.")
            return redirect('staff_dashboard')

    return render(request, 'admin_menu_form.html', {'item': item, 'categories': categories})


def admin_menu_delete(request, item_id):
    if not _staff_required(request):
        return redirect('staff_login')
    if request.method == 'POST':
        item = MenuItem.objects.filter(id=item_id).first()
        if item:
            try:
                name = item.name
                item.delete()
                messages.success(request, f"'{name}' deleted.")
            except Exception:
                # It's referenced by existing orders/reviews (protected) —
                # hide it from the menu instead of a hard delete.
                item.is_available = False
                item.save(update_fields=['is_available'])
                messages.info(
                    request,
                    f"'{item.name}' is part of past orders, so it can't be fully deleted — "
                    f"marked as unavailable instead."
                )
    return redirect('staff_dashboard')


def _notify_customer(user, subject, message):
    """Send a status-update email to the customer. Uses the console email
    backend in development, so it prints into the runserver terminal —
    swap EMAIL_BACKEND in settings.py for real SMTP to actually send it."""
    if not user.email:
        return
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    except Exception:
        pass


def staff_update_order(request, order_id, new_status):
    if not _staff_required(request):
        return redirect('staff_login')
    if request.method == 'POST' and new_status in dict(Order.STATUS_CHOICES):
        order = Order.objects.filter(id=order_id).first()
        if order:
            order.status = new_status
            order.save(update_fields=['status', 'updated_at'])
            messages.success(request, f"Order #{order.id} marked as {order.get_status_display()}.")
            _notify_customer(
                order.customer,
                f"DineSmart — Order #DS-{order.id} is now {order.get_status_display()}",
                f"Hi {order.customer.first_name or order.customer.username},\n\n"
                f"Your order #DS-{order.id} (Tk {order.total:.0f}) is now: {order.get_status_display()}.\n\n"
                f"Track it anytime at /orders/.\n\n— DineSmart",
            )
    return redirect('staff_dashboard')


def staff_update_reservation(request, reservation_id, new_status):
    if not _staff_required(request):
        return redirect('staff_login')
    if request.method == 'POST' and new_status in dict(Reservation.STATUS_CHOICES):
        reservation = Reservation.objects.filter(id=reservation_id).first()
        if reservation:
            reservation.status = new_status
            reservation.save(update_fields=['status'])
            messages.success(
                request,
                f"{reservation.table.label} reservation for {reservation.date} marked as "
                f"{reservation.get_status_display()}."
            )
            _notify_customer(
                reservation.customer,
                f"DineSmart — Your table booking is {reservation.get_status_display()}",
                f"Hi {reservation.customer.first_name or reservation.customer.username},\n\n"
                f"Your booking for {reservation.table.label} on {reservation.date} at "
                f"{reservation.slot_start} is now: {reservation.get_status_display()}.\n\n"
                f"— DineSmart",
            )
    return redirect('staff_dashboard')
def reservation_attendance(request, token):
    """
    Handle YES / NO response from the reservation attendance email.
    The signed token makes the link specific to one reservation
    and valid only for a limited time.
    """

    try:
        data = signing.loads(
            token,
            salt="dinesmart-reservation-attendance",
            max_age=600
        )
    except signing.BadSignature:
        return render(
            request,
            "reservation_attendance.html",
            {
                "success": False,
                "message": "This attendance link is invalid or has expired."
            }
        )

    reservation_id = data.get("reservation_id")
    action = data.get("action")

    reservation = (
        Reservation.objects
        .select_related("customer", "table")
        .filter(id=reservation_id)
        .first()
    )

    if not reservation:
        return render(
            request,
            "reservation_attendance.html",
            {
                "success": False,
                "message": "Reservation not found."
            }
        )

    # Already handled
    if reservation.status != "confirmed":
        return render(
            request,
            "reservation_attendance.html",
            {
                "success": False,
                "message": (
                    f"This reservation is already "
                    f"{reservation.get_status_display().lower()}."
                )
            }
        )

    now = timezone.now()

    # Check 10-minute deadline
    if reservation.attendance_prompt_sent_at:
        deadline = reservation.attendance_prompt_sent_at + timedelta(minutes=10)

        if now > deadline:
            reservation.status = "cancelled"
            reservation.save(update_fields=["status"])

            if reservation.customer.email:
                send_mail(
                    "DineSmart — Reservation Cancelled",
                    (
                        f"Hi {reservation.customer.first_name or reservation.customer.username},\n\n"
                        f"Your reservation for {reservation.table.label} "
                        f"was automatically cancelled because we did not "
                        f"receive your arrival confirmation within 10 minutes.\n\n"
                        f"— DineSmart"
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    [reservation.customer.email],
                    fail_silently=True,
                )

            return render(
                request,
                "reservation_attendance.html",
                {
                    "success": False,
                    "message": (
                        "The 10-minute response period has expired. "
                        "Your reservation has been cancelled."
                    )
                }
            )

    # Customer says YES
    if action == "yes":

        reservation.attendance_response = "yes"
        reservation.attendance_responded_at = now
        reservation.status = "completed"

        reservation.save(
            update_fields=[
                "attendance_response",
                "attendance_responded_at",
                "status",
            ]
        )

        return render(
            request,
            "reservation_attendance.html",
            {
                "success": True,
                "message": (
                    "Thank you! Your arrival has been confirmed. "
                    "We hope you enjoy your meal!"
                )
            }
        )

    # Customer says NO
    elif action == "no":

        reservation.attendance_response = "no"
        reservation.attendance_responded_at = now
        reservation.status = "cancelled"

        reservation.save(
            update_fields=[
                "attendance_response",
                "attendance_responded_at",
                "status",
            ]
        )

        if reservation.customer.email:
            send_mail(
                "DineSmart — Reservation Cancelled",
                (
                    f"Hi {reservation.customer.first_name or reservation.customer.username},\n\n"
                    f"Your reservation for {reservation.table.label} "
                    f"has been cancelled as requested.\n\n"
                    f"Thank you for letting us know.\n\n"
                    f"— DineSmart"
                ),
                settings.DEFAULT_FROM_EMAIL,
                [reservation.customer.email],
                fail_silently=True,
            )

        return render(
            request,
            "reservation_attendance.html",
            {
                "success": True,
                "message": (
                    "Your reservation has been cancelled successfully."
                )
            }
        )

    return render(
        request,
        "reservation_attendance.html",
        {
            "success": False,
            "message": "Invalid attendance response."
        }
    )