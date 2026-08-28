from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from core.models import Reservation


class Command(BaseCommand):
    help = "Send reservation attendance emails and cancel no-shows."

    def handle(self, *args, **options):

        now = timezone.localtime()

        # ==========================================================
        # 1. SEND ATTENDANCE EMAIL WHEN BOOKING TIME STARTS
        # ==========================================================

        reservations = (
            Reservation.objects
            .filter(
                status="confirmed",
                attendance_prompt_sent_at__isnull=True,
                date=now.date(),
                slot_start__lte=now.time(),
            )
            .select_related("customer", "table")
        )

        for reservation in reservations:

            if not reservation.customer.email:
                continue

            # Create secure YES token
            yes_token = signing.dumps(
                {
                    "reservation_id": reservation.id,
                    "action": "yes",
                },
                salt="dinesmart-reservation-attendance",
            )

            # Create secure NO token
            no_token = signing.dumps(
                {
                    "reservation_id": reservation.id,
                    "action": "no",
                },
                salt="dinesmart-reservation-attendance",
            )

            yes_url = (
                settings.SITE_URL
                + reverse(
                    "reservation_attendance",
                    kwargs={"token": yes_token},
                )
            )

            no_url = (
                settings.SITE_URL
                + reverse(
                    "reservation_attendance",
                    kwargs={"token": no_token},
                )
            )

            subject = "DineSmart — Are you at the restaurant?"

            text_message = (
                f"Hi {reservation.customer.first_name or reservation.customer.username},\n\n"
                f"Your table booking time has started.\n\n"
                f"Table: {reservation.table.label}\n"
                f"Time: {reservation.slot_start.strftime('%I:%M %p')}\n"
                f"Guests: {reservation.party_size}\n\n"
                f"Please confirm your arrival within 10 minutes.\n\n"
                f"YES, I'M HERE:\n{yes_url}\n\n"
                f"I'M NOT COMING:\n{no_url}\n\n"
                f"If we don't receive a response within 10 minutes, "
                f"your reservation will be automatically cancelled.\n\n"
                f"— DineSmart"
            )

            html_message = f"""
            <div style="
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: auto;
                padding: 30px;
            ">

                <h2 style="color:#003049;">
                    DineSmart
                </h2>

                <h3>
                    Are you at the restaurant?
                </h3>

                <p>
                    Hi {reservation.customer.first_name or reservation.customer.username},
                </p>

                <p>
                    Your table booking time has started.
                    Please confirm whether you have arrived.
                </p>

                <div style="
                    background:#f5f5f5;
                    padding:20px;
                    border-radius:10px;
                    margin:20px 0;
                ">
                    <strong>Table:</strong>
                    {reservation.table.label}
                    <br>

                    <strong>Time:</strong>
                    {reservation.slot_start.strftime('%I:%M %p')}
                    <br>

                    <strong>Guests:</strong>
                    {reservation.party_size}
                </div>

                <p>
                    Please respond within
                    <strong>10 minutes</strong>.
                </p>

                <p>

                    <a href="{yes_url}"
                       style="
                       display:inline-block;
                       background:#16a34a;
                       color:white;
                       padding:12px 20px;
                       text-decoration:none;
                       border-radius:6px;
                       margin-right:10px;
                       ">
                        YES, I'M HERE
                    </a>

                    <a href="{no_url}"
                       style="
                       display:inline-block;
                       background:#dc2626;
                       color:white;
                       padding:12px 20px;
                       text-decoration:none;
                       border-radius:6px;
                       ">
                        I'M NOT COMING
                    </a>

                </p>

                <p style="color:#666;">
                    If we don't receive a response within 10 minutes,
                    your reservation will be automatically cancelled.
                </p>

                <p>
                    — DineSmart
                </p>

            </div>
            """

            send_mail(
                subject,
                text_message,
                settings.DEFAULT_FROM_EMAIL,
                [reservation.customer.email],
                html_message=html_message,
                fail_silently=False,
            )

            reservation.attendance_prompt_sent_at = now

            reservation.save(
                update_fields=["attendance_prompt_sent_at"]
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Attendance email sent for reservation #{reservation.id}"
                )
            )

        # ==========================================================
        # 2. AUTOMATICALLY CANCEL AFTER 10 MINUTES
        # ==========================================================

        deadline = now - timedelta(minutes=10)

        no_shows = (
            Reservation.objects
            .filter(
                status="confirmed",
                attendance_prompt_sent_at__isnull=False,
                attendance_prompt_sent_at__lte=deadline,
                attendance_response="",
            )
            .select_related("customer", "table")
        )

        for reservation in no_shows:

            reservation.status = "cancelled"

            reservation.save(
                update_fields=["status"]
            )

            if reservation.customer.email:

                send_mail(
                    "DineSmart — Reservation Automatically Cancelled",

                    (
                        f"Hi {reservation.customer.first_name or reservation.customer.username},\n\n"
                        f"Your reservation for {reservation.table.label} "
                        f"was automatically cancelled because we did not "
                        f"receive your arrival confirmation within 10 minutes.\n\n"
                        f"— DineSmart"
                    ),

                    settings.DEFAULT_FROM_EMAIL,

                    [reservation.customer.email],

                    fail_silently=False,
                )

            self.stdout.write(
                self.style.WARNING(
                    f"Reservation #{reservation.id} automatically cancelled."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Reservation check completed."
            )
        )