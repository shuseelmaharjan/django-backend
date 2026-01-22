from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)

from .services import load_locations
from .serializers import ProvinceSerializer, DistrictSerializer, MunicipalitySerializer


def _sorted_by_label(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda x: (x.get("label") or "").lower())


@extend_schema_view(
    get=extend_schema(
        tags=["Locations"],
        operation_id="list_provinces",
        summary="List provinces",
        description="Returns all provinces from the static locations.json file.",
        responses={
            200: ProvinceSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "Success",
                value=[
                    {"label": "Koshi Province", "value": "koshi_province"},
                    {"label": "Madhesh Province", "value": "madhesh_province"},
                ],
                response_only=True,
            )
        ],
        extensions={
            "x-code-samples": [
                {
                    "lang": "cURL",
                    "source": 'curl -X GET "http://localhost:8000/api/v1/provinces/" -H "accept: application/json"',
                }
            ]
        },
    )
)
class ProvinceListAPI(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ["get", "options", "head"]

    def get(self, request):
        data = load_locations()
        provinces = data.get("provinces", [])
        return Response(_sorted_by_label(provinces))


@extend_schema_view(
    get=extend_schema(
        tags=["Locations"],
        operation_id="list_districts",
        summary="List districts by province",
        description="Returns districts filtered by province (query param: `province`).",
        parameters=[
            OpenApiParameter(
                name="province",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Province value (e.g. `koshi_province`).",
                examples=[
                    OpenApiExample("Koshi", value="koshi_province"),
                    OpenApiExample("Madhesh", value="madhesh_province"),
                ],
            )
        ],
        responses={
            200: DistrictSerializer(many=True),
            400: OpenApiResponse(
                description="Missing required query param",
                response=None,
            ),
        },
        examples=[
            OpenApiExample(
                "Success",
                value=[
                    {"label": "Morang", "value": "morang", "province": "koshi_province"},
                    {"label": "Sunsari", "value": "sunsari", "province": "koshi_province"},
                ],
                response_only=True,
            ),
            OpenApiExample(
                "Bad Request",
                value={"detail": "Query param 'province' is required. Example: ?province=koshi_province"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
        extensions={
            "x-code-samples": [
                {
                    "lang": "cURL",
                    "source": 'curl -X GET "http://localhost:8000/api/v1/districts/?province=koshi_province" -H "accept: application/json"',
                }
            ]
        },
    )
)
class DistrictListAPI(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ["get", "options", "head"]

    def get(self, request):
        province_value = request.query_params.get("province")
        if not province_value:
            return Response(
                {"detail": "Query param 'province' is required. Example: ?province=koshi_province"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = load_locations()
        districts = [
            d for d in data.get("districts", [])
            if d.get("province") == province_value
        ]
        return Response(_sorted_by_label(districts))


@extend_schema_view(
    get=extend_schema(
        tags=["Locations"],
        operation_id="list_municipalities",
        summary="List municipalities by district",
        description="Returns municipalities filtered by district (query param: `district`).",
        parameters=[
            OpenApiParameter(
                name="district",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="District value (e.g. `morang`).",
                examples=[
                    OpenApiExample("Morang", value="morang"),
                    OpenApiExample("Dhanusha", value="dhanusha"),
                ],
            )
        ],
        responses={
            200: MunicipalitySerializer(many=True),
            400: OpenApiResponse(description="Missing required query param", response=None),
        },
        examples=[
            OpenApiExample(
                "Success",
                value=[
                    {
                        "label": "Biratnagar Municipality",
                        "value": "biratnagar_municipality",
                        "district": "morang",
                    }
                ],
                response_only=True,
            ),
            OpenApiExample(
                "Bad Request",
                value={"detail": "Query param 'district' is required. Example: ?district=morang"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
        extensions={
            "x-code-samples": [
                {
                    "lang": "cURL",
                    "source": 'curl -X GET "http://localhost:8000/api/v1/municipalities/?district=morang" -H "accept: application/json"',
                }
            ]
        },
    )
)
class MunicipalityListAPI(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ["get", "options", "head"]

    def get(self, request):
        district_value = request.query_params.get("district")
        if not district_value:
            return Response(
                {"detail": "Query param 'district' is required. Example: ?district=morang"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = load_locations()
        municipalities = [
            m for m in data.get("municipalities", [])
            if m.get("district") == district_value
        ]
        return Response(_sorted_by_label(municipalities))
