from django.db.models import Prefetch

from schools.serializers import PublicSchoolSerializer
from .models import Navigation, Courses, Events, Ads, FooterGroup, FooterLink
from .serializers_public import (
    NavigationCourseTreeSerializer,
    EventsSerializer,
    AdsSerializer,
    FooterGroupSerializer,
)


def build_public_metadata(school, request=None):
    context = {"request": request} if request else {}

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

    events = Events.objects.all().order_by("-event_date", "-created_at")

    return {
        "school": PublicSchoolSerializer(
            school,
            context=context
        ).data,
        "navigations": NavigationCourseTreeSerializer(
            navigations,
            many=True,
            context=context
        ).data,
        "events": EventsSerializer(
            events,
            many=True,
            context=context
        ).data,
        "ads": AdsSerializer(
            ads,
            many=True,
            context=context
        ).data,
        "footer_groups": FooterGroupSerializer(
            footer_groups,
            many=True,
            context=context
        ).data,
    }