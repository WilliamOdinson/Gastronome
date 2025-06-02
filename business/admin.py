import csv
import datetime
from typing import Any, Dict

from django.contrib import admin
from django.core.cache import cache
from django.db.models import F
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from business.models import (
    Business,
    Category,
    CheckIn,
    Hour,
    Photo,
)
from business.tasks import BATCH_SIZE, refresh_open_batch


def export_csv_action(description: str):
    """Return a generic "export selected as CSV" ModelAdmin action."""

    def export(modeladmin, request, queryset):
        opts = modeladmin.model._meta
        fields = [f.name for f in opts.fields]
        resp = HttpResponse(content_type="text/csv")
        resp[
            "Content-Disposition"
        ] = f'attachment; filename="{opts.model_name}_{datetime.date.today()}.csv"'
        writer = csv.writer(resp)
        writer.writerow(fields)
        for obj in queryset:
            writer.writerow([getattr(obj, f) for f in fields])
        return resp

    export.short_description = description
    return export


class HourInline(admin.TabularInline):
    model = Hour
    extra = 0
    list_select_related = ("business",)
    readonly_fields = ("business", "day")
    fields = ("business", "day", "open_time", "close_time")


class PhotoInline(admin.TabularInline):
    model = Photo
    fields = ("photo_id", "business", "label", "caption", "thumb")
    readonly_fields = ("photo_id", "business", "thumb")

    @staticmethod
    def thumb(obj):
        return format_html('<img src="{}" width="100" />', obj.image_url)

    thumb.short_description = _("Preview")


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "state",
        "city",
        "stars",
        "review_count",
        "is_open",
        "timezone",
    )
    list_filter = ("state", "is_open")
    search_fields = ("name", "address", "city", "business_id")
    readonly_fields = (
        "business_id",
        "city",
        "state",
        "is_open",
        "timezone",
    )
    fields = (
        "business_id",
        "name",
        "address",
        "city",
        "state",
        "postal_code",
        "latitude",
        "longitude",
        "stars",
        "review_count",
        "is_open",
        "timezone",
        "categories",
        "attributes",
    )
    inlines = (HourInline, PhotoInline)
    ordering = ("-review_count",)
    raw_id_fields: tuple[str, ...] = ()
    autocomplete_fields = ("categories",)
    actions = (
        export_csv_action(_("Export selected businesses to CSV")),
        "recompute_open_now",
        "toggle_open_flag",
        "queue_open_refresh",
        "flush_detail_cache",
    )

    @admin.action(description=_("Re-evaluate opening status immediately"))
    def recompute_open_now(self, request, queryset):
        changed = 0
        for biz in queryset:
            new_state = biz.calculate_open_status()
            if new_state != biz.is_open:
                biz.is_open = new_state
                biz.save(update_fields=["is_open"])
                changed += 1
        self.message_user(request, _("%d business(es) updated.") % changed)

    @admin.action(description=_("Toggle \"is_open\" flag"))
    def toggle_open_flag(self, request, queryset):
        updated = queryset.update(is_open=~F("is_open"))
        self.message_user(request, _("%d business(es) toggled.") % updated)

    @admin.action(description=_("Queue Celery open-status refresh"))
    def queue_open_refresh(self, request, queryset):
        ids = list(queryset.values_list("business_id", flat=True))
        for i in range(0, len(ids), BATCH_SIZE):
            refresh_open_batch.delay(ids[i: i + BATCH_SIZE])
        self.message_user(
            request, _("Queued refresh for %d business(es).") % len(ids)
        )

    @admin.action(description=_("Delete cached detail pages"))
    def flush_detail_cache(self, request, queryset):
        deleted = sum(
            cache.delete(f"biz_detail:{biz.business_id}") for biz in queryset
        )
        self.message_user(request, _("%d cache key(s) deleted.") % deleted)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)

    def has_module_permission(self, request):
        return False


@admin.register(Hour)
class HourAdmin(admin.ModelAdmin):
    list_display = ("business", "day", "open_time", "close_time")
    list_filter = ("day",)
    search_fields = ("business__name",)
    list_select_related = ("business",)
    raw_id_fields = ("business",)
    readonly_fields = ("business", "day")
    fields = ("business", "day", "open_time", "close_time")


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("photo_id", "business", "label", "caption", "preview")
    list_filter = ("label",)
    search_fields = ("photo_id", "business__name", "label")
    readonly_fields = ("photo_id", "business", "preview")
    fields = ("photo_id", "business", "label", "caption", "preview")
    list_select_related = ("business",)
    raw_id_fields = ("business",)

    @staticmethod
    def preview(obj):
        return format_html('<img src="{}" width="120" />', obj.image_url)

    preview.short_description = _("Preview")


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("business", "checkin_time")
    list_filter = ("checkin_time",)
    raw_id_fields = ("business",)
    list_select_related = ("business",)
    search_fields = ("business__name",)
    readonly_fields = ("business",)
    fields = ("business", "checkin_time")


admin.site.site_header = "Gastronome Business Admin"
admin.site.site_title = "Business Admin"
admin.site.index_title = "Business Dashboard"
