import importlib.util
import asyncio
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

from utils.matcher import product_similarity
from utils.env_loader import load_live_app_env


load_live_app_env()


def _ensure_playwright_event_loop_policy():
    if os.name != "nt":
        return
    try:
        current_policy = asyncio.get_event_loop_policy()
        if not isinstance(current_policy, asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


SUPPORTED_BROWSER_PLATFORMS = ("Blinkit", "Instamart", "Amazon", "Dmart", "Zepto", "Flipkart", "BigBasket")

PLATFORM_ENV_PREFIX = {
    "Blinkit": "BLINKIT",
    "Instamart": "INSTAMART",
    "Amazon": "AMAZON",
    "Dmart": "DMART",
    "Zepto": "ZEPTO",
    "Flipkart": "FLIPKART",
    "BigBasket": "BIGBASKET",
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


def _extract_amazon_picker_name(card, fallback_name):
    try:
        card_text = _normalize_space(card.inner_text(timeout=2000))
    except Exception:
        return fallback_name

    if not card_text:
        return fallback_name

    lines = [line.strip(" |") for line in card_text.splitlines() if line.strip()]
    if not lines:
        return fallback_name

    combined = " ".join(lines[:2])
    combined = re.split(r"\b\d+(\.\d+)? out of 5 stars\b", combined, maxsplit=1)[0]
    combined = re.split(r"\b\d+[Kk+]* bought in past month\b", combined, maxsplit=1)[0]
    combined = combined.replace("|", " ")
    candidate_name = _normalize_space(combined)

    if not candidate_name:
        return fallback_name

    if fallback_name and fallback_name.lower() in candidate_name.lower():
        return candidate_name

    return candidate_name


def _prepare_search_query(platform, requested_name):
    return requested_name


def _build_browser_search_url(config, query, pincode):
    return config["search_url"].format(
        query=quote_plus(query),
        pincode=quote_plus(pincode or ""),
    )


def _resolve_href(base_url, href):
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"{base_url}{href}"
    return f"{base_url}/{href}"


def _is_promising_browser_result(platform, requested_name, candidate_name, strict=True):
    similarity = product_similarity(requested_name, candidate_name)
    requested_tokens = set(re.findall(r"[a-z0-9]+", requested_name.lower()))
    lowered = candidate_name.lower()
    candidate_tokens = set(re.findall(r"[a-z0-9]+", lowered))

    if not strict:
        if requested_name.lower() in lowered:
            return True
        if requested_tokens & candidate_tokens and similarity >= 0.35:
            return True
        return similarity >= 0.45

    if similarity < 0.55:
        return False

    if platform not in {"Amazon", "Flipkart"}:
        return True

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
        "milkshake",
        "shake",
        "flavoured",
        "flavored",
        "coconut",
        "almond",
        "barista",
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
        "basundi",
        "cream",
        "latte",
    }

    if any(keyword in lowered for keyword in blocked_keywords) and not requested_tokens.intersection(blocked_keywords):
        return False

    if platform == "Flipkart":
        request_specific_blockers = {
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
                "mango",
                "strawberry",
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
                "mate",
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
        }

        for token, blockers in request_specific_blockers.items():
            if token in requested_tokens and any(blocker in lowered for blocker in blockers):
                return False

    minimum_similarity = 0.68 if platform == "Flipkart" else 0.62
    return bool(requested_tokens & candidate_tokens) and similarity >= minimum_similarity


def _collect_items_for_query(page, platform, requested_name, config, strict=True, limit=8):
    collected_items = []
    cards = page.locator(config["product_card_selector"])
    total_cards = min(cards.count(), 24)

    for index in range(total_cards):
        card = cards.nth(index)
        try:
            if platform == "Flipkart":
                name_locator = card.locator(config["name_selector"]).first
                name = _normalize_space(
                    name_locator.get_attribute("title") or name_locator.inner_text(timeout=3000)
                )
                major_price = card.locator('.QiMO5r .hZ3P6w')
                minor_price = card.locator('.QiMO5r .kRYCnD')
                if not major_price.count():
                    continue
                price_text = major_price.first.inner_text(timeout=3000).strip()
                if minor_price.count():
                    price_text = f"{price_text}.{minor_price.first.inner_text(timeout=3000).strip()}"
            else:
                name = _normalize_space(card.locator(config["name_selector"]).first.inner_text(timeout=3000))
                price_text = card.locator(config["price_selector"]).first.inner_text(timeout=3000).strip()
                if platform == "Amazon" and not strict:
                    name = _extract_amazon_picker_name(card, name)
            delivery = "N/A"

            if config["delivery_selector"] and not _is_placeholder(config["delivery_selector"]):
                try:
                    delivery = _normalize_space(
                        card.locator(config["delivery_selector"]).first.inner_text(timeout=1500)
                    )
                except Exception:
                    delivery = "N/A"

            price = _extract_price(price_text)
            if name and price is not None and _is_promising_browser_result(platform, requested_name, name, strict=strict):
                href = ""
                if platform == "Flipkart":
                    href = card.locator("a").first.get_attribute("href") or ""
                collected_items.append(
                    {
                        "name": name,
                        "price": price,
                        "delivery": delivery,
                        "_score": product_similarity(requested_name, name),
                        "_href": href,
                    }
                )
        except Exception:
            continue

    collected_items.sort(key=lambda item: (-item["_score"], item["price"]))
    trimmed_items = []
    for item in collected_items[:limit]:
        trimmed_items.append(
            {
                "name": item["name"],
                "price": item["price"],
                "delivery": item["delivery"],
                "_href": item.get("_href", ""),
            }
        )
    return trimmed_items


def search_browser_product_options(platform, search_term, pincode, limit=24):
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

    _ensure_playwright_event_loop_policy()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(session_path))
        page = context.new_page()

        search_query = _prepare_search_query(platform, search_term)
        search_url = _build_browser_search_url(config, search_query, pincode)
        page.goto(search_url, wait_until="domcontentloaded", timeout=45000)

        if platform == "Amazon":
            _apply_amazon_pincode(page, pincode)

        if config["wait_selector"] and not _is_placeholder(config["wait_selector"]):
            page.wait_for_selector(config["wait_selector"], timeout=15000)
        else:
            page.wait_for_timeout(4000)

        option_items = _collect_items_for_query(
            page,
            platform,
            search_term,
            config,
            strict=False,
            limit=limit,
        )

        context.close()
        browser.close()

    deduped_items = []
    seen_names = set()
    for item in option_items:
        dedupe_key = item["name"].lower()
        if dedupe_key in seen_names:
            continue
        seen_names.add(dedupe_key)
        deduped_items.append(item)

    return deduped_items


def _apply_flipkart_pincode(detail_page, pincode):
    if not pincode:
        return

    body = detail_page.locator("body").inner_text(timeout=5000)
    if pincode in body and "location not set" not in body.lower():
        return

    try:
        detail_page.get_by_text("Select delivery location", exact=False).first.click(timeout=5000)
        detail_page.wait_for_timeout(1500)
        location_input = detail_page.locator('input[placeholder="Search by area, street name, pin code"]').first
        location_input.fill(pincode)
        detail_page.wait_for_timeout(2500)
        detail_page.get_by_text(pincode, exact=False).first.click(timeout=5000)
        detail_page.wait_for_timeout(3500)
        detail_page.get_by_text("Confirm", exact=False).first.click(timeout=5000)
        detail_page.wait_for_timeout(6000)
    except Exception:
        return


def _apply_amazon_pincode(page, pincode):
    if not pincode:
        return

    try:
        current_location = page.locator("#glow-ingress-line2")
        if current_location.count():
            location_text = current_location.first.inner_text(timeout=2000)
            if pincode in location_text:
                return
    except Exception:
        pass

    try:
        page.locator("#nav-global-location-popover-link").first.click(timeout=5000)
        page.wait_for_timeout(2500)
        zip_input = page.locator("#GLUXZipUpdateInput").first
        zip_input.fill("")
        zip_input.fill(pincode)
        page.locator("#GLUXZipUpdate").first.click(timeout=5000)
        page.wait_for_timeout(4500)

        confirm_button = page.locator("#GLUXConfirmClose")
        if confirm_button.count():
            try:
                confirm_button.first.click(timeout=3000)
                page.wait_for_timeout(2500)
            except Exception:
                pass
    except Exception:
        return


def _extract_flipkart_delivery_text(body_text):
    lowered = body_text.lower()
    if "not deliverable at your location" in lowered:
        return "Not deliverable at your location"

    match = re.search(r"Delivery details\s+.*?\s+Delivery\s+by\s+([^\n]+)", body_text, re.IGNORECASE | re.DOTALL)
    if match:
        return _normalize_space(f"Delivery by {match.group(1)}")

    return "N/A"


def _enrich_flipkart_delivery(context, items, pincode):
    detail_page = context.new_page()

    for item in items:
        href = item.get("_href", "")
        if not href:
            continue

        try:
            detail_page.goto(_resolve_href("https://www.flipkart.com", href), wait_until="domcontentloaded", timeout=45000)
            detail_page.wait_for_timeout(3000)
            _apply_flipkart_pincode(detail_page, pincode)
            body = detail_page.locator("body").inner_text(timeout=5000)
            item["delivery"] = _extract_flipkart_delivery_text(body)
        except Exception:
            continue

    detail_page.close()

    return [
        {
            "name": item["name"],
            "price": item["price"],
            "delivery": item["delivery"],
        }
        for item in items
    ]


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

    _ensure_playwright_event_loop_policy()
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

            if platform == "Amazon":
                _apply_amazon_pincode(page, pincode)

            if config["wait_selector"] and not _is_placeholder(config["wait_selector"]):
                page.wait_for_selector(config["wait_selector"], timeout=15000)
            else:
                page.wait_for_timeout(4000)

            query_items = _collect_items_for_query(page, platform, requested_name, config)
            if platform == "Flipkart" and query_items:
                query_items = _enrich_flipkart_delivery(context, query_items, pincode)
            items.extend(query_items)

        context.close()
        browser.close()

    deduped_items = []
    seen_names = set()
    for item in items:
        dedupe_key = item["name"].lower()
        if dedupe_key in seen_names:
            continue
        seen_names.add(dedupe_key)
        deduped_items.append(
            {
                "name": item["name"],
                "price": item["price"],
                "delivery": item["delivery"],
            }
        )

    return deduped_items
