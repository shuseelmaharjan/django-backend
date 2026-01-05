# startup/apps.py
import os
import sys
import logging
from django.apps import AppConfig
from django.db.utils import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

SKIP_COMMANDS = {"makemigrations", "migrate", "collectstatic", "shell", "test"}


class StartupConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "startup"

    def ready(self):
        # Skip seeding during management commands
        if len(sys.argv) > 1 and sys.argv[1] in SKIP_COMMANDS:
            return

        # Allow disabling via env
        if os.environ.get("DISABLE_STARTUP_ADMIN_SEED") == "1":
            return

        try:
            from accounts.models import User

            # If any superuser exists, do nothing
            if User.objects.filter(is_superuser=True).exists():
                return

            email = os.environ.get("DEFAULT_ADMIN_EMAIL", "").strip().lower()
            password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "")
            phone = os.environ.get("DEFAULT_ADMIN_PHONE", "")
            first_name = os.environ.get("DEFAULT_ADMIN_FIRST_NAME", "")
            last_name = os.environ.get("DEFAULT_ADMIN_LAST_NAME", "")

            if not email or not password:
                logger.warning("Admin seed skipped: email or password missing in env.")
                return

            User.objects.create_superuser(
                email=email,
                password=password,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
            )

            logger.info("Seeded default super admin: %s", email)

        except (OperationalError, ProgrammingError):
            # DB not ready (migrations not applied)
            return
        except Exception:
            logger.exception("Startup admin seeding failed.")
