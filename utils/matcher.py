import re
from difflib import SequenceMatcher


def _normalize(text):
    cleaned_text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return " ".join(cleaned_text.split())


def _tokens(text):
    normalized = _normalize(text)
    if not normalized:
        return set()
    return set(normalized.split())


GENERIC_BLOCKED_KEYWORDS = {
    "mold",
    "maker",
    "container",
    "bottle",
    "cup",
    "toy",
    "rack",
    "stand",
    "rusk",
    "biscuit",
    "cookies",
    "mix",
    "mixes",
    "milkshake",
    "shake",
    "flavoured",
    "flavored",
    "pan",
    "cake",
    "baking",
    "bakeware",
    "mixer",
    "machine",
    "utensil",
    "tray",
    "tin",
    "tool",
}


REQUEST_SPECIFIC_BLOCKERS = {
    "milk": {
        "powder",
        "milkshake",
        "shake",
        "soy",
        "soya",
        "oat",
        "almond",
        "coconut",
        "vegan",
        "substitute",
        "substitutes",
        "creamer",
        "badam",
        "flavoured",
        "flavored",
        "protein",
        "basundi",
        "cream",
        "fresh cream",
        "coffee",
        "latte",
        "evaporated",
        "condensed",
        "imported",
    },
    "bread": {
        "crumb",
        "crumbs",
        "flour",
        "yeast",
        "butter",
        "peanut",
        "chocolate",
        "spread",
        "cake",
        "rusk",
        "toast",
        "mix",
        "maker",
        "mold",
        "bake",
        "baking",
        "panko",
    },
    "rice": {"flour", "bran", "powder"},
    "sugar": {"free", "substitute"},
    "oil": {"essential", "fragrance", "hair", "massage"},
    "egg": {"powder", "masala"},
    "eggs": {"powder", "masala"},
}


def is_candidate_compatible(user_input, product_name):
    user_text = _normalize(user_input)
    product_text = _normalize(product_name)

    if not user_text or not product_text:
        return False

    user_tokens = _tokens(user_text)
    product_tokens = _tokens(product_text)
    token_overlap = user_tokens & product_tokens

    if not token_overlap:
        return False

    if any(keyword in product_tokens for keyword in GENERIC_BLOCKED_KEYWORDS if keyword not in user_tokens):
        return False

    for token, blockers in REQUEST_SPECIFIC_BLOCKERS.items():
        if token in user_tokens and any(blocker in product_text for blocker in blockers):
            return False

    return True


def product_similarity(user_input, product_name):
    user_text = _normalize(user_input)
    product_text = _normalize(product_name)

    if not user_text or not product_text:
        return 0

    user_tokens = user_text.split()
    product_tokens = product_text.split()

    if user_text == product_text:
        return 1.0

    if user_text in product_text:
        return 0.95

    overlap_ratio = len(set(user_tokens) & set(product_tokens)) / len(set(user_tokens))
    similarity_ratio = SequenceMatcher(None, user_text, product_text).ratio()

    return max(overlap_ratio, similarity_ratio)


def match_product(user_input, product_name, threshold=0.6):
    if not is_candidate_compatible(user_input, product_name):
        return False
    return product_similarity(user_input, product_name) >= threshold
