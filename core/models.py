from django.conf import settings
from django.db import models


# ---------------------------------------------------------------
# Menu
# ---------------------------------------------------------------
class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    SPICE_CHOICES = [
        ("mild", "Mild"),
        ("medium", "Medium"),
        ("spicy", "Spicy"),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    spice_level = models.CharField(max_length=10, choices=SPICE_CHOICES, blank=True)
    image = models.ImageField(upload_to="menu_items/", blank=True, null=True)
    image_url = models.URLField(blank=True, help_text="Used only if no image is uploaded above.")
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    @property
    def display_image(self):
        """Prefer a real uploaded photo; fall back to the placeholder URL."""
        if self.image:
            return self.image.url
        return self.image_url


# ---------------------------------------------------------------
# Orders
# ---------------------------------------------------------------
class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("bkash", "bKash"),
        ("nagad", "Nagad"),
        ("rocket", "Rocket"),
        ("card", "Card"),
        ("cod", "Cash on Delivery"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default="cod")
    is_paid = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=40, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=40)
    delivery_address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} — {self.customer}"

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())

    @property
    def total(self):
        return self.subtotal + self.delivery_fee


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


# ---------------------------------------------------------------
# Table Reservation  (Parallel Seat Allocation lives in the view,
# using select_for_update() + unique_together as a DB-level guard)
# ---------------------------------------------------------------
class RestaurantTable(models.Model):
    label = models.CharField(max_length=30, unique=True)   # e.g. "Table #5"
    capacity = models.PositiveIntegerField(default=4)

    def __str__(self):
        return self.label


class Reservation(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    # No-show / attendance tracking
    attendance_prompt_sent_at = models.DateTimeField(
        null=True,
        blank=True
    )

    attendance_response = models.CharField(
        max_length=10,
        choices=[
            ("yes", "Yes, arrived"),
            ("no", "Not coming"),
        ],
        blank=True,
        default=""
    )

    attendance_responded_at = models.DateTimeField(
        null=True,
        blank=True
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations"
    )

    table = models.ForeignKey(
        RestaurantTable,
        on_delete=models.CASCADE,
        related_name="reservations"
    )

    date = models.DateField()
    slot_start = models.TimeField()
    slot_end = models.TimeField()
    party_size = models.PositiveIntegerField(default=2)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # DB-level guard: the same table cannot be double-booked
        # for the same slot
        unique_together = ("table", "date", "slot_start")
        ordering = ["date", "slot_start"]

    def __str__(self):
        return f"{self.table} on {self.date} {self.slot_start}"

# ---------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------
class Review(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()  # 1-5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rating}★ — {self.menu_item.name}"

