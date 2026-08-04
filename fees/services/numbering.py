from __future__ import annotations

from django.db import IntegrityError, transaction

from fees.models import DocumentSequenceKind, FeeDocumentSequence
from fees.services.configuration import get_fee_configuration


def next_document_number(*, school, kind: str, document_date) -> str:
    """Concurrency-safe numbering for MySQL using a locked sequence row."""
    with transaction.atomic():
        try:
            sequence = FeeDocumentSequence.objects.select_for_update().get(
                school=school,
                kind=kind,
                year=document_date.year,
            )
        except FeeDocumentSequence.DoesNotExist:
            # The inner savepoint keeps the outer transaction usable if another
            # request creates the same sequence row concurrently.
            try:
                with transaction.atomic():
                    FeeDocumentSequence.objects.create(
                        school=school,
                        kind=kind,
                        year=document_date.year,
                        last_number=0,
                    )
            except IntegrityError:
                pass
            sequence = FeeDocumentSequence.objects.select_for_update().get(
                school=school,
                kind=kind,
                year=document_date.year,
            )

        sequence.last_number += 1
        sequence.save(update_fields=["last_number", "updated_at"])
        sequence_value = sequence.last_number

    config = get_fee_configuration(school)
    prefix = config.invoice_prefix if kind == DocumentSequenceKind.INVOICE else config.receipt_prefix
    school_code = str(school.code).upper()
    return f"{school_code}-{prefix.upper()}-{document_date.year}-{sequence_value:06d}"
