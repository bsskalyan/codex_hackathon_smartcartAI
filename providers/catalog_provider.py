import json
import os
from urllib.parse import quote_plus

import requests
from providers.amazon_paapi import search_amazon_products
from providers.browser_automation import get_browser_provider_status, load_browser_catalog
from utils.env_loader import load_live_app_env


load_live_app_env()


SOURCES = {
    "Blinkit": "data/blinkit.json",
    "Instamart": "data/instamart.json",
    "Amazon": "data/amazon.json",
    "Dmart": "data/dmart.json",
    "Zepto": "data/zepto.json",
    "Flipkart": "data/flipkart.json",
    "BigBasket": "data/bigbasket.json",
}

LIVE_ENDPOINT_ENV = {
    "Blinkit": "LIVE_BLINKIT_SEARCH_URL",
    "Instamart": "LIVE_INSTAMART_SEARCH_URL",
    "Dmart": "LIVE_DMART_SEARCH_URL",
    "Zepto": "LIVE_ZEPTO_SEARCH_URL",
    "Flipkart": "LIVE_FLIPKART_SEARCH_URL",
    "BigBasket": "LIVE_BIGBASKET_SEARCH_URL",
}


def _is_placeholder(value):
    lowered = value.strip().lower()
    return (
        not lowered
        or "your-" in lowered
        or "your_" in lowered
        or ".example" in lowered
    )


def get_live_configuration_status():
    status = {}
    browser_status = get_browser_provider_status()

    for platform, env_name in LIVE_ENDPOINT_ENV.items():
        configured_value = os.getenv(env_name, "").strip()
        browser_ready = browser_status.get(platform, {})
        status[platform] = {
            "configured": (
                not _is_placeholder(configured_value)
                or (
                    browser_ready.get("playwright_installed")
                    and browser_ready.get("session_saved")
                    and browser_ready.get("search_url_configured")
                    and browser_ready.get("selectors_configured")
                )
            ),
            "type": "endpoint or browser session",
            "env_name": env_name,
            "browser_session_saved": browser_ready.get("session_saved", False),
            "browser_ready": (
                browser_ready.get("playwright_installed")
                and browser_ready.get("session_saved")
                and browser_ready.get("search_url_configured")
                and browser_ready.get("selectors_configured")
            ),
        }

    amazon_browser_ready = browser_status.get("Amazon", {})
    amazon_env_names = [
        "AMAZON_PAAPI_ACCESS_KEY",
        "AMAZON_PAAPI_SECRET_KEY",
        "AMAZON_PAAPI_PARTNER_TAG",
    ]
    amazon_ready = all(not _is_placeholder(os.getenv(env_name, "").strip()) for env_name in amazon_env_names)
    status["Amazon"] = {
        "configured": (
            amazon_ready
            or (
                amazon_browser_ready.get("playwright_installed")
                and amazon_browser_ready.get("session_saved")
                and amazon_browser_ready.get("search_url_configured")
                and amazon_browser_ready.get("selectors_configured")
            )
        ),
        "type": "credentials or browser session",
        "env_name": ", ".join(amazon_env_names),
        "browser_session_saved": amazon_browser_ready.get("session_saved", False),
        "browser_ready": (
            amazon_browser_ready.get("playwright_installed")
            and amazon_browser_ready.get("session_saved")
            and amazon_browser_ready.get("search_url_configured")
            and amazon_browser_ready.get("selectors_configured")
        ),
    }

    return status


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


def _format_error(error):
    text = str(error).strip()
    if text:
        return text
    return type(error).__name__


def get_catalogs(product_requests, pincode, data_mode, selected_platforms=None, fallback_to_mock_on_live_failure=True):
    catalogs = {}
    warnings = []
    browser_status = get_browser_provider_status()
    platforms_to_use = selected_platforms or list(SOURCES.keys())

    for platform in platforms_to_use:
        if data_mode == "live":
            try:
                if platform == "Amazon":
                    try:
                        live_catalog = search_amazon_products(product_requests)
                    except Exception as amazon_error:
                        browser_ready = browser_status.get(platform, {})
                        if (
                            browser_ready.get("playwright_installed")
                            and browser_ready.get("session_saved")
                            and browser_ready.get("search_url_configured")
                            and browser_ready.get("selectors_configured")
                        ):
                            live_catalog = load_browser_catalog(platform, product_requests, pincode)
                            warnings.append(
                                f"{platform}: PA-API unavailable ({_format_error(amazon_error)}); browser session search used instead."
                            )
                        else:
                            raise amazon_error
                else:
                    try:
                        live_catalog = load_live_catalog(platform, product_requests, pincode)
                    except Exception as endpoint_error:
                        browser_ready = browser_status.get(platform, {})
                        if (
                            browser_ready.get("playwright_installed")
                            and browser_ready.get("session_saved")
                            and browser_ready.get("search_url_configured")
                            and browser_ready.get("selectors_configured")
                        ):
                            live_catalog = load_browser_catalog(platform, product_requests, pincode)
                            warnings.append(
                                f"{platform}: API endpoint unavailable ({_format_error(endpoint_error)}); browser session search used instead."
                            )
                        else:
                            raise endpoint_error
                if live_catalog:
                    catalogs[platform] = live_catalog
                    continue
                if fallback_to_mock_on_live_failure:
                    warnings.append(f"{platform}: live source returned no items, using mock data.")
                else:
                    warnings.append(f"{platform}: live source returned no items.")
            except Exception as error:
                if fallback_to_mock_on_live_failure:
                    warnings.append(f"{platform}: live fetch failed ({_format_error(error)}), using mock data.")
                else:
                    warnings.append(f"{platform}: live fetch failed ({_format_error(error)}).")

        if data_mode == "live" and not fallback_to_mock_on_live_failure:
            catalogs[platform] = []
        else:
            catalogs[platform] = load_mock_catalog(platform)

    return catalogs, warnings
