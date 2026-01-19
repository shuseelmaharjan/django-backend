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

            phone = os.environ.get("DEFAULT_ADMIN_PHONE", "").strip()
            password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "")

            # optional fields
            email = os.environ.get("DEFAULT_ADMIN_EMAIL", "").strip().lower()
            first_name = os.environ.get("DEFAULT_ADMIN_FIRST_NAME", "").strip()
            middle_name = os.environ.get("DEFAULT_ADMIN_MIDDLE_NAME", "").strip()
            last_name = os.environ.get("DEFAULT_ADMIN_LAST_NAME", "").strip()

            if not phone or not password:
                logger.warning("Admin seed skipped: phone or password missing in env.")
                return

            su = User.objects.create_superuser(
                phone=phone,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )

            # middle_name isn't in AbstractUser; it's your custom field
            if middle_name:
                su.middle_name = middle_name
                su.save(update_fields=["middle_name"])

            logger.info("Seeded default super admin phone=%s", phone)

        except (OperationalError, ProgrammingError):
            # DB not ready (migrations not applied)
            return
        except Exception:
            logger.exception("Startup admin seeding failed.")
