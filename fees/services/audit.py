from __future__ import annotations

from fees.models import FeeAuditEvent


def audit(*, school, actor, event_type: str, entity, payload: dict | None = None):
    return FeeAuditEvent.objects.create(
        school=school,
        actor=actor,
        event_type=event_type,
        entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk),
        payload=payload or {},
    )
