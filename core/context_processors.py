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