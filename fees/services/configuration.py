from __future__ import annotations

from django.db import IntegrityError, transaction

from fees.models import FeeConfiguration


def get_fee_configuration(school) -> FeeConfiguration:
    """Race-safe one-row-per-school configuration lookup."""
    try:
        with transaction.atomic():
            config, _ = FeeConfiguration.objects.get_or_create(school=school)
            return config
    except IntegrityError:
        return FeeConfiguration.objects.get(school=school)
