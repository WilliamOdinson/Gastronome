import csv
import datetime
from math import ceil
from typing import Any, Dict, List

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.core.paginator import Paginator
from django.db.models import Case, F, When
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from Gastronome.opensearch import get_opensearch_client
from Gastronome.utils.pagination import DummyPaginator
from review.models import Review, Tip
from review.tasks import compute_auto_score

op = get_opensearch_client()
ALLOWED_TIP_SORT = {"date", "compliment_count"}
ALLOWED_REVIEW_SORT = {"date", "stars", "useful", "funny", "cool", "auto_score"}


def export_as_csv_action(description: str):
    """
    Returns a ModelAdmin 'action' that exports selected rows as CSV.
    """

    def export(modeladmin, request, queryset):
        meta = queryset.model._meta
        fields = [f.name for f in meta.fields]
        resp = HttpResponse(content_type="text/csv")
        resp[
            "Content-Disposition"
        ] = f'attachment; filename="{meta.model_name}_{datetime.date.today()}.csv"'
        writer = csv.writer(resp)
        writer.writerow(fields)
        for obj in queryset:
            writer.writerow([getattr(obj, f) for f in fields])
        return resp

    export.short_description = description
    return export


class OSReviewChangeList(ChangeList):
    """
    All searching, filtering, sorting and pagination are executed in OpenSearch.
    Only the IDs for the current page are hydrated back from the database in
    their original order, keeping admin templates unchanged.
    """

    def _build_os_query(self, request) -> Dict[str, Any]:
        """
        Build the OpenSearch DSL 'query' section from search box and filters.
        """
        query: Dict[str, Any] = {"bool": {"must": [], "filter": []}}

        # Full-text search box
        if self.query:
            query["bool"]["must"].append(
                {
                    "multi_match": {
                        "query": self.query,
                        "type": "bool_prefix",
                        "fields": [
                            "text",
                            "text.ng",
                            "user_name",
                            "user_name.ng",
                            "business_name",
                            "business_name.ng",
                        ],
                    }
                }
            )

        # Star rating exact filter
        stars_val: str | None = request.GET.get("stars__exact")
        if stars_val:
            query["bool"]["filter"].append({"term": {"stars": int(stars_val)}})

        # Auto-score bucket filter (driven by AutoScoreFilter below)
        auto_bucket = request.GET.get("auto_score")
        if auto_bucket == "null":
            query["bool"]["must_not"] = [{"exists": {"field": "auto_score"}}]
        elif auto_bucket == "low":
            query["bool"]["filter"].append({"range": {"auto_score": {"lt": 2.0}}})
        elif auto_bucket == "mid":
            query["bool"]["filter"].append(
                {"range": {"auto_score": {"gte": 2.0, "lte": 3.5}}}
            )
        elif auto_bucket == "high":
            query["bool"]["filter"].append({"range": {"auto_score": {"gt": 3.5}}})

        return query

    def get_results(self, request):
        super().get_results(request)
        # Build DSL query
        dsl_query: Dict[str, Any] = self._build_os_query(request)

        # Respect column-header clicks by using the ChangeList method that
        # already interprets the 'o' GET parameter.
        ordering_tuple: tuple[str, ...] = self.get_ordering(
            request,
            self.root_queryset,
        ) or ("-date",)

        # Translate Django ordering into OpenSearch 'sort'
        sort_clause: List[Dict[str, Any]] = []
        for ordering in ordering_tuple:
            fld = ordering.lstrip("-")
            if fld not in ALLOWED_REVIEW_SORT:
                # Ignore fields that are computed or absent in the index
                continue
            direction = "desc" if ordering.startswith("-") else "asc"
            sort_clause.append({fld: {"order": direction}})
        if not sort_clause:
            sort_clause = [{"date": {"order": "desc"}}]

        # Pagination math (0-based for OpenSearch)
        per_page: int = self.list_per_page
        page_num_0: int = int(request.GET.get("p", "0"))
        start: int = page_num_0 * per_page

        # Hit OpenSearch
        res: Dict[str, Any] = op.search(
            index=settings.OPENSEARCH["REVIEW_INDEX"],
            body={
                "query": dsl_query,
                "sort": sort_clause,
                "from": start,
                "size": per_page,
            },
            _source=False,
            track_total_hits=True,
        )

        # Total hits extraction
        total_obj = res["hits"].get("total", 0)
        total_hits: int = total_obj["value"] if isinstance(total_obj, dict) else int(total_obj)

        # Inform Django-admin about the result set size
        self.result_count = self.full_result_count = total_hits
        self.can_show_all = False  # SQL 'show all' would be meaningless
        self.multi_page = total_hits > per_page

        # Hydrate ORM objects for the current page, preserving OS order
        ids: List[str] = [h["_id"] for h in res["hits"]["hits"]]
        if not ids:
            self.result_list = Review.objects.none()
        else:
            preserve = Case(*[When(pk=pk, then=i) for i, pk in enumerate(ids)])
            self.result_list = (
                Review.objects.filter(pk__in=ids)
                .select_related("user", "business")
                .order_by(preserve)
            )

        self.page_num = page_num_0 + 1  # Django is 1-based
        self.paginator = DummyPaginator(total_hits, per_page)


class AutoScoreFilter(admin.SimpleListFilter):
    title = _("auto-score")
    parameter_name = "auto_score"

    def lookups(self, request, model_admin):
        return (
            ("null", _("Missing")),
            ("low", _("< 2.0")),
            ("mid", _("2.0 - 3.5")),
            ("high", _("> 3.5")),
        )

    def queryset(self, *args):
        # All filtering is performed in OpenSearch
        return None


class ReviewAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_max_show_all = 500
    show_full_result_count = False

    raw_id_fields = ("user", "business")

    list_display = (
        "short_text",
        "stars",
        "author",
        "business_obj",
        "date",
        "useful",
        "funny",
        "cool",
        "auto_score",
    )
    list_display_links = ("short_text",)
    search_fields = ("text", "user__display_name", "business__name")
    list_filter = ("stars", AutoScoreFilter)
    ordering = ("-date",)
    fields = (
        "review_id",
        "user",
        "business",
        "stars",
        "date",
        "text",
        "useful",
        "funny",
        "cool",
        "auto_score",
    )
    readonly_fields = (
        "review_id",
        "user",
        "business",
        "stars",
        "date",
        "text",
    )
    actions = (
        export_as_csv_action(_("Export selected reviews to CSV")),
        "recompute_auto_score",
        "add_useful",
        "add_funny",
        "add_cool",
    )

    # Use the custom ChangeList
    def get_changelist(self, request, **kwargs):
        return OSReviewChangeList

    @admin.display(description=_("Author"))
    def author(self, obj):
        url = reverse("admin:user_user_change", args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.display_name or obj.user.email)

    @admin.display(description=_("Business"))
    def business_obj(self, obj):
        url = reverse("admin:business_business_change", args=[obj.business.pk])
        return format_html('<a href="{}">{}</a>', url, obj.business.name)

    @admin.display(description=_("Text"))
    def short_text(self, obj):
        return obj.text if len(obj.text) <= 60 else f"{obj.text[:60]}..."

    @admin.action(description="Recompute auto-score")
    def recompute_auto_score(self, request, queryset):
        for rid in queryset.values_list("pk", flat=True):
            compute_auto_score.delay(rid)
        self.message_user(request, _("Auto-score recomputation queued."))

    def _inc(self, request, queryset, field):
        updated = queryset.update(**{field: F(field) + 1})
        self.message_user(request, _("%d review(s) updated.") % updated)

    @admin.action(description="+1 Useful to selected reviews")
    def add_useful(self, r, q):
        self._inc(r, q, "useful")

    @admin.action(description="+1 Funny to selected reviews")
    def add_funny(self, r, q):
        self._inc(r, q, "funny")

    @admin.action(description="+1 Cool to selected reviews")
    def add_cool(self, r, q):
        self._inc(r, q, "cool")


class OSTipChangeList(ChangeList):
    """
    Custom ChangeList for Tip: all searching, filtering, sorting, and pagination
    is performed in OpenSearch. Only the objects for the current page are hydrated
    via Django ORM in the exact original order.
    """

    def _build_os_query(self, request) -> Dict[str, Any]:
        query: Dict[str, Any] = {"bool": {"must": [], "filter": []}}

        # Full-text search from the admin search box
        if self.query:
            query["bool"]["must"].append(
                {
                    "multi_match": {
                        "query": self.query,
                        "type": "bool_prefix",
                        "fields": [
                            "text",
                            "text.ng",
                            "user_name",
                            "user_name.ng",
                            "business_name",
                            "business_name.ng",
                        ],
                    }
                }
            )

        # Year-based date filter (Django admin uses `date__year`)
        year = request.GET.get("date__year")
        if year and year.isdigit():
            y = int(year)
            query["bool"]["filter"].append(
                {
                    "range": {
                        "date": {
                            "gte": f"{y}-01-01",
                            "lt": f"{y + 1}-01-01",
                        }
                    }
                }
            )

        return query

    def get_results(self, request):
        super().get_results(request)
        dsl_query = self._build_os_query(request)

        # Translate ?o= sorting param into OpenSearch sort
        ordering_tuple = self.get_ordering(request, self.root_queryset) or ("-date",)

        sort_clause: List[Dict[str, Any]] = []
        for ordering in ordering_tuple:
            fld = ordering.lstrip("-")
            if fld not in ALLOWED_TIP_SORT:
                continue
            direction = "desc" if ordering.startswith("-") else "asc"
            sort_clause.append({fld: {"order": direction}})
        if not sort_clause:
            sort_clause = [{"date": {"order": "desc"}}]

        # Pagination: zero-based in OpenSearch
        per_page: int = self.list_per_page
        page_num_0: int = int(request.GET.get("p", "0"))
        start: int = page_num_0 * per_page

        res: Dict[str, Any] = op.search(
            index=settings.OPENSEARCH["TIP_INDEX"],
            body={
                "query": dsl_query,
                "sort": sort_clause,
                "from": start,
                "size": per_page,
            },
            _source=False,
            track_total_hits=True,
        )

        total_obj = res["hits"].get("total", 0)
        total_hits: int = total_obj["value"] if isinstance(total_obj, dict) else int(total_obj)

        self.result_count = self.full_result_count = total_hits
        self.can_show_all = False
        self.multi_page = total_hits > per_page

        ids: List[str] = [h["_id"] for h in res["hits"]["hits"]]
        if not ids:
            self.result_list = Tip.objects.none()
        else:
            preserve = Case(*[When(pk=pk, then=i) for i, pk in enumerate(ids)])
            self.result_list = (
                Tip.objects.filter(pk__in=ids)
                .select_related("user", "business")
                .order_by(preserve)
            )

        self.page_num = page_num_0 + 1
        self.paginator = DummyPaginator(total_hits, per_page)


class TipAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_max_show_all = 500
    show_full_result_count = False

    raw_id_fields = ("user", "business")

    list_display = (
        "short_text",
        "author",
        "business_obj",
        "date",
        "compliment_count",
    )
    search_fields = ("text", "user__display_name", "business__name")
    list_filter = ()  # Filter handled by OpenSearch DSL
    ordering = ("-date",)
    fields = (
        "user",
        "business",
        "text",
        "date",
        "compliment_count",
    )
    readonly_fields = (
        "user",
        "business",
        "text",
        "date",
    )

    actions = (
        export_as_csv_action(_("Export selected tips to CSV")),
        "add_compliment",
    )

    def get_changelist(self, request, **kwargs):
        return OSTipChangeList

    @admin.display(description=_("Text"))
    def short_text(self, obj):
        return obj.text if len(obj.text) <= 60 else f"{obj.text[:60]}..."

    @admin.display(description=_("Author"))
    def author(self, obj):
        url = reverse("admin:user_user_change", args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.display_name or obj.user.email)

    @admin.display(description=_("Business"))
    def business_obj(self, obj):
        url = reverse("admin:business_business_change", args=[obj.business.pk])
        return format_html('<a href="{}">{}</a>', url, obj.business.name)

    @admin.action(description="+1 Compliment to selected tips")
    def add_compliment(self, request, queryset):
        updated = queryset.update(compliment_count=F("compliment_count") + 1)
        self.message_user(request, _("%d tip(s) complimented.") % updated)


admin.site.register(Review, ReviewAdmin)
admin.site.register(Tip, TipAdmin)

admin.site.site_header = "Gastronome Administration"
admin.site.site_title = "Gastronome Admin"
admin.site.index_title = "Project Dashboard"
