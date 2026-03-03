"""
Template context processors injected into every rendered template.

``category_keywords`` — maps UI category labels (e.g. "Restaurants") to
OpenSearch match keywords for sidebar filtering.

``rating_filters`` — provides the predefined star-rating filter labels
displayed in the search results sidebar.
"""

CATEGORY_KEYWORDS = {
    "Shops": ["shop"],
    "Hotels": ["hotel"],
    "Restaurants": ["restaurant"],
    "Bars": ["bar"],
    "Fitness": ["fitness", "gym", "exercise"],
    "Events": ["event"],
}

RATING_FILTERS = [
    "Excellent 4.5+",
    "Good 4+",
    "Fair 3+",
    "Even 2+",
    "Bad 1+",
]


def category_keywords(_request):
    return {"CATEGORY_KEYWORDS": CATEGORY_KEYWORDS}


def rating_filters(_request):
    return {"RATING_FILTERS": RATING_FILTERS}
