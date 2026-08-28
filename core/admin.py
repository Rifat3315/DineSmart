from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    Category,
    MenuItem,
    Order,
    OrderItem,
    RestaurantTable,
    Reservation,
    Review,
)

admin.site.site_header = "DineSmart Admin"
admin.site.site_title = "DineSmart Admin"
admin.site.index_title = "DineSmart Administration"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = ("name", "slug", "display_order")

    prepopulated_fields = {
        "slug": ("name",)
    }


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "category",
        "price",
        "spice_level",
        "is_available",
    )

    list_filter = (
        "category",
        "is_available",
        "spice_level",
    )

    search_fields = (
        "name",
    )


class OrderItemInline(admin.TabularInline):

    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "customer",
        "status",
        "payment_method",
        "is_paid",
        "total",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_method",
        "is_paid",
    )

    inlines = [
        OrderItemInline
    ]

    def save_model(self, request, obj, form, change):

        # -------------------------------------------------------
        # Check previous order status
        # -------------------------------------------------------

        old_status = None

        if change and obj.pk:

            old_order = Order.objects.get(pk=obj.pk)
            old_status = old_order.status

        # -------------------------------------------------------
        # Save the order first
        # -------------------------------------------------------

        super().save_model(
            request,
            obj,
            form,
            change
        )

        # -------------------------------------------------------
        # Send email ONLY when:
        #
        # Pending → Confirmed
        #
        # This prevents duplicate emails when admin
        # simply saves an already confirmed order.
        # -------------------------------------------------------

        if (
            change
            and old_status == "pending"
            and obj.status == "confirmed"
            and obj.customer.email
        ):

            order_items = (
                obj.items
                .select_related("menu_item")
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
                f"Hi {obj.customer.first_name or obj.customer.username},\n\n"

                f"Good news! Your DineSmart order has been confirmed.\n\n"

                f"Order ID: #DS-{obj.id}\n"
                f"Payment Method: "
                f"{obj.get_payment_method_display()}\n"
                f"Order Status: Confirmed\n\n"

                f"ORDER ITEMS\n"
                f"--------------------\n"
                f"{item_lines}\n"

                f"Delivery Fee: "
                f"Tk {obj.delivery_fee:.0f}\n"

                f"Total: "
                f"Tk {obj.total:.0f}\n\n"

                f"Our restaurant has accepted your order "
                f"and will start preparing it soon.\n\n"

                f"You can track your order from your "
                f"DineSmart account.\n\n"

                f"Thank you for choosing DineSmart!\n\n"

                f"— DineSmart Team"
            )

            send_mail(
                subject=(
                    f"DineSmart — Order #{obj.id} Confirmed"
                ),

                message=email_message,

                from_email=settings.DEFAULT_FROM_EMAIL,

                recipient_list=[
                    obj.customer.email
                ],

                fail_silently=False,
            )


@admin.register(RestaurantTable)
class RestaurantTableAdmin(admin.ModelAdmin):

    list_display = (
        "label",
        "capacity",
    )


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):

    list_display = (
        "table",
        "date",
        "slot_start",
        "slot_end",
        "customer",
        "party_size",
        "status",
    )

    list_filter = (
        "status",
        "date",
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):

    list_display = (
        "menu_item",
        "customer",
        "rating",
        "created_at",
    )

    list_filter = (
        "rating",
    )