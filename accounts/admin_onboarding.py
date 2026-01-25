# accounts/views/admin_onboarding.py
from django.db.models import Exists, OuterRef, Q

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated

from accounts.models import User
from schools.models import School
from profiles.models import Profile, Address, ProfileDocument

from common.pagination import MetaPageNumberPagination
from common.mixins import ListFilterMetaMixin
from common.permissions import IsPlatformSuperAdmin

from accounts.services.admin_onboarding import (
    create_admin_user,
    create_school_for_admin,
    create_profile_bundle,
)

from accounts.serializers.admin_onboarding import (
    AdminPersonalInfoCreateSerializer,
    AdminPersonalInfoUpdateSerializer,
    AdminSchoolInfoCreateSerializer,
    AdminSchoolInfoUpdateSerializer,
    AdminClientInfoCreateSerializer,
    AdminBundleReadSerializer,
    ProfileReadSerializer, SchoolReadSerializer,
)

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    OpenApiExample,
    OpenApiParameter,
)


@extend_schema(
    tags=["Admin Onboarding"],
    request=AdminPersonalInfoCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=dict,
            description="Admin created (password generated and emailed).",
            examples=[
                OpenApiExample(
                    "Created",
                    value={
                        "user_id": "7f3a0f0e-8d4b-4f4f-9fbf-2c8cddf8c7a1",
                        "username": "u_12345678",
                        "role": "admin",
                        "status": "active",
                        "message": "Admin user created. Password generated and should be sent via email.",
                    },
                )
            ],
        )
    },
)
class AdminPersonalInfoCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request):
        ser = AdminPersonalInfoCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user = create_admin_user(**ser.validated_data)

        return Response(
            {
                "user_id": str(user.id),
                "username": user.username,
                "role": user.role,
                "status": user.status,
                "message": "Admin user created. Password generated and should be sent via email.",
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Admin Onboarding"],
    request=AdminPersonalInfoUpdateSerializer,
    responses={200: AdminBundleReadSerializer},
)
class AdminPersonalInfoUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def put(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        ser = AdminPersonalInfoUpdateSerializer(instance=user, data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()

        dob_display = request.query_params.get("dob_display", "bs")
        return Response(AdminBundleReadSerializer(user, context={"dob_display": dob_display}).data)

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)


        dob_display = request.query_params.get("dob_display", "bs")
        return Response(AdminBundleReadSerializer(user, context={"dob_display": dob_display}).data)


@extend_schema(
    tags=["Admin Onboarding"],
    request=AdminSchoolInfoCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=dict,
            examples=[
                OpenApiExample(
                    "Created",
                    value={
                        "school_id": "b8c9f7c2-6b3f-49e4-a6a6-3d9c1bf6d4f2",
                        "owner_id": "7f3a0f0e-8d4b-4f4f-9fbf-2c8cddf8c7a1",
                        "message": "School created for admin owner.",
                    },
                )
            ],
        )
    },
)
class AdminSchoolInfoCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request):
        ser = AdminSchoolInfoCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        owner_id = ser.validated_data.pop("owner_id")
        owner = get_object_or_404(User, pk=owner_id)

        school = create_school_for_admin(owner=owner, **ser.validated_data)

        return Response(
            {
                "school_id": str(school.id),
                "owner_id": str(owner.id),
                "message": "School created for admin owner.",
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Admin Onboarding"],
    request=AdminSchoolInfoUpdateSerializer,
    responses={200: AdminSchoolInfoUpdateSerializer},
)
class AdminSchoolInfoUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def put(self, request, school_id):
        school = get_object_or_404(School, pk=school_id)
        ser = AdminSchoolInfoUpdateSerializer(instance=school, data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def get(self, request, school_id):
        school = get_object_or_404(School, pk=school_id)
        ser = SchoolReadSerializer(instance=school, context={'request': request})
        return Response(ser.data)


@extend_schema(
    tags=["Admin Onboarding"],
    request=AdminClientInfoCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=dict,
            examples=[
                OpenApiExample(
                    "Created",
                    value={
                        "profile_id": "0b0f9a3a-52f0-4d91-9df2-2f1d9b1b2c33",
                        "message": "Profile + Addresses + Documents created/updated.",
                    },
                )
            ],
        )
    },
)
class AdminClientInfoCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request):
        ser = AdminClientInfoCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user = get_object_or_404(User, pk=ser.validated_data["user_id"])
        school = get_object_or_404(School, pk=ser.validated_data["school_id"])

        profile_data = {
            "date_of_birth": ser.validated_data["date_of_birth"],
            "gender": ser.validated_data["gender"],
            "blood_group": ser.validated_data["blood_group"],
            "nationality": ser.validated_data["nationality"],
            "religion": ser.validated_data["religion"],
            "mother_tongue": ser.validated_data["mother_tongue"],
            "citizenship_no": ser.validated_data["citizenship_no"],
            "pan_no": ser.validated_data["pan_no"],
        }

        profile = create_profile_bundle(
            user=user,
            school=school,
            profile_data=profile_data,
            addresses_data=ser.validated_data["addresses"],
            documents_data=ser.validated_data["documents"],
            date_of_birth_type=ser.validated_data["date_of_birth_type"],
            replace_documents=False,
        )

        return Response(
            {
                "profile_id": str(profile.id),
                "message": "Profile + Addresses + Documents created/updated.",
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Admin Onboarding"],
    request=AdminClientInfoCreateSerializer,
    responses={
        200: OpenApiResponse(
            response=dict,
            examples=[OpenApiExample("Updated", value={"profile_id": "...", "message": "Client info updated (upsert)."})],
        )
    },
)
class AdminClientInfoUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def put(self, request, user_id):
        payload = dict(request.data)
        payload["user_id"] = str(user_id)

        ser = AdminClientInfoCreateSerializer(data=payload)
        ser.is_valid(raise_exception=True)

        user = get_object_or_404(User, pk=ser.validated_data["user_id"])
        school = get_object_or_404(School, pk=ser.validated_data["school_id"])

        profile_data = {
            "date_of_birth": ser.validated_data["date_of_birth"],
            "gender": ser.validated_data["gender"],
            "blood_group": ser.validated_data["blood_group"],
            "nationality": ser.validated_data["nationality"],
            "religion": ser.validated_data["religion"],
            "mother_tongue": ser.validated_data["mother_tongue"],
            "citizenship_no": ser.validated_data["citizenship_no"],
            "pan_no": ser.validated_data["pan_no"],
        }

        create_profile_bundle(
            user=user,
            school=school,
            profile_data=profile_data,
            addresses_data=ser.validated_data["addresses"],
            documents_data=ser.validated_data["documents"],
            date_of_birth_type=ser.validated_data["date_of_birth_type"],
            replace_documents=False,
        )

        dob_display = request.query_params.get("dob_display", "bs")
        return Response(
            AdminBundleReadSerializer(user, context={"dob_display": dob_display}).data,
            status=status.HTTP_200_OK,
        )

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        dob_display = request.query_params.get("dob_display", "bs")
        return Response(AdminBundleReadSerializer(user, context={"dob_display": dob_display}).data)



@extend_schema(
    tags=["Admins"],
    parameters=[
        OpenApiParameter(
            name="profile_status",
            required=False,
            type=str,
            description="Filter by completeness: complete or incomplete",
            examples=[
                OpenApiExample("Complete", value="complete"),
                OpenApiExample("Incomplete", value="incomplete"),
            ],
        ),
        OpenApiParameter(name="dob_display", required=False, type=str, description="Return DOB display as bs or ad"),
        OpenApiParameter(name="search", required=False, type=str, description="Search by phone/email/name/username"),
        OpenApiParameter(name="page", required=False, type=int),
        OpenApiParameter(name="page_size", required=False, type=int),
    ],
    responses={200: AdminBundleReadSerializer(many=True)},
)
class AdminListView(ListFilterMetaMixin, ListAPIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]
    serializer_class = AdminBundleReadSerializer
    pagination_class = MetaPageNumberPagination

    public_filter_meta = {
        "profile_status": {"type": "choice", "choices": ["complete", "incomplete"]},
    }
    search_fields = ["phone", "email", "first_name", "last_name", "username"]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["dob_display"] = self.request.query_params.get("dob_display", "bs")
        return ctx

    def get_queryset(self):
        qs = User.objects.all().order_by("-date_joined")

        profile_status = self.request.query_params.get("profile_status")
        if profile_status in ("complete", "incomplete"):
            has_school = Exists(School.objects.filter(owner=OuterRef("pk")))
            has_profile = Exists(Profile.objects.filter(user=OuterRef("pk")))
            has_address = Exists(Address.objects.filter(profile__user=OuterRef("pk")))
            has_docs = Exists(ProfileDocument.objects.filter(profile__user=OuterRef("pk")))

            qs = qs.annotate(
                _has_school=has_school,
                _has_profile=has_profile,
                _has_address=has_address,
                _has_docs=has_docs,
            )

            if profile_status == "complete":
                qs = qs.filter(_has_school=True, _has_profile=True, _has_address=True, _has_docs=True)
            else:
                qs = qs.exclude(_has_school=True, _has_profile=True, _has_address=True, _has_docs=True)

        search = self.request.query_params.get(self.search_param_name)
        if search:
            qs = qs.filter(
                Q(phone__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(username__icontains=search)
            )

        return qs


@extend_schema(tags=["Admins"], responses={200: AdminBundleReadSerializer})
class AdminDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]
    serializer_class = AdminBundleReadSerializer
    queryset = User.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["dob_display"] = self.request.query_params.get("dob_display", "bs")
        return ctx


@extend_schema(
    tags=["Admins"],
    responses={200: OpenApiResponse(response=dict, description="Deleted")},
)
class AdminDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformSuperAdmin]

    def delete(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        School.objects.filter(owner=user).delete()
        user.delete()
        return Response({"message": "Admin deleted."}, status=status.HTTP_200_OK)
