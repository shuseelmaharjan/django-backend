# accounts/views.py
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse
from authx.models import UserSession
from accounts.serializers import (ChangePasswordRequestSerializer, ChangePasswordResponseSerializer,
                                  RoleAssignmentMiniSerializer, MyProfileResponseSerializer)


@extend_schema(tags=["01. Auth"])
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change password (requires old password)",
        request=ChangePasswordRequestSerializer,
        responses={200: ChangePasswordResponseSerializer},
    )
    def post(self, request):
        ser = ChangePasswordRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)

        user = request.user
        old_pw = ser.validated_data["oldPassword"]
        new_pw = ser.validated_data["newPassword"]

        # 1) Check old password
        if not user.check_password(old_pw):
            return Response(
                {"detail": "Old password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) Set new password
        user.set_password(new_pw)
        user.save(update_fields=["password"])

        # OPTIONAL SECURITY:
        # Revoke all other sessions so password change kicks other devices out.
        # Keep current session alive.
        current_sid = None

        token = getattr(request, "auth", None)
        if token is not None:
            try:
                current_sid = str(token.get("sid", "")) or None
            except Exception:
                current_sid = None

        qs = UserSession.objects.filter(user=user, revoked_at__isnull=True)
        if current_sid:
            qs = qs.exclude(id=current_sid)

        qs.update(revoked_at=timezone.now())

        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)

def _active_role_assignments(user):
    # If you want only active-by-date roles, use:
    # roles = [ra for ra in user.role_assignments.select_related("role").all() if ra.is_active()]
    return user.role_assignments.select_related("role").all()


def build_profile_payload(user):
    # roles
    roles_qs = user.role_assignments.select_related("role").all()
    roles_data = RoleAssignmentMiniSerializer(roles_qs, many=True).data

    data = {
        "user": {
            "id": str(user.id),
            "username": user.username or "",
            "email": user.email,
            "phone": user.phone or "",
            "status": user.status,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
        },
        "roles": roles_data,
    }

    # staff block
    staff_profile = getattr(user, "staff_profile", None)
    if staff_profile:
        data["staff"] = {
            "id": str(staff_profile.id),
            "school_id": staff_profile.school_id,
            "campus_id": staff_profile.campus_id,
            "staff_type": staff_profile.staff_type,
            "employee_code": staff_profile.employee_code,
            "employment_status": staff_profile.employment_status,
            "joined_date": staff_profile.joined_date,
        }

        teacher_profile = getattr(staff_profile, "teacher_profile", None)
        if teacher_profile:
            data["teacher"] = {
                "id": str(teacher_profile.id),
                "designation": teacher_profile.designation,
                "qualification": teacher_profile.qualification,
                "assignments_count": teacher_profile.assignments.count(),
            }

    # student block
    student_profile = getattr(user, "student_profile", None)
    if student_profile:
        data["student"] = {
            "id": str(student_profile.id),
            "status": student_profile.status,
            "school_id": student_profile.school_id,
            "campus_id": student_profile.campus_id,
            "class_id": student_profile.class_id,
            "section_id": student_profile.section_id,
            "date_of_birth": student_profile.date_of_birth,
            "gender": student_profile.gender,
            "blood_group": student_profile.blood_group,
        }

    return data


def build_profile_payload(user):
    # roles
    roles_qs = user.role_assignments.select_related("role").all()
    roles_data = RoleAssignmentMiniSerializer(roles_qs, many=True).data

    data = {
        "user": {
            "id": str(user.id),
            "username": user.username or "",
            "email": user.email,
            "phone": user.phone or "",
            "status": user.status,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
        },
        "roles": roles_data,
    }

    # staff block
    staff_profile = getattr(user, "staff_profile", None)
    if staff_profile:
        data["staff"] = {
            "id": str(staff_profile.id),
            "school_id": staff_profile.school_id,
            "campus_id": staff_profile.campus_id,
            "staff_type": staff_profile.staff_type,
            "employee_code": staff_profile.employee_code,
            "employment_status": staff_profile.employment_status,
            "joined_date": staff_profile.joined_date,
            "citizenship_no": staff_profile.citizenship_no,
            "pan_no": staff_profile.pan_no,
            "ssf_no": staff_profile.ssf_no,
            "permanent_address": staff_profile.permanent_address,
            "temporary_address": staff_profile.temporary_address,
            "citizenship_file": str(staff_profile.citizenship_file_id) if staff_profile.citizenship_file_id else None,
            "contract_file": str(staff_profile.contract_file_id) if staff_profile.contract_file_id else None,
            "created_at": staff_profile.created_at,
        }

        teacher_profile = getattr(staff_profile, "teacher_profile", None)
        if teacher_profile:
            # include assignments
            assignments = teacher_profile.assignments.select_related(
                "academic_year", "academic_class", "section"
            ).all()

            data["teacher"] = {
                "id": str(teacher_profile.id),
                "designation": teacher_profile.designation,
                "qualification": teacher_profile.qualification,
                "signature_file": str(teacher_profile.signature_file_id) if teacher_profile.signature_file_id else None,
                "assignments": [
                    {
                        "id": str(a.id),
                        "academic_year_id": str(a.academic_year_id),
                        "academic_year_name": a.academic_year.name,
                        "academic_class_id": str(a.academic_class_id),
                        "academic_class_name": a.academic_class.name,
                        "section_id": str(a.section_id) if a.section_id else None,
                        "section_name": a.section.name if a.section else None,
                        "subject_id": a.subject_id,
                        "is_class_teacher": a.is_class_teacher,
                    }
                    for a in assignments
                ],
            }

    # student block
    student_profile = getattr(user, "student_profile", None)
    if student_profile:
        data["student"] = {
            "id": str(student_profile.id),
            "status": student_profile.status,
            "school_id": student_profile.school_id,
            "campus_id": student_profile.campus_id,
            "class_id": student_profile.class_id,
            "section_id": student_profile.section_id,
            "date_of_birth": student_profile.date_of_birth,
            "gender": student_profile.gender,
            "blood_group": student_profile.blood_group,
            "profile_photo": str(student_profile.profile_photo_id) if student_profile.profile_photo_id else None,
            "birth_certificate_no": student_profile.birth_certificate_no,
            "student_national_id": student_profile.student_national_id,
            "created_at": student_profile.created_at,

            "addresses": [
                {
                    "id": str(addr.id),
                    "address_type": addr.address_type,
                    "province": addr.province,
                    "district": addr.district,
                    "municipality": addr.municipality,
                    "ward_no": addr.ward_no,
                    "tole": addr.tole,
                    "street": addr.street,
                    "postal_code": addr.postal_code,
                }
                for addr in student_profile.addresses.all()
            ],
            "guardians": [
                {
                    "id": str(g.id),
                    "guardian_type": g.guardian_type,
                    "full_name": g.full_name,
                    "phone": g.phone,
                    "email": g.email,
                    "occupation": g.occupation,
                    "citizenship_no": g.citizenship_no,
                    "citizenship_document": str(g.citizenship_document_id) if g.citizenship_document_id else None,
                    "is_primary_contact": g.is_primary_contact,
                    "guardian_user_id": str(g.guardian_user_id) if g.guardian_user_id else None,
                }
                for g in student_profile.guardians.all()
            ],
            "documents": [
                {
                    "id": str(d.id),
                    "doc_type": d.doc_type,
                    "title": d.title,
                    "is_required": d.is_required,
                    "is_verified": d.is_verified,
                    "uploaded_at": d.uploaded_at,
                    "file": str(d.file_id),
                }
                for d in student_profile.documents.all()
            ],
        }

    return data

@extend_schema(tags=["01. Auth"])
class ProfileGetView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get my profile (role-aware)",
        responses={200: MyProfileResponseSerializer},
    )
    def get(self, request):
        payload = build_profile_payload(request.user)
        return Response(payload, status=status.HTTP_200_OK)

