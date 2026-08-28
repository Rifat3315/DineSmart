from django.core.management.base import BaseCommand
from core.models import Category, MenuItem, RestaurantTable


class Command(BaseCommand):
    help = "Seed DineSmart with demo categories, menu items, and tables"

    def handle(self, *args, **options):
        cats = {
            "Biryani": "biryani",
            "Kebab": "kebab",
            "Curry": "curry",
            "Drinks": "drinks",
            "Dessert": "dessert",
        }
        cat_objs = {}
        for i, (name, slug) in enumerate(cats.items()):
            obj, _ = Category.objects.get_or_create(
                slug=slug, defaults={"name": name, "display_order": i}
            )
            cat_objs[name] = obj

        items = [
            ("Kacchi Biryani", "Biryani", 350, "spicy", "https://loremflickr.com/400/300/biryani"),
            ("Morog Polao", "Biryani", 280, "medium", "https://loremflickr.com/400/300/chickenrice"),
            ("Chicken Kebab", "Kebab", 280, "medium", "https://loremflickr.com/400/300/kebab,chicken"),
            ("Seekh Kebab", "Kebab", 220, "spicy", "https://loremflickr.com/400/300/seekhkebab"),
            ("Beef Rezala", "Curry", 420, "spicy", "https://loremflickr.com/400/300/beefcurry"),
            ("Prawn Malaikari", "Curry", 450, "mild", "https://loremflickr.com/400/300/prawncurry"),
            ("Borhani", "Drinks", 60, "", "https://loremflickr.com/400/300/yogurtdrink"),
            ("Matha", "Drinks", 50, "", "https://loremflickr.com/400/300/lassi"),
            ("Firni", "Dessert", 90, "", "https://loremflickr.com/400/300/ricepudding"),
        ]
        for name, cat, price, spice, img in items:
            MenuItem.objects.get_or_create(
                name=name,
                defaults={
                    "category": cat_objs[cat],
                    "price": price,
                    "spice_level": spice,
                    "image_url": img,
                },
            )

        for label, capacity in [("Table #1", 2), ("Table #2", 4), ("Table #5", 4), ("Table #8", 6)]:
            RestaurantTable.objects.get_or_create(label=label, defaults={"capacity": capacity})

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {MenuItem.objects.count()} menu items, "
            f"{Category.objects.count()} categories, "
            f"{RestaurantTable.objects.count()} tables."
        ))
