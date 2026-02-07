from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from fees.models import FeeStructure, FeeScope, FeeStatus


class Command(BaseCommand):
    help = "Expire FeeStructures where batch end_date_ad has passed (scope: BATCH/CLASS/BATCH_CLASS)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many would be expired without updating.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        today = timezone.localdate()

        qs = (
            FeeStructure.objects.select_related("batch")
            .filter(
                status=FeeStatus.active,
                scope__in=[FeeScope.BATCH, FeeScope.CLASS, FeeScope.BATCH_CLASS],
                batch__isnull=False,
                batch__end_date_ad__isnull=False,
                batch__end_date_ad__lt=today,  # expired
            )
        )

        count = qs.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would expire: {count} fee structures"))
            return

        updated = qs.update(status=FeeStatus.expired)
        self.stdout.write(self.style.SUCCESS(f"Expired: {updated} fee structures"))
