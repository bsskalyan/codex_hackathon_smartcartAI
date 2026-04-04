import json
import os
from urllib.parse import quote_plus

import requests
from providers.amazon_paapi import search_amazon_products


SOURCES = {
    "Blinkit": "data/blinkit.json",
    "Instamart": "data/instamart.json",
    "Amazon": "data/amazon.json",
    "Dmart": "data/dmart.json",
    "Zepto": "data/zetpo.json",
}

LIVE_ENDPOINT_ENV = {
    "Blinkit": "LIVE_BLINKIT_SEARCH_URL",
    "Instamart": "LIVE_INSTAMART_SEARCH_URL",
    "Dmart": "LIVE_DMART_SEARCH_URL",
    "Zepto": "LIVE_ZEPTO_SEARCH_URL",
}


def _is_placeholder(value):
    lowered = value.strip().lower()
    return (
        not lowered
        or "your-" in lowered
        or "your_" in lowered
        or ".example" in lowered
    )


def load_mock_catalog(platform):
    with open(SOURCES[platform], "r") as file:
        return json.load(file)


def _normalize_live_items(payload):
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("items") or payload.get("products") or payload.get("results") or []
    else:
        items = []

    normalized_items = []
    for item in items:
        name = item.get("name") or item.get("title") or item.get("product_name")
        price = item.get("price") or item.get("amount") or item.get("selling_price")
        delivery = item.get("delivery") or item.get("delivery_eta") or item.get("eta") or "N/A"

        if name and price is not None:
            normalized_items.append(
                {
                    "name": str(name),
                    "price": float(price),
                    "delivery": str(delivery),
                }
            )

    return normalized_items


def load_live_catalog(platform, product_requests, pincode):
    endpoint_template = os.getenv(LIVE_ENDPOINT_ENV[platform], "").strip()

    if _is_placeholder(endpoint_template):
        raise ValueError(f"Missing endpoint configuration for {platform}")

    query = ", ".join(request["name"] for request in product_requests)
    endpoint = endpoint_template.format(
        query=quote_plus(query),
        pincode=quote_plus(pincode or ""),
    )

    response = requests.get(endpoint, timeout=15)
    response.raise_for_status()
    return _normalize_live_items(response.json())


def get_catalogs(product_requests, pincode, data_mode):
    catalogs = {}
    warnings = []

    for platform in SOURCES:
        if data_mode == "live":
            try:
                if platform == "Amazon":
                    live_catalog = search_amazon_products(product_requests)
                else:
                    live_catalog = load_live_catalog(platform, product_requests, pincode)
                if live_catalog:
                    catalogs[platform] = live_catalog
                    continue
                warnings.append(f"{platform}: live source returned no items, using mock data.")
            except Exception as error:
                warnings.append(f"{platform}: live fetch failed ({error}), using mock data.")

        catalogs[platform] = load_mock_catalog(platform)

    return catalogs, warnings
