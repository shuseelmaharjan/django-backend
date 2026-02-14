from django.db import transaction
from fees.models import FeeInclude, FeeStructure, FeeScope, FeeStatus
from academics.models import StudentEnrollments

def _applicable_fee_structures(school, batch, academic_class, *, include_upgrade_impact: bool):
    qs = FeeStructure.objects.filter(
        school=school,
        status=FeeStatus.active,
    )

    # If you want “promotion only adds upgrade_impact=True structures”
    if include_upgrade_impact:
        qs = qs.filter(upgrade_impact=True)

    # GLOBAL
    q_global = qs.filter(scope=FeeScope.GLOBAL)

    # BATCH
    q_batch = qs.filter(scope=FeeScope.BATCH, batch=batch)

    # CLASS (in your serializer you required batch+class, but model clean() for CLASS differs)
    q_class = qs.filter(scope=FeeScope.CLASS, academic_class=academic_class)

    # BATCH_CLASS
    q_bc = qs.filter(scope=FeeScope.BATCH_CLASS, batch=batch, academic_class=academic_class)

    return (q_global | q_batch | q_class | q_bc).distinct()

@transaction.atomic
def assign_default_fees_for_enrollment(*, student, enrollment: StudentEnrollments, school, is_promotion: bool):
    """
    - For new enrollment: add all applicable FeeStructures
    - For promotion: you can choose to add only upgrade_impact=True, or add all again for new scope
    """
    batch = enrollment.batch
    academic_class = enrollment.academic_class

    structures = _applicable_fee_structures(
        school=school,
        batch=batch,
        academic_class=academic_class,
        include_upgrade_impact=is_promotion,  # tweak rule here
    )

    to_create = []
    for fs in structures:
        to_create.append(FeeInclude(
            fees=fs,
            user=student,
            batch=batch,
            classroom=academic_class,
            status=FeeStatus.active,
        ))

    # bulk_create with ignore_conflicts works well with your unique constraint
    FeeInclude.objects.bulk_create(to_create, ignore_conflicts=True)
