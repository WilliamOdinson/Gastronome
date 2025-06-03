from math import ceil
from django.core.paginator import Paginator


class DummyPaginator:
    """
    Lightweight paginator for use with OpenSearch-based ChangeLists.
    Only used to render pagination controls in Django admin templates.
    """
    ELLIPSIS = Paginator.ELLIPSIS

    def __init__(self, total: int, per: int):
        self.count = total
        self.per_page = per
        self.num_pages = ceil(total / per) if per else 0
        self.page_range = range(1, self.num_pages + 1)
        self._real = Paginator(range(total), per) if per else None

    def get_elided_page_range(
        self,
        number: int,
        *,
        on_each_side: int = 3,
        on_ends: int = 2,
    ):
        if not self._real:
            return []
        return self._real.get_elided_page_range(
            number,
            on_each_side=on_each_side,
            on_ends=on_ends,
        )
