import re
from difflib import SequenceMatcher


def _normalize(text):
    cleaned_text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return " ".join(cleaned_text.split())


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
    return product_similarity(user_input, product_name) >= threshold
