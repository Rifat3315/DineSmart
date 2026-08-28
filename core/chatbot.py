"""
DineSmart AI Assistant
-----------------------
This is a lightweight RAG (Retrieval-Augmented Generation) setup:
we RETRIEVE live facts from the MySQL database (menu, prices, stock,
the customer's own recent order/reservation) and AUGMENT the prompt
sent to the Groq LLM with that data, so answers are grounded in real
restaurant data instead of the model guessing.
"""
from groq import Groq
from django.conf import settings

from .models import MenuItem, Order, Reservation

MODEL_NAME = "openai/gpt-oss-20b"

SYSTEM_PROMPT = """You are DineSmart AI, the friendly assistant for DineSmart,
a Bangladeshi restaurant that takes online orders and table reservations.

Rules:
- Reply in the SAME language the customer used (Bangla or English). If mixed, mix naturally.
- Only answer using the "Live restaurant data" given below. If something isn't in it, say you're
  not sure and suggest they check the Menu page or contact the restaurant — never invent prices,
  dishes, or order details.
- Keep answers short and conversational (2-4 sentences), like a helpful waiter, not a formal report.
- You can help with: menu questions, prices, spice level, recommending dishes, order status,
  reservation status, and general restaurant questions (hours, delivery, payment methods).
- Payment methods accepted: bKash, Nagad, Rocket, Card, Cash on Delivery.
"""


def _build_context(user):
    lines = ["Live restaurant data:", ""]

    lines.append("MENU:")
    for item in MenuItem.objects.filter(is_available=True).select_related("category"):
        spice = f", {item.get_spice_level_display()}" if item.spice_level else ""
        lines.append(f"- {item.name} ({item.category.name}{spice}): Tk {item.price:.0f}")

    if user and user.is_authenticated:
        order = Order.objects.filter(customer=user).order_by("-created_at").first()
        if order:
            items_summary = ", ".join(
                f"{oi.menu_item.name} x{oi.quantity}" for oi in order.items.all()
            )
            lines.append("")
            lines.append(
                f"CUSTOMER'S MOST RECENT ORDER: #DS-{order.id}, status: {order.get_status_display()}, "
                f"items: {items_summary}, total: Tk {order.total:.0f}"
            )

        reservation = Reservation.objects.filter(customer=user).order_by("-created_at").first()
        if reservation:
            lines.append(
                f"CUSTOMER'S MOST RECENT TABLE BOOKING: {reservation.table.label} on "
                f"{reservation.date} at {reservation.slot_start}, status: {reservation.get_status_display()}"
            )
    else:
        lines.append("")
        lines.append("The customer is not logged in, so you cannot see their personal order/booking status.")

    return "\n".join(lines)


def ask_chatbot(message, user=None):
    if not settings.GROQ_API_KEY:
        return (
            "The AI assistant isn't configured yet — the restaurant owner needs to add a "
            "GROQ_API_KEY in the .env file."
        )

    client = Groq(api_key=settings.GROQ_API_KEY)
    context = _build_context(user)

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": context},
            {"role": "user", "content": message},
        ],
        temperature=0.4,
        max_tokens=300,
    )
    return completion.choices[0].message.content.strip()
