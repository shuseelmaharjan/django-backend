from django.core.management.base import BaseCommand
from django.utils import timezone

from batch.models import AcademicBatch, BatchStatus


class Command(BaseCommand):
    help = "Update AcademicBatch status automatically based on dates."

    def handle(self, *args, **options):
        today = timezone.localdate()
        updated = 0

        batches = AcademicBatch.objects.all()

        for batch in batches:
            # Skip archived / deleted
            if batch.status in (BatchStatus.ARCHIVED, BatchStatus.DELETED):
                continue

            old_status = batch.status
            old_active = batch.is_active

            # Decide new status
            if batch.end_date_ad < today:
                batch.status = BatchStatus.EXPIRED
                batch.is_active = False

            elif batch.start_date_ad <= today <= batch.end_date_ad:
                batch.status = BatchStatus.ACTIVE
                batch.is_active = True

            else:
                batch.status = BatchStatus.INACTIVE
                batch.is_active = False

            # Save only if changed
            if batch.status != old_status or batch.is_active != old_active:
                batch.save(update_fields=["status", "is_active", "updated_at"])
                updated += 1

                self.stdout.write(
                    f"Batch {batch.id} ({batch.name}) -> "
                    f"{old_status}/{old_active} → {batch.status}/{batch.is_active}"
                )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {updated} batch(es) updated. Today = {today}"
        ))
