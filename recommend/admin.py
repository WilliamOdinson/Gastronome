import json
import logging
from types import SimpleNamespace

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.core.cache import cache
from django.db.models import Avg, Sum, Min
from django.utils.translation import gettext_lazy as _
from django_redis import get_redis_connection
from us import states

from business.models import Business
from user.models import User
from recommend.tasks import compute_user_recs, precache_recommendations
from recommend.services import get_state_hotlist, TOP_K
from Gastronome.utils.pagination import DummyPaginator

logger = logging.getLogger(__name__)


class BusinessState(Business):
    class Meta:
        proxy = True
        verbose_name = _("State hotlist cache")
        verbose_name_plural = _("State hotlist caches")


class PersonalRec(User):
    class Meta:
        proxy = True
        verbose_name = _("Personal rec cache")
        verbose_name_plural = _("Personal rec caches")


@admin.register(PersonalRec)
class PersonalRecAdmin(admin.ModelAdmin):
    list_display = ("email", "display_name", "review_count")
    search_fields = ("email", "display_name")
    ordering = ("-review_count",)
    actions = ("compute_personal_recs", "flush_personal_cache")

    def _state_for_user(self, user):
        """The recommendation model is currently trained only for PA."""
        return "PA"

    @admin.action(description=_("Compute personal recommendations (async)"))
    def compute_personal_recs(self, request, queryset):
        for user in queryset:
            compute_user_recs.delay(user.pk, state=self._state_for_user(user))
        self.message_user(request, _("%d user(s) queued.") % queryset.count())

    @admin.action(description=_("Delete personal-rec cache"))
    def flush_personal_cache(self, request, queryset):
        deleted = sum(cache.delete(f"rec:user:{user.pk}") for user in queryset)
        self.message_user(request, _("%d cache key(s) deleted.") % deleted)


class StateRow(SimpleNamespace):
    """
    Lightweight row object representing a single state's aggregates.
    Keeps BusinessState._meta so Django admin templates treat it like a model.
    """

    _meta = BusinessState._meta

    def serializable_value(self, field_name):
        return getattr(self, field_name, None)


class StateAggChangeList(ChangeList):
    """Aggregate the queryset so one row represents one state."""

    def get_results(self, request):
        super().get_results(request)

        pk_name = self.model._meta.pk.attname

        qs = (
            self.queryset.values("state")
            .annotate(
                _avg_rating=Avg("stars"),
                _total_reviews=Sum("review_count"),
                _pk=Min(pk_name),
            )
            .order_by("state")
        )

        rows = []
        for row in qs:
            obj = StateRow(
                pk=row["_pk"],
                id=row["_pk"],
                state=row["state"],
                _avg_rating=row["_avg_rating"],
                _total_reviews=row["_total_reviews"],
            )
            setattr(obj, pk_name, row["_pk"])
            rows.append(obj)

        self.result_list = rows
        self.result_count = self.full_result_count = len(rows)
        self.can_show_all = False
        self.multi_page = False
        self.page_num = 1
        self.paginator = DummyPaginator(len(rows), len(rows))


@admin.register(BusinessState)
class BusinessStateAdmin(admin.ModelAdmin):
    list_display = ("state_human", "avg_rating", "total_reviews")
    list_display_links = None
    list_filter = ()
    ordering = ("state",)
    actions = (
        "get_state_hotlist_action",
        "flush_state_hotlist_cache",
        "run_precache_recommendations",
        "update_precache_cache",
        "flush_precache_cache",
    )

    def get_changelist(self, request, **kwargs):
        return StateAggChangeList

    @admin.display(description=_("State"), ordering="state")
    def state_human(self, obj):
        code = getattr(obj, "state", "")
        st = states.lookup(code)
        return f"{st.name} ({code})" if st else code

    @admin.display(description=_("Average rating"))
    def avg_rating(self, obj):
        return round(getattr(obj, "_avg_rating", 0) or 0, 2)

    @admin.display(description=_("Review count"))
    def total_reviews(self, obj):
        return getattr(obj, "_total_reviews", 0) or 0

    def _states(self, queryset):
        """Return a set of uppercase state codes from the selected rows."""
        return {getattr(row, "state", "").upper() for row in queryset}

    @admin.action(description=_("Compute and cache hot list for selected states"))
    def get_state_hotlist_action(self, request, queryset):
        selected = self._states(queryset)
        for st in selected:
            biz_ids = get_state_hotlist(st, TOP_K)
            cache.set(f"rec:state:{st}", json.dumps(biz_ids), timeout=86_400)
        self.message_user(request, _("%d state hot list(s) refreshed.") % len(selected))

    @admin.action(description=_("Delete hot list cache for selected states"))
    def flush_state_hotlist_cache(self, request, queryset):
        selected = self._states(queryset)
        deleted = sum(cache.delete(f"rec:state:{st}") for st in selected)
        self.message_user(request, _("%d cache key(s) deleted.") % deleted)

    @admin.action(description=_("Pre-cache recommendations for PA (async)"))
    def run_precache_recommendations(self, request, queryset):
        if "PA" in self._states(queryset):
            precache_recommendations.delay()
            self.message_user(request, _("precache_recommendations queued."))
        else:
            self.message_user(
                request,
                _("Select at least one business in PA to run this."),
                level="warning",
            )

    @admin.action(description=_("Update PA precache cache (async)"))
    def update_precache_cache(self, request, queryset):
        self.run_precache_recommendations(request, queryset)

    @admin.action(description=_("Flush all PA precache cache"))
    def flush_precache_cache(self, request, queryset):
        if "PA" not in self._states(queryset):
            self.message_user(
                request,
                _("Select at least one business in PA to flush."),
                level="warning",
            )
            return

        cache.delete("rec:state:PA")
        redis = get_redis_connection("default")
        deleted = sum(redis.delete(key) for key in redis.scan_iter("rec:user:*"))
        self.message_user(
            request,
            _("Deleted PA precache cache and %d personal key(s).") % deleted,
        )


admin.site.site_header = "Gastronome Recommendation Admin"
admin.site.site_title = "Recommendation Admin"
admin.site.index_title = "Recommendation Dashboard"
