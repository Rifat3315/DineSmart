import os
import sys
import threading
import time

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Only start the background scheduler when actually running the dev
        # server (not during migrate/makemigrations/shell/etc.), and only in
        # the real worker process — Django's autoreloader spawns a second
        # process, and RUN_MAIN is only set to 'true' in that real one.
        if 'runserver' not in sys.argv:
            return
        if os.environ.get('RUN_MAIN') != 'true':
            return

        def _loop():
            # Wait a moment for the app registry / DB connections to settle.
            time.sleep(5)
            from django.core.management import call_command
            while True:
                try:
                    call_command('check_reservations')
                except Exception as e:
                    print(f"[check_reservations scheduler] error: {e}")
                time.sleep(60)  # run every 1 minute

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        print(" No-show reservation checker started (runs every 60 seconds in the background).")