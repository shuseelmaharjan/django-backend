from django.core.management.base import BaseCommand

from academics.models import StudentEnrollments
from fees.services.wallet_service import rebuild_wallet


class Command(BaseCommand):
    help = "Rebuild StudentFeeWallet summaries from invoices, allocations, and advance credits."

    def add_arguments(self, parser):
        parser.add_argument("--school-id", dest="school_id")
        parser.add_argument("--enrollment-id", dest="enrollment_id")

    def handle(self, *args, **options):
        qs = StudentEnrollments.objects.select_related("student", "batch", "academic_class")
        if options.get("school_id"):
            qs = qs.filter(batch__school_id=options["school_id"])
        if options.get("enrollment_id"):
            qs = qs.filter(id=options["enrollment_id"])

        count = 0
        for enrollment in qs.iterator():
            rebuild_wallet(enrollment=enrollment)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Rebuilt {count} fee wallet(s)."))
