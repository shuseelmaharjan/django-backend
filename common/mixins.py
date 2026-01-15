class ListFilterMetaMixin:
    ordering_param_name = "ordering"
    search_param_name = "search"

    def initial(self, request, *args, **kwargs):
        request._view = self
        super().initial(request, *args, **kwargs)

        self.filterable_fields = self._get_public_filters()
        self.sortable_fields = self._get_public_sorting()
        self.searchable_fields = self._get_searchable_fields()

    def _get_public_filters(self):
        return getattr(self, "public_filter_meta", {})

    def _get_public_sorting(self):
        return getattr(self, "public_sort_meta", {})

    def _get_searchable_fields(self):
        return list(getattr(self, "search_fields", []))
