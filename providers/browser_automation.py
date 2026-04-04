import importlib.util
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

from utils.matcher import product_similarity


SUPPORTED_BROWSER_PLATFORMS = ("Blinkit", "Instamart", "Amazon", "Dmart", "Zepto")

PLATFORM_ENV_PREFIX = {
    "Blinkit": "BLINKIT",
    "Instamart": "INSTAMART",
    "Amazon": "AMAZON",
    "Dmart": "DMART",
    "Zepto": "ZEPTO",
}

SESSIONS_DIR = Path(__file__).resolve().parents[1] / ".sessions"


def _env(name, default=""):
    return os.getenv(name, default).strip()


def _is_placeholder(value):
    lowered = value.strip().lower()
    return (
        not lowered
        or "your-" in lowered
        or "your_" in lowered
        or ".example" in lowered
    )


def is_playwright_installed():
    return importlib.util.find_spec("playwright") is not None


def ensure_sessions_dir():
    SESSIONS_DIR.mkdir(exist_ok=True)
    return SESSIONS_DIR


def get_session_path(platform):
    ensure_sessions_dir()
    safe_name = platform.lower().replace(" ", "_")
    return SESSIONS_DIR / f"{safe_name}_session.json"


def get_platform_browser_config(platform):
    prefix = PLATFORM_ENV_PREFIX[platform]
    return {
        "login_url": _env(f"BROWSER_{prefix}_LOGIN_URL"),
        "search_url": _env(f"BROWSER_{prefix}_SEARCH_URL"),
        "product_card_selector": _env(f"BROWSER_{prefix}_PRODUCT_CARD_SELECTOR"),
        "name_selector": _env(f"BROWSER_{prefix}_NAME_SELECTOR"),
        "price_selector": _env(f"BROWSER_{prefix}_PRICE_SELECTOR"),
        "delivery_selector": _env(f"BROWSER_{prefix}_DELIVERY_SELECTOR"),
        "wait_selector": _env(f"BROWSER_{prefix}_WAIT_SELECTOR"),
    }


def get_browser_login_command(platform):
    session_path = get_session_path(platform)
    return (
        f'python scripts/browser_session_login.py --platform "{platform}" '
        f'--session-path "{session_path}"'
    )


def get_browser_provider_status():
    playwright_ready = is_playwright_installed()
    statuses = {}

    for platform in SUPPORTED_BROWSER_PLATFORMS:
        config = get_platform_browser_config(platform)
        session_path = get_session_path(platform)
        statuses[platform] = {
            "playwright_installed": playwright_ready,
            "session_saved": session_path.exists(),
            "session_path": str(session_path),
            "login_url_configured": not _is_placeholder(config["login_url"]),
            "search_url_configured": not _is_placeholder(config["search_url"]),
            "selectors_configured": all(
                not _is_placeholder(config[key])
                for key in ("product_card_selector", "name_selector", "price_selector")
            ),
            "login_command": get_browser_login_command(platform),
        }

    return statuses


def _extract_price(raw_price):
    cleaned = "".join(character for character in raw_price if character.isdigit() or character == ".")
    if not cleaned:
        return None
    return float(cleaned)


def _normalize_space(text):
    return re.sub(r"\s+", " ", text).strip()


def _prepare_search_query(platform, requested_name):
    if platform == "Amazon":
        return f"{requested_name} grocery"
    return requested_name


def _build_browser_search_url(config, query, pincode):
    return config["search_url"].format(
        query=quote_plus(query),
        pincode=quote_plus(pincode or ""),
    )


def _is_promising_browser_result(platform, requested_name, candidate_name):
    similarity = product_similarity(requested_name, candidate_name)

    if similarity < 0.55:
        return False

    if platform != "Amazon":
        return True

    lowered = candidate_name.lower()
    blocked_keywords = {
        "mold",
        "maker",
        "container",
        "bottle",
        "cup",
        "toy",
        "rack",
        "stand",
        "powder",
        "rusk",
        "biscuit",
        "cookies",
        "mix",
        "mixes",
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
        "soap",
        "shampoo",
    }
    requested_tokens = set(re.findall(r"[a-z0-9]+", requested_name.lower()))
    candidate_tokens = set(re.findall(r"[a-z0-9]+", lowered))

    if any(keyword in lowered for keyword in blocked_keywords) and not requested_tokens.intersection(blocked_keywords):
        return False

    return bool(requested_tokens & candidate_tokens) and similarity >= 0.62


def _collect_items_for_query(page, platform, requested_name, config):
    collected_items = []
    cards = page.locator(config["product_card_selector"])
    total_cards = min(cards.count(), 24)

    for index in range(total_cards):
        card = cards.nth(index)
        try:
            name = _normalize_space(card.locator(config["name_selector"]).first.inner_text(timeout=3000))
            price_text = card.locator(config["price_selector"]).first.inner_text(timeout=3000).strip()
            delivery = "N/A"

            if config["delivery_selector"] and not _is_placeholder(config["delivery_selector"]):
                try:
                    delivery = _normalize_space(
                        card.locator(config["delivery_selector"]).first.inner_text(timeout=1500)
                    )
                except Exception:
                    delivery = "N/A"

            price = _extract_price(price_text)
            if name and price is not None and _is_promising_browser_result(platform, requested_name, name):
                collected_items.append(
                    {
                        "name": name,
                        "price": price,
                        "delivery": delivery,
                        "_score": product_similarity(requested_name, name),
                    }
                )
        except Exception:
            continue

    collected_items.sort(key=lambda item: (-item["_score"], item["price"]))
    trimmed_items = []
    for item in collected_items[:8]:
        trimmed_items.append(
            {
                "name": item["name"],
                "price": item["price"],
                "delivery": item["delivery"],
            }
        )
    return trimmed_items


def load_browser_catalog(platform, product_requests, pincode):
    if not is_playwright_installed():
        raise ValueError("Playwright is not installed. Add it to the environment first.")

    session_path = get_session_path(platform)
    if not session_path.exists():
        raise ValueError(f"No saved browser session found for {platform}")

    config = get_platform_browser_config(platform)
    if _is_placeholder(config["search_url"]):
        raise ValueError(f"Missing browser search URL configuration for {platform}")
    if not all(
        not _is_placeholder(config[key])
        for key in ("product_card_selector", "name_selector", "price_selector")
    ):
        raise ValueError(f"Missing browser selector configuration for {platform}")

    from playwright.sync_api import sync_playwright

    items = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(session_path))
        page = context.new_page()

        for request in product_requests:
            requested_name = request["name"]
            search_query = _prepare_search_query(platform, requested_name)
            search_url = _build_browser_search_url(config, search_query, pincode)
            page.goto(search_url, wait_until="domcontentloaded", timeout=45000)

            if config["wait_selector"] and not _is_placeholder(config["wait_selector"]):
                page.wait_for_selector(config["wait_selector"], timeout=15000)
            else:
                page.wait_for_timeout(4000)

            items.extend(_collect_items_for_query(page, platform, requested_name, config))

        context.close()
        browser.close()

    deduped_items = []
    seen_names = set()
    for item in items:
        dedupe_key = item["name"].lower()
        if dedupe_key in seen_names:
            continue
        seen_names.add(dedupe_key)
        deduped_items.append(item)

    return deduped_items
