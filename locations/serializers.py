from rest_framework import serializers


class ProvinceSerializer(serializers.Serializer):
    label = serializers.CharField()
    value = serializers.CharField()


class DistrictSerializer(serializers.Serializer):
    label = serializers.CharField()
    value = serializers.CharField()
    province = serializers.CharField()


class MunicipalitySerializer(serializers.Serializer):
    label = serializers.CharField()
    value = serializers.CharField()
    district = serializers.CharField()
