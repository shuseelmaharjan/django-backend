from django.contrib import admin
from .models import FeeHead


@admin.register(FeeHead)
class FeeHeadAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "group", "is_active", "updated_at")
    list_filter = ("group", "is_active")
    search_fields = ("name", "code", "description")
    ordering = ("name",)
    prepopulated_fields = {"code": ("name",)}
