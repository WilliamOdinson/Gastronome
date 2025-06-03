import csv
import datetime
from typing import Any, Dict, List

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.cache import cache
from django.db.models import Case, When
from django.http import HttpResponse
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from Gastronome.opensearch import get_opensearch_client
from Gastronome.utils.pagination import DummyPaginator
from user.models import User
from user.tasks import send_verification_email

op = get_opensearch_client(timeout=15)

ALLOWED_USER_SORT = {
    "email",
    "display_name",
    "review_count",
    "fans",
    "average_stars",
}


class UserCreationForm(forms.ModelForm):
    """Form used in the Django admin to create a new user."""

    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "display_name")

    def clean_password2(self) -> str:
        """Verify that the two password entries match."""
        if self.cleaned_data.get("password1") != self.cleaned_data.get("password2"):
            raise forms.ValidationError(_("Passwords don't match."))
        return self.cleaned_data["password2"]

    def save(self, commit: bool = True) -> User:
        """Save the new user with a properly hashed password."""
        user: User = super().save(commit=False)
        user.username = user.email
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """Form used in the Django admin to update an existing user."""

    # Read-only field shows the hashed password; it should never be edited here.
    password = ReadOnlyPasswordHashField(label=_("Password hash"))

    class Meta:
        model = User
        exclude: list[str] = []

    def clean_password(self) -> str:
        """Return the initial (unchanged) password hash."""
        return self.initial["password"]


class OSUserChangeList(ChangeList):
    """
    Custom ChangeList that replaces the normal Django ORM queryset with
    an OpenSearch query. Only IDs for the current page are fetched from
    the database so the order returned by OpenSearch is preserved.
    """

    def get_results(self, request) -> None:
        super().get_results(request)

        # Build the OpenSearch query
        query: Dict[str, Any] = {"bool": {"must": [], "filter": []}}

        # Handle free-text search from the search box
        if self.query:
            query["bool"]["must"].append(
                {
                    "multi_match": {
                        "query": self.query,
                        "fields": ["display_name", "email", "user_id"],
                    }
                }
            )

        # Boolean filters such as is_active, is_staff, is_superuser
        for param in ("is_active__exact", "is_staff__exact", "is_superuser__exact"):
            val = request.GET.get(param)
            if val in ("0", "1"):
                query["bool"]["filter"].append({"term": {param.split("__")[0]: bool(int(val))}})

        # Elite year filter: current year, any year, or none
        elite_val = request.GET.get("elite")
        current_year = datetime.date.today().year
        if elite_val == "current":
            query["bool"]["filter"].append({"term": {"elite_years": current_year}})
        elif elite_val == "any":
            query["bool"]["filter"].append({"exists": {"field": "elite_years"}})
        elif elite_val == "none":
            query["bool"]["must_not"] = [{"exists": {"field": "elite_years"}}]

        # Determine ordering based on the column header clicked
        ordering_tuple = self.get_ordering(request, self.root_queryset) or ("email",)

        sort_clause: List[Dict[str, Any]] = []
        for ordering in ordering_tuple:
            field = ordering.lstrip("-")
            if field not in ALLOWED_USER_SORT:
                # Ignore unsupported fields
                continue
            direction = "desc" if ordering.startswith("-") else "asc"
            sort_clause.append({field: {"order": direction}})
        if not sort_clause:
            # Fall back to a stable order by email ascending
            sort_clause = [{"email": {"order": "asc"}}]

        # Pagination parameters
        per_page = self.list_per_page
        page_idx = int(request.GET.get("p", "0"))  # OpenSearch uses zero-based pages
        start = page_idx * per_page

        # Execute the OpenSearch query
        res = op.search(
            index=settings.OPENSEARCH["USER_INDEX"],
            body={
                "query": query,
                "sort": sort_clause,
                "from": start,
                "size": per_page,
            },
            _source=False,
            track_total_hits=True,
        )

        total_raw = res["hits"].get("total", 0)
        total_hits = total_raw["value"] if isinstance(total_raw, dict) else int(total_raw)

        self.result_count = self.full_result_count = total_hits
        self.can_show_all = False
        self.multi_page = total_hits > per_page

        # Extract IDs and fetch only those rows with the ORM
        ids: List[str] = [hit["_id"] for hit in res["hits"]["hits"]]
        if not ids:
            self.result_list = User.objects.none()
            return

        # Preserve the OpenSearch order using a CASE expression
        preserve = Case(*[When(pk=pk, then=i) for i, pk in enumerate(ids)])
        self.result_list = User.objects.filter(pk__in=ids).order_by(preserve)

        # Build a dummy paginator so the admin templates work
        self.page_num = page_idx + 1  # Django templates expect one-based pages
        self.paginator = DummyPaginator(total_hits, per_page)


class EliteYearFilter(admin.SimpleListFilter):
    title = _("elite status")
    parameter_name = "elite"

    def lookups(self, request, model_admin):
        return (
            ("current", _("Current year")),
            ("any", _("Any elite year")),
            ("none", _("Never elite")),
        )

    # Filtering itself is handled in OSUserChangeList, so return None here.
    def queryset(self, *args):
        return None


class UserAdmin(BaseUserAdmin):
    """Admin interface for the User model with OpenSearch-powered list view."""

    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    list_display = (
        "email",
        "user_display_name",
        "review_count",
        "fans",
        "average_stars",
        "is_active",
        "is_staff",
    )
    ordering = ("email",)
    search_fields = ("email", "display_name", "user_id")
    list_filter = ("is_staff", "is_superuser", "is_active", EliteYearFilter)
    list_per_page = 100
    list_max_show_all = 1000
    show_full_result_count = False

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("display_name", "username", "user_id", "yelping_since")}),
        (_("Yelp stats"), {"fields": (("review_count", "average_stars"),
         ("useful", "funny", "cool"), "fans")}),
        (_("Friends & Elite"), {"fields": ("friends", "elite_years")}),
        (_("Compliments"), {
            "fields": (
                ("compliment_hot", "compliment_more", "compliment_profile"),
                ("compliment_cute", "compliment_list", "compliment_note"),
                ("compliment_plain", "compliment_cool", "compliment_funny"),
                ("compliment_writer", "compliment_photos"),
            )
        }),
        (_("Permissions"), {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    readonly_fields = (
        "user_id",
        "display_name",
        "yelping_since",
        "review_count",
        "useful",
        "funny",
        "cool",
        "fans",
        "average_stars",
        "friends",
        "compliment_hot",
        "compliment_more",
        "compliment_profile",
        "compliment_cute",
        "compliment_list",
        "compliment_note",
        "compliment_plain",
        "compliment_cool",
        "compliment_funny",
        "compliment_writer",
        "compliment_photos",
        "last_login",
        "date_joined",
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "display_name",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")

    @admin.display(description=_("Nickname"), ordering=None)
    def user_display_name(self, obj):
        return obj.display_name

    def get_changelist(self, request, **kwargs):
        """Tell Django to use the custom ChangeList defined above."""
        return OSUserChangeList

    # Action methods follow.

    @admin.action(description=_("Export selected users as CSV"))
    def export_as_csv(self, request, queryset):
        """Stream the selected users as a CSV download."""
        meta = self.model._meta
        fields = [f.name for f in meta.fields]
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="users_{datetime.date.today()}.csv"'
        writer = csv.writer(resp)
        writer.writerow(fields)
        for obj in queryset:
            writer.writerow([getattr(obj, f) for f in fields])
        return resp

    @admin.action(description=_("Activate selected users"))
    def activate_users(self, request, qs):
        """Set is_active to True for all selected users."""
        count = qs.update(is_active=True)
        self.message_user(request, _("%d user(s) activated.") % count)

    @admin.action(description=_("Deactivate selected users"))
    def deactivate_users(self, request, qs):
        """Set is_active to False for all selected users."""
        count = qs.update(is_active=False)
        self.message_user(request, _("%d user(s) deactivated.") % count)

    @admin.action(description=_("Grant current-year elite status to selected users"))
    def add_current_elite(self, request, qs):
        """Add the current year to each user's elite_years list."""
        year = datetime.date.today().year
        changed = 0
        for u in qs:
            years = set(u.elite_years)
            if year not in years:
                years.add(year)
                u.elite_years = sorted(years)
                u.save(update_fields=["elite_years"])
                changed += 1
        self.message_user(request, _("%d user(s) granted elite status for %d.") % (changed, year))

    @admin.action(description=_("Resend verification email to selected users"))
    def send_verification_again(self, request, qs):
        """Generate a new verification code and queue an email for each selected user."""
        for u in qs:
            code = get_random_string(6, "0123456789")
            cache.set(
                f"pending_register:{u.email}",
                {
                    "password_hash": u.password,
                    "display_name": u.display_name,
                    "verification_code": code,
                },
                timeout=600,
            )
            send_verification_email.delay(u.email, code)
        self.message_user(request, _("Verification email queued for selected users."))

    # List of callable names that appear in the action drop-down.
    actions = (
        "export_as_csv",
        "activate_users",
        "deactivate_users",
        "add_current_elite",
        "send_verification_again",
    )


# Register the admin class and customize site titles.
admin.site.register(User, UserAdmin)
admin.site.site_header = "Gastronome Administration"
admin.site.site_title = "Gastronome Admin"
admin.site.index_title = "Project Dashboard"
