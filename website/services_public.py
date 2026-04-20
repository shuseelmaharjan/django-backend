from django.db.models import Prefetch

from schools.serializers import PublicSchoolSerializer
from .models import Navigation, Courses, Events, Ads, FooterGroup, FooterLink
from .serializers_public import (
    NavigationCourseTreeSerializer,
    EventsSerializer,
    AdsSerializer,
    FooterGroupSerializer,
)


def build_public_metadata(school):
    navigations = Navigation.objects.filter(
        school=school
    ).prefetch_related(
        Prefetch(
            "courses",
            queryset=Courses.objects.order_by("sort_order", "created_at")
        )
    ).order_by("sort_order", "created_at")

    ads = Ads.objects.filter(
        school=school
    ).select_related(
        "image"
    ).order_by("?")[:4]

    footer_groups = FooterGroup.objects.filter(
        school=school
    ).prefetch_related(
        Prefetch(
            "links",
            queryset=FooterLink.objects.order_by("created_at")
        )
    ).order_by("created_at")

    # NOTE:
    # Events model currently has no school FK, so this is global for now.
    events = Events.objects.all().order_by("-event_date", "-created_at")

    return {
        "school": PublicSchoolSerializer(school).data,
        "navigations": NavigationCourseTreeSerializer(navigations, many=True).data,
        "events": EventsSerializer(events, many=True).data,
        "ads": AdsSerializer(ads, many=True).data,
        "footer_groups": FooterGroupSerializer(footer_groups, many=True).data,
    }