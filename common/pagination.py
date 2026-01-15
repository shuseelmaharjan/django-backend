# common/pagination.py
from collections import OrderedDict
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class MetaPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    # static options for frontend dropdown
    page_size_options = [10, 20, 50, 100]

    def get_page_size(self, request):
        """
        Enforce only allowed page sizes (static dropdown values).
        If client passes something else, fallback to default `page_size`.
        """
        raw = request.query_params.get(self.page_size_query_param)
        if not raw:
            return self.page_size
        try:
            val = int(raw)
        except ValueError:
            return self.page_size

        if val in self.page_size_options:
            return min(val, self.max_page_size)
        return self.page_size

    def get_paginated_response(self, data):
        # add serial number globally (based on pagination offset)
        start_index = (self.page.number - 1) * self.get_page_size(self.request)
        for i, item in enumerate(data, start=1):
            if isinstance(item, dict):
                item["serial"] = start_index + i

        view = getattr(self.request, "_view", None)

        meta = {
            "page": self.page.number,
            "page_size": self.get_page_size(self.request),

            # expose dropdown info
            "page_size_param": self.page_size_query_param,
            "page_size_options": self.page_size_options,
            "max_page_size": self.max_page_size,

            "filterable": getattr(view, "filterable_fields", {}),
            "sortable": getattr(view, "sortable_fields", {}),
            "searchable": getattr(view, "searchable_fields", []),
            "ordering_param": getattr(view, "ordering_param_name", "ordering"),
            "search_param": getattr(view, "search_param_name", "search"),
        }

        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("meta", meta),
                    ("results", data),
                ]
            )
        )
