from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiResponse

from common.schema import schema
from common.permissions import IsSchoolManagement

from profiles.models import (
    Address,
    AddressType,
    Guardian,
    ProfileDocument,
    StudentOtherInfo,
)

from profiles.serializers_management_profile import (
    ManagementUserSummarySerializer,
    ManagementUserIdentityUpdateSerializer,
    ManagementProfilePictureUpdateSerializer,
    PersonalInfoSerializer,
    PersonalInfoUpdateSerializer,
    AddressSerializer,
    AddressUpdateSerializer,
    GuardianSerializer,
    GuardianCreateUpdateSerializer,
    ProfileDocumentSerializer,
    ProfileDocumentCreateUpdateSerializer,
    StudentHealthSerializer,
    StudentHealthUpdateSerializer,

)

from profiles.services_management_profile import (
    get_managed_user_or_404,
    get_or_create_managed_profile,
)


class ManagedUserCompleteProfileView(APIView):
    permission_classes = [IsSchoolManagement]

    @schema(
        tag="03. School Management Profile",
        summary="Get complete profile of a specific user",
        responses={
            200: OpenApiResponse(
                description="Complete user profile data."
            ),
            404: OpenApiResponse(
                description="User not found in the managed school."
            ),
        },
    )
    def get(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)

        try:
            profile = user.profile
        except Exception:
            profile = None

        addresses = {}

        if profile:
            addresses = {
                address.address_type: address
                for address in profile.addresses.all()
            }

        response_data = {
            "user": ManagementUserSummarySerializer(
                user,
                context={"request": request},
            ).data,
            "personal_info": (
                PersonalInfoSerializer(profile).data
                if profile
                else None
            ),
            "permanent_address": (
                AddressSerializer(
                    addresses.get(AddressType.PERMANENT)
                ).data
                if addresses.get(AddressType.PERMANENT)
                else None
            ),
            "temporary_address": (
                AddressSerializer(
                    addresses.get(AddressType.TEMPORARY)
                ).data
                if addresses.get(AddressType.TEMPORARY)
                else None
            ),
            "current_address": (
                AddressSerializer(
                    addresses.get(AddressType.CURRENT)
                ).data
                if addresses.get(AddressType.CURRENT)
                else None
            ),
            "guardians": (
                GuardianSerializer(
                    profile.guardians.all(),
                    many=True,
                ).data
                if profile
                else []
            ),
            "documents": (
                ProfileDocumentSerializer(
                    profile.documents.select_related("file").all(),
                    many=True,
                    context={"request": request},
                ).data
                if profile
                else []
            ),
            "health": None,
        }

        if profile:
            health = profile.student_other_info.first()

            if health:
                response_data["health"] = StudentHealthSerializer(
                    health
                ).data

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )


class ManagedUserIdentityUpdateView(APIView):
    permission_classes = [IsSchoolManagement]

    @schema(
        tag="03. School Management Profile",
        summary="Update user's first, middle and last name",
        request=ManagementUserIdentityUpdateSerializer,
        responses={
            200: ManagementUserSummarySerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="User not found."),
        },
    )
    def patch(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)

        serializer = ManagementUserIdentityUpdateSerializer(
            user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        output = ManagementUserSummarySerializer(
            user,
            context={"request": request},
        )

        return Response(
            {
                "updated": True,
                "message": "User name updated successfully.",
                "user": output.data,
            },
            status=status.HTTP_200_OK,
        )


class ManagedUserProfilePictureView(APIView):
    permission_classes = [IsSchoolManagement]

    @schema(
        tag="03. School Management Profile",
        summary="Update a user's profile picture",
        request=ManagementProfilePictureUpdateSerializer,
        responses={
            200: ManagementUserSummarySerializer,
            400: OpenApiResponse(description="Invalid image file."),
            404: OpenApiResponse(description="User not found."),
        },
    )
    def patch(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)

        serializer = ManagementProfilePictureUpdateSerializer(
            user,
            data=request.data,
            context={
                "request": request,
                "target_user": user,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        output = ManagementUserSummarySerializer(
            user,
            context={"request": request},
        )

        return Response(
            {
                "updated": True,
                "message": "Profile picture updated successfully.",
                "user": output.data,
            },
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Remove a user's profile picture",
        request=None,
        responses={
            200: OpenApiResponse(
                description="Profile picture removed."
            ),
            404: OpenApiResponse(description="User not found."),
        },
    )
    def delete(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)

        user.profile_picture_file = None
        user.save(update_fields=["profile_picture_file"])

        return Response(
            {
                "removed": True,
                "message": "Profile picture removed successfully.",
            },
            status=status.HTTP_200_OK,
        )


class ManagedUserPersonalInfoView(APIView):
    permission_classes = [IsSchoolManagement]

    @schema(
        tag="03. School Management Profile",
        summary="Get a user's personal information",
        responses={
            200: PersonalInfoSerializer,
            404: OpenApiResponse(description="User not found."),
        },
    )
    def get(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        return Response(
            PersonalInfoSerializer(profile).data,
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Update a user's personal information",
        request=PersonalInfoUpdateSerializer,
        responses={
            200: PersonalInfoSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="User not found."),
        },
    )
    def patch(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        serializer = PersonalInfoUpdateSerializer(
            profile,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "updated": True,
                "message": "Personal information updated successfully.",
                "personal_info": PersonalInfoSerializer(profile).data,
            },
            status=status.HTTP_200_OK,
        )


class ManagedUserAddressView(APIView):
    permission_classes = [IsSchoolManagement]

    allowed_address_types = {
        AddressType.PERMANENT,
        AddressType.TEMPORARY,
        AddressType.CURRENT,
    }

    def _validate_address_type(self, address_type):
        if address_type not in self.allowed_address_types:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({
                "address_type": "Invalid address type."
            })

    @schema(
        tag="03. School Management Profile",
        summary="Get a user's address by type",
        responses={
            200: AddressSerializer,
            404: OpenApiResponse(description="Address not found."),
        },
    )
    def get(self, request, user_id, address_type):
        self._validate_address_type(address_type)

        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        address = get_object_or_404(
            Address,
            profile=profile,
            address_type=address_type,
        )

        return Response(
            AddressSerializer(address).data,
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Create or update a user's address",
        request=AddressUpdateSerializer,
        responses={
            200: AddressSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="User not found."),
        },
    )
    def patch(self, request, user_id, address_type):
        self._validate_address_type(address_type)

        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        address, _ = Address.objects.get_or_create(
            profile=profile,
            address_type=address_type,
        )

        serializer = AddressUpdateSerializer(
            address,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "updated": True,
                "message": (
                    f"{address_type.capitalize()} address "
                    "updated successfully."
                ),
                "address": AddressSerializer(address).data,
            },
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Delete a user's address",
        request=None,
        responses={
            200: OpenApiResponse(description="Address deleted."),
            404: OpenApiResponse(description="Address not found."),
        },
    )
    def delete(self, request, user_id, address_type):
        self._validate_address_type(address_type)

        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        address = get_object_or_404(
            Address,
            profile=profile,
            address_type=address_type,
        )

        address.delete()

        return Response(
            {
                "deleted": True,
                "message": (
                    f"{address_type.capitalize()} address "
                    "deleted successfully."
                ),
            },
            status=status.HTTP_200_OK,
        )


class ManagedUserGuardianListCreateView(APIView):
    permission_classes = [IsSchoolManagement]

    @schema(
        tag="03. School Management Profile",
        summary="List a user's guardians",
        responses={200: GuardianSerializer(many=True)},
    )
    def get(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        guardians = profile.guardians.all().order_by(
            "-is_primary",
            "relation",
            "full_name",
        )

        return Response(
            GuardianSerializer(guardians, many=True).data,
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Create guardian information",
        request=GuardianCreateUpdateSerializer,
        responses={
            201: GuardianSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        serializer = GuardianCreateUpdateSerializer(
            data=request.data,
            context={"profile": profile},
        )
        serializer.is_valid(raise_exception=True)
        guardian = serializer.save()

        return Response(
            {
                "created": True,
                "message": "Guardian created successfully.",
                "guardian": GuardianSerializer(guardian).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ManagedUserGuardianDetailView(APIView):
    permission_classes = [IsSchoolManagement]

    def get_guardian(self, request, user_id, guardian_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        return get_object_or_404(
            Guardian,
            pk=guardian_id,
            profile=profile,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Get guardian information",
        responses={200: GuardianSerializer},
    )
    def get(self, request, user_id, guardian_id):
        guardian = self.get_guardian(
            request,
            user_id,
            guardian_id,
        )

        return Response(
            GuardianSerializer(guardian).data,
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Update guardian information",
        request=GuardianCreateUpdateSerializer,
        responses={200: GuardianSerializer},
    )
    def patch(self, request, user_id, guardian_id):
        guardian = self.get_guardian(
            request,
            user_id,
            guardian_id,
        )

        serializer = GuardianCreateUpdateSerializer(
            guardian,
            data=request.data,
            partial=True,
            context={"profile": guardian.profile},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "updated": True,
                "message": "Guardian updated successfully.",
                "guardian": GuardianSerializer(guardian).data,
            },
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Delete guardian information",
        request=None,
        responses={
            200: OpenApiResponse(description="Guardian deleted.")
        },
    )
    def delete(self, request, user_id, guardian_id):
        guardian = self.get_guardian(
            request,
            user_id,
            guardian_id,
        )

        guardian.delete()

        return Response(
            {
                "deleted": True,
                "message": "Guardian deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )


class ManagedUserDocumentListCreateView(APIView):
    permission_classes = [IsSchoolManagement]

    @schema(
        tag="03. School Management Profile",
        summary="List a user's documents",
        responses={200: ProfileDocumentSerializer(many=True)},
    )
    def get(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        documents = profile.documents.select_related("file").order_by(
            "-created_at"
        )

        return Response(
            ProfileDocumentSerializer(
                documents,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Add a document to a user's profile",
        request=ProfileDocumentCreateUpdateSerializer,
        responses={
            201: ProfileDocumentSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        serializer = ProfileDocumentCreateUpdateSerializer(
            data=request.data,
            context={
                "request": request,
                "profile": profile,
                "target_user": user,
            },
        )
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        return Response(
            {
                "created": True,
                "message": "Document added successfully.",
                "document": ProfileDocumentSerializer(
                    document,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ManagedUserDocumentDetailView(APIView):
    permission_classes = [IsSchoolManagement]

    def get_document(self, request, user_id, document_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        return get_object_or_404(
            ProfileDocument.objects.select_related("file"),
            pk=document_id,
            profile=profile,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Get a user document",
        responses={200: ProfileDocumentSerializer},
    )
    def get(self, request, user_id, document_id):
        document = self.get_document(
            request,
            user_id,
            document_id,
        )

        return Response(
            ProfileDocumentSerializer(
                document,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Update a user document",
        request=ProfileDocumentCreateUpdateSerializer,
        responses={200: ProfileDocumentSerializer},
    )
    def patch(self, request, user_id, document_id):
        document = self.get_document(
            request,
            user_id,
            document_id,
        )

        serializer = ProfileDocumentCreateUpdateSerializer(
            document,
            data=request.data,
            partial=True,
            context={
                "request": request,
                "profile": document.profile,
                "target_user": document.profile.user,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "updated": True,
                "message": "Document updated successfully.",
                "document": ProfileDocumentSerializer(
                    document,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Delete a user document",
        request=None,
        responses={
            200: OpenApiResponse(description="Document deleted.")
        },
    )
    def delete(self, request, user_id, document_id):
        document = self.get_document(
            request,
            user_id,
            document_id,
        )

        document.delete()

        return Response(
            {
                "deleted": True,
                "message": "Document deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )


class ManagedUserHealthView(APIView):
    permission_classes = [IsSchoolManagement]

    @schema(
        tag="03. School Management Profile",
        summary="Get a user's health information",
        responses={
            200: StudentHealthSerializer,
            404: OpenApiResponse(
                description="Health information not found."
            ),
        },
    )
    def get(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        health = get_object_or_404(
            StudentOtherInfo,
            profile=profile,
        )

        return Response(
            StudentHealthSerializer(health).data,
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Create or update a user's health information",
        request=StudentHealthUpdateSerializer,
        responses={
            200: StudentHealthSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def patch(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        health, _ = StudentOtherInfo.objects.get_or_create(
            profile=profile,
        )

        serializer = StudentHealthUpdateSerializer(
            health,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "updated": True,
                "message": "Health information updated successfully.",
                "health": StudentHealthSerializer(health).data,
            },
            status=status.HTTP_200_OK,
        )

    @schema(
        tag="03. School Management Profile",
        summary="Delete a user's health information",
        request=None,
        responses={
            200: OpenApiResponse(
                description="Health information deleted."
            )
        },
    )
    def delete(self, request, user_id):
        user = get_managed_user_or_404(request, user_id)
        profile = get_or_create_managed_profile(request, user)

        health = get_object_or_404(
            StudentOtherInfo,
            profile=profile,
        )

        health.delete()

        return Response(
            {
                "deleted": True,
                "message": "Health information deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )