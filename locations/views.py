import json
from pathlib import Path
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from functools import lru_cache

from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers


@lru_cache(maxsize=1)
def load_json_data():
    """Load all location data once per process and cache it."""
    data_dir = Path(getattr(settings, "DATA_DIR", Path(settings.BASE_DIR) / "locations" / "json"))

    try:
        with open(data_dir / "provinces.json", "r", encoding="utf-8") as f:
            provinces = json.load(f)
        with open(data_dir / "districts.json", "r", encoding="utf-8") as f:
            districts = json.load(f)
        with open(data_dir / "local_levels.json", "r", encoding="utf-8") as f:
            local_levels = json.load(f)
        with open(data_dir / "local_level_type.json", "r", encoding="utf-8") as f:
            local_level_types = json.load(f)

        return {
            "provinces": provinces,
            "districts": districts,
            "municipalities": local_levels,
            "local_level_types": local_level_types,
        }
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Missing location data file: {str(e)}")


# Serializers for individual endpoints (schema-only)
ProvinceSerializer = inline_serializer(
    name="ProvinceItem",
    fields={
        "province_id": serializers.IntegerField(),
        "name": serializers.CharField(),
        "nepali_name": serializers.CharField(),
    },
)

DistrictSerializer = inline_serializer(
    name="DistrictItem",
    fields={
        "district_id": serializers.IntegerField(),
        "name": serializers.CharField(),
        "nepali_name": serializers.CharField(),
        "province_id": serializers.IntegerField(),
    },
)

MunicipalitySerializer = inline_serializer(
    name="MunicipalityItem",
    fields={
        "municipality_id": serializers.IntegerField(),
        "name": serializers.CharField(),
        "nepali_name": serializers.CharField(),
        "district_id": serializers.IntegerField(),
        "local_level_type_id": serializers.IntegerField(),
        "label": serializers.CharField(),
        "nepali_label": serializers.CharField(),
        "local_level_type": inline_serializer(
            name="MunicipalityLocalLevelType",
            fields={
                "local_level_type_id": serializers.IntegerField(),
                "name": serializers.CharField(),
                "nepali_name": serializers.CharField(),
            },
        ),
    },
)


class ProvinceListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public Locations API"],
        summary="List all provinces",
        responses={200: serializers.ListSerializer(child=ProvinceSerializer)},
        description="Returns a list of all provinces in Nepal.",
    )
    def get(self, request):
        try:
            data = load_json_data()
            provinces = sorted(data["provinces"], key=lambda x: x.get("name", ""))
            return Response(provinces, status=status.HTTP_200_OK)
        except FileNotFoundError as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DistrictListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public Locations API"],
        summary="List districts",
        parameters=[
            OpenApiParameter(
                name="province_id",
                type=int,
                location="query",
                required=False,
                description="Filter districts by province ID",
            ),
        ],
        responses={200: serializers.ListSerializer(child=DistrictSerializer)},
        description="Returns a list of districts. Optionally filter by province_id.",
    )
    def get(self, request):
        try:
            data = load_json_data()
            districts = data["districts"]

            province_id = request.query_params.get("province_id")
            if province_id:
                try:
                    province_id = int(province_id)
                except ValueError:
                    return Response({"error": "province_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
                districts = [d for d in districts if d.get("province_id") == province_id]

            districts = sorted(districts, key=lambda x: x.get("name", ""))
            return Response(districts, status=status.HTTP_200_OK)
        except FileNotFoundError as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MunicipalityListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public Locations API"],
        summary="List municipalities/local governments",
        parameters=[
            OpenApiParameter(
                name="district_id",
                type=int,
                location="query",
                required=False,
                description="Filter municipalities by district ID",
            ),
            OpenApiParameter(
                name="province_id",
                type=int,
                location="query",
                required=False,
                description="Filter municipalities by province ID",
            ),
        ],
        responses={200: serializers.ListSerializer(child=MunicipalitySerializer)},
        description="Returns a list of municipalities. Optionally filter by district_id or province_id.",
    )
    def get(self, request):
        try:
            data = load_json_data()
            municipalities = list(data["municipalities"])
            type_by_id = {t["local_level_type_id"]: t for t in data["local_level_types"]}

            district_id = request.query_params.get("district_id")
            province_id = request.query_params.get("province_id")

            if district_id:
                try:
                    district_id = int(district_id)
                except ValueError:
                    return Response({"error": "district_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
                municipalities = [m for m in municipalities if m.get("district_id") == district_id]

            if province_id:
                try:
                    province_id = int(province_id)
                except ValueError:
                    return Response({"error": "province_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

                valid_district_ids = {
                    d["district_id"] for d in data["districts"] if d.get("province_id") == province_id
                }
                municipalities = [m for m in municipalities if m.get("district_id") in valid_district_ids]

            # Enrich response with label + local_level_type object
            enriched = []
            for m in municipalities:
                t = type_by_id.get(m.get("local_level_type_id"))
                enriched.append({
                    **m,
                    "local_level_type": (
                        {
                            "local_level_type_id": t["local_level_type_id"],
                            "name": t["name"],
                            "nepali_name": t["nepali_name"],
                        } if t else None
                    ),
                    "label": f'{m.get("name", "")} {t["name"]}' if t else m.get("name", ""),
                    "nepali_label": f'{m.get("nepali_name", "")} {t["nepali_name"]}' if t else m.get("nepali_name", ""),
                })

            enriched = sorted(enriched, key=lambda x: x.get("name", ""))
            return Response(enriched, status=status.HTTP_200_OK)

        except FileNotFoundError as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def build_province_tree():
    data = load_json_data()

    provinces = list(data["provinces"])
    districts = list(data["districts"])
    local_levels = list(data["municipalities"])
    local_level_types = list(data["local_level_types"])

    type_by_id = {t["local_level_type_id"]: t for t in local_level_types}

    districts_by_province = {}
    for d in districts:
        districts_by_province.setdefault(d["province_id"], []).append(d)

    locals_by_district = {}
    for ll in local_levels:
        locals_by_district.setdefault(ll["district_id"], []).append(ll)

    provinces.sort(key=lambda x: (x.get("name", ""), x.get("province_id", 0)))
    for pid in districts_by_province:
        districts_by_province[pid].sort(key=lambda x: (x.get("name", ""), x.get("district_id", 0)))
    for did in locals_by_district:
        locals_by_district[did].sort(key=lambda x: (x.get("name", ""), x.get("municipality_id", 0)))

    result = []
    for p in provinces:
        province_item = {
            "province_id": p["province_id"],
            "name": p["name"],
            "nepali_name": p["nepali_name"],
            "districts": [],
        }

        for d in districts_by_province.get(p["province_id"], []):
            district_item = {
                "district_id": d["district_id"],
                "name": d["name"],
                "nepali_name": d["nepali_name"],
                "local_governments": [],
            }

            for ll in locals_by_district.get(d["district_id"], []):
                t = type_by_id.get(ll.get("local_level_type_id"))
                local_item = {
                    "municipality_id": ll["municipality_id"],
                    "name": ll["name"],
                    "nepali_name": ll["nepali_name"],
                    "local_level_type": (
                        {
                            "local_level_type_id": t["local_level_type_id"],
                            "name": t["name"],
                            "nepali_name": t["nepali_name"],
                        }
                        if t
                        else None
                    ),
                    "label": f'{ll["name"]} {t["name"]}' if t else ll["name"],
                    "nepali_label": f'{ll["nepali_name"]} {t["nepali_name"]}' if t else ll["nepali_name"],
                }
                district_item["local_governments"].append(local_item)

            province_item["districts"].append(district_item)

        result.append(province_item)

    return result


# --- Swagger schema (explicit response shape) ---
LocalLevelTypeSchema = inline_serializer(
    name="LocalLevelType",
    fields={
        "local_level_type_id": serializers.IntegerField(),
        "name": serializers.CharField(),
        "nepali_name": serializers.CharField(),
    },
)

LocalGovernmentSchema = inline_serializer(
    name="LocalGovernment",
    fields={
        "municipality_id": serializers.IntegerField(),
        "name": serializers.CharField(),
        "nepali_name": serializers.CharField(),
        "label": serializers.CharField(),
        "nepali_label": serializers.CharField(),
        "local_level_type": LocalLevelTypeSchema,  # may be null in response
    },
)

DistrictSchema = inline_serializer(
    name="DistrictTree",
    fields={
        "district_id": serializers.IntegerField(),
        "name": serializers.CharField(),
        "nepali_name": serializers.CharField(),
        # FIX: ListField child must be a Field, so use ListSerializer for schema
        "local_governments": serializers.ListSerializer(child=LocalGovernmentSchema),
    },
)

ProvinceSchema = inline_serializer(
    name="ProvinceTree",
    fields={
        "province_id": serializers.IntegerField(),
        "name": serializers.CharField(),
        "nepali_name": serializers.CharField(),
        "districts": serializers.ListSerializer(child=DistrictSchema),
    },
)


class ProvinceTreeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public Locations API"],
        summary="Get province → district → local government tree",
        responses={200: serializers.ListSerializer(child=ProvinceSchema)},
        description=(
            "Returns provinces with associated districts and local governments.\n\n"
            "Local government labels:\n"
            "- label = name + local_level_type.name\n"
            "- nepali_label = nepali_name + local_level_type.nepali_name"
        ),
    )
    def get(self, request):
        try:
            tree = build_province_tree()
            return Response(tree, status=status.HTTP_200_OK)
        except FileNotFoundError as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except json.JSONDecodeError as e:
            return Response({"error": f"Invalid JSON: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
