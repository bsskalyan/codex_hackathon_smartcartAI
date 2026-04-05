import re

import pandas as pd
import streamlit as st

from providers.browser_automation import get_browser_provider_status, search_browser_product_options
from providers.catalog_provider import get_catalogs, get_live_configuration_status
from utils.comparator import (
    compare_product_list,
    get_quantity_options,
    get_recommended_platform,
    optimize_basket,
    optimize_split_basket,
    parse_quantity_choice,
)
from utils.env_loader import load_live_app_env
from utils.matcher import product_similarity


PRESET_BASKETS = {
    "Weekly Essentials": [
        {"name": "milk", "pack_size": "1 litre", "count": 2},
        {"name": "bread", "pack_size": "1 pcs", "count": 2},
        {"name": "eggs", "pack_size": "12 pcs", "count": 1},
    ],
    "Kitchen Staples": [
        {"name": "rice", "pack_size": "5 kg", "count": 1},
        {"name": "sugar", "pack_size": "1 kg", "count": 1},
        {"name": "sunflower oil", "pack_size": "1 litre", "count": 1},
    ],
    "Snack Run": [
        {"name": "chips", "pack_size": "2 pcs", "count": 2},
        {"name": "juice", "pack_size": "1 litre", "count": 1},
        {"name": "biscuits", "pack_size": "2 pcs", "count": 2},
    ],
}

DEFAULT_BASKET = [
    ("milk", "1 litre", 1),
    ("bread", "1 pcs", 2),
]

LIVE_COMPARISON_PLATFORMS = ["Amazon", "Flipkart"]
APP_BUILD = "2026-04-05-stable-v4"


def inject_theme():
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(99, 102, 241, 0.16), transparent 30%),
                radial-gradient(circle at top right, rgba(45, 212, 191, 0.16), transparent 28%),
                radial-gradient(circle at bottom, rgba(56, 189, 248, 0.14), transparent 26%),
                linear-gradient(180deg, #f4f8ff 0%, #eef6fb 46%, #edf7f5 100%);
            color: #152538;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(125, 145, 180, 0.18);
            border-radius: 20px;
            box-shadow: 0 18px 50px rgba(53, 92, 136, 0.08);
            backdrop-filter: blur(10px);
        }
        .hero-card {
            padding: 1.5rem 1.7rem;
            border-radius: 24px;
            background: linear-gradient(135deg, #243b53 0%, #355c7d 42%, #2a9d8f 100%);
            color: #f7fbff;
            box-shadow: 0 24px 60px rgba(36, 59, 83, 0.24);
            margin-bottom: 1rem;
        }
        .hero-card h1 {
            margin: 0;
            font-size: 2.35rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }
        .hero-card p {
            margin: 0.6rem 0 0;
            font-size: 1rem;
            max-width: 760px;
        }
        .section-note {
            padding: 0.9rem 1rem;
            border-radius: 16px;
            background: linear-gradient(135deg, rgba(244, 248, 255, 0.96), rgba(234, 245, 243, 0.96));
            border: 1px solid rgba(125, 145, 180, 0.18);
            color: #34506b;
            margin: 0.3rem 0 1rem;
        }
        .stButton > button {
            border-radius: 12px;
            border: none;
            background: linear-gradient(135deg, #355c7d, #3aa6b9);
            color: #f7fbff;
            font-weight: 700;
            box-shadow: 0 10px 24px rgba(53, 92, 125, 0.18);
        }
        .stButton > button:hover {
            color: #f7fbff;
            filter: brightness(1.03);
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(243,248,255,0.94));
            border: 1px solid rgba(125, 145, 180, 0.18);
            padding: 0.8rem;
            border-radius: 16px;
        }
        .match-card {
            padding: 0.9rem 1rem;
            border-radius: 16px;
            background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(240,247,251,0.94));
            border: 1px solid rgba(125, 145, 180, 0.16);
            margin-bottom: 0.55rem;
        }
        .match-card-title {
            font-size: 1rem;
            font-weight: 700;
            color: #18324a;
        }
        .match-card-meta {
            font-size: 0.88rem;
            color: #486581;
            margin-top: 0.25rem;
        }
        .match-card-price {
            font-size: 0.95rem;
            font-weight: 700;
            color: #2a9d8f;
            margin-top: 0.45rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_currency(value):
    if float(value).is_integer():
        return f"Rs {int(value)}"
    return f"Rs {value:.2f}"


def validate_indian_pincode(pincode):
    normalized = pincode.strip()
    if not normalized:
        return "Enter a valid Indian pincode to continue."
    if not re.fullmatch(r"[1-9][0-9]{5}", normalized):
        return "Enter a correct 6-digit Indian pincode."
    return ""


def build_lookup_request(search_term):
    return [{
        "name": search_term,
        "quantity": 1,
        "quantity_unit": "pcs",
        "quantity_label": "1 pcs",
        "item_count": 1,
    }]


def infer_brand(product_name):
    tokens = product_name.replace("|", " ").split()
    if not tokens:
        return "Other"
    return tokens[0].strip(".,-").title()


def infer_category(product_name):
    lowered = product_name.lower()
    rules = {
        "Milk": ["milk"],
        "Biscuits": ["biscuit", "cookie", "cracker", "rusk"],
        "Bread": ["bread", "bun", "loaf"],
        "Rice & Grains": ["rice", "atta", "flour", "grain"],
        "Snacks": ["chips", "namkeen", "snack"],
        "Beverages": ["juice", "tea", "coffee", "drink", "lassi"],
        "Dairy": ["curd", "paneer", "butter", "cheese", "cream"],
    }
    for category, keywords in rules.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Other"


def build_compare_name(product_name):
    compare_name = product_name.strip()
    compare_name = re.sub(r"\s+\d+(?:\.\d+)?\s*$", "", compare_name)
    compare_name = re.sub(r"\s+\d+(?:\.\d+)?\s+out of 5 stars.*$", "", compare_name, flags=re.IGNORECASE)
    compare_name = re.sub(r"\s+\(\d+(?:\.\d+)?[Kk]?\)\s*$", "", compare_name)
    return compare_name.strip(" |-")


def row_keys(index):
    return {
        "name": f"product_name_{index}",
        "compare": f"product_compare_name_{index}",
        "compare_display": f"product_compare_display_{index}",
        "source": f"product_source_{index}",
        "pack": f"product_pack_size_{index}",
        "count": f"product_count_{index}",
        "options": f"product_options_{index}",
        "warnings": f"product_option_warnings_{index}",
        "searched_name": f"product_option_searched_name_{index}",
        "selected": f"selected_match_{index}",
    }


def clear_match_state(index):
    keys = row_keys(index)
    for key in ("compare", "compare_display", "source", "options", "warnings", "searched_name", "selected"):
        st.session_state.pop(keys[key], None)


def initialize_state():
    st.session_state.setdefault("item_count", len(DEFAULT_BASKET))
    st.session_state.setdefault("previous_data_mode", "mock")
    st.session_state.setdefault("auto_compare_enabled", True)
    for index, (name, pack_size, count) in enumerate(DEFAULT_BASKET):
        keys = row_keys(index)
        st.session_state.setdefault(keys["name"], name)
        st.session_state.setdefault(keys["pack"], pack_size)
        st.session_state.setdefault(keys["count"], count)


def apply_pending_updates():
    pending = st.session_state.pop("pending_state_updates", {})
    for key, value in pending.items():
        st.session_state[key] = value


def queue_state_updates(updates):
    pending = st.session_state.get("pending_state_updates", {})
    pending.update(updates)
    st.session_state["pending_state_updates"] = pending


def clear_basket(item_count=1):
    current_items = st.session_state.get("item_count", 1)
    for index in range(max(current_items, item_count)):
        keys = row_keys(index)
        for key in keys.values():
            st.session_state.pop(key, None)
    st.session_state["item_count"] = item_count
    for index in range(item_count):
        keys = row_keys(index)
        st.session_state.setdefault(keys["name"], "")
        st.session_state.setdefault(keys["pack"], "1 pcs")
        st.session_state.setdefault(keys["count"], 1)


def set_default_mock_basket():
    clear_basket(item_count=len(DEFAULT_BASKET))
    for index, (name, pack_size, count) in enumerate(DEFAULT_BASKET):
        keys = row_keys(index)
        st.session_state[keys["name"]] = name
        st.session_state[keys["pack"]] = pack_size
        st.session_state[keys["count"]] = count
    pending = st.session_state.get("pending_state_updates", {})
    pending["auto_compare_enabled"] = True
    st.session_state["pending_state_updates"] = pending


def set_empty_live_basket():
    clear_basket(item_count=1)
    pending = st.session_state.get("pending_state_updates", {})
    pending["auto_compare_enabled"] = False
    st.session_state["pending_state_updates"] = pending


def load_preset_basket(preset_name):
    items = PRESET_BASKETS[preset_name]
    clear_basket(item_count=len(items))
    for index, item in enumerate(items):
        keys = row_keys(index)
        st.session_state[keys["name"]] = item["name"]
        st.session_state[keys["pack"]] = item["pack_size"]
        st.session_state[keys["count"]] = item["count"]


def sync_row_state(index):
    keys = row_keys(index)
    current_name = st.session_state.get(keys["name"], "").strip()
    compare_display = st.session_state.get(keys["compare_display"], "").strip()
    if compare_display and compare_display != current_name:
        clear_match_state(index)


def build_product_requests():
    requests = []
    for index in range(st.session_state["item_count"]):
        keys = row_keys(index)
        name_value = st.session_state.get(keys["name"], "").strip()
        if not name_value:
            continue
        compare_name = st.session_state.get(keys["compare"], "").strip()
        compare_display = st.session_state.get(keys["compare_display"], "").strip()
        product_source = st.session_state.get(keys["source"], "live").strip() or "live"
        quantity_choice = st.session_state.get(keys["pack"], "1 pcs")
        count_value = st.session_state.get(keys["count"], 1)
        quantity_value, quantity_unit = parse_quantity_choice(quantity_choice)
        effective_name = compare_name if compare_name and compare_display == name_value else name_value
        requests.append(
            {
                "name": effective_name,
                "display_name": name_value,
                "quantity": quantity_value,
                "quantity_unit": quantity_unit,
                "quantity_label": quantity_choice,
                "item_count": count_value,
                "source": product_source,
            }
        )
    return requests


def prepare_requests_for_live_compare(product_requests):
    prepared = []
    for request in product_requests:
        normalized = dict(request)
        if normalized.get("source") == "mock":
            normalized["name"] = normalized.get("display_name", normalized["name"])
            normalized["source"] = "manual"
        prepared.append(normalized)
    return prepared


def collect_options_from_catalogs(search_term, catalogs):
    search_lower = search_term.lower()
    tokens = search_lower.split()
    scored = {}
    for platform, items in catalogs.items():
        for item in items:
            name = item["name"].strip()
            similarity = product_similarity(search_term, name)
            lowered = name.lower()
            if search_lower in lowered or any(token in lowered for token in tokens) or similarity >= 0.5:
                existing = scored.get(name)
                option = {
                    "name": name,
                    "compare_name": build_compare_name(name),
                    "brand": infer_brand(name),
                    "category": infer_category(name),
                    "price": float(item.get("price", 0)),
                    "platforms": {platform},
                    "score": similarity,
                    "source": item.get("source", "mock"),
                }
                if existing is None:
                    scored[name] = option
                else:
                    existing["score"] = max(existing["score"], option["score"])
                    existing["price"] = min(existing["price"], option["price"])
                    existing["platforms"].add(platform)
                    if existing.get("source") != "live" and option.get("source") == "live":
                        existing["source"] = "live"
    ordered = sorted(scored.values(), key=lambda item: (-item["score"], item["price"], item["name"].lower()))
    results = []
    for option in ordered[:40]:
        results.append(
            {
                "name": option["name"],
                "compare_name": option["compare_name"],
                "brand": option["brand"],
                "category": option["category"],
                "price": option["price"],
                "platforms": sorted(option["platforms"]),
                "source": option.get("source", "mock"),
            }
        )
    return results


def collect_product_options(search_term, pincode, data_mode):
    search_term = search_term.strip()
    if not search_term:
        return [], []

    if data_mode == "live":
        warnings = []
        platform_catalogs = {}
        for platform in LIVE_COMPARISON_PLATFORMS:
            try:
                live_items = search_browser_product_options(platform, search_term, pincode, limit=24)
                for item in live_items:
                    item["source"] = "live"
                platform_catalogs[platform] = live_items
            except Exception as error:
                platform_catalogs[platform] = []
                warnings.append(f"{platform}: {error}")
        options = collect_options_from_catalogs(search_term, platform_catalogs)
        if options:
            return options, warnings
        fallback_catalogs, _ = get_catalogs(build_lookup_request(search_term), pincode, "mock")
        for items in fallback_catalogs.values():
            for item in items:
                item["source"] = "mock"
        warnings.append("Live picker search was empty, so demo suggestions are shown to help you continue.")
        return collect_options_from_catalogs(search_term, fallback_catalogs), warnings

    catalogs, warnings = get_catalogs(build_lookup_request(search_term), pincode, "mock")
    for items in catalogs.values():
        for item in items:
            item["source"] = "mock"
    return collect_options_from_catalogs(search_term, catalogs), warnings


def render_platform_cards(totals, recommended_row):
    if not totals:
        return
    st.markdown("#### Platform Spotlight")
    columns = st.columns(min(len(totals), 5))
    for index, row in enumerate(totals[:5]):
        badge = "Recommended" if recommended_row and row["Platform"] == recommended_row["Platform"] else "Compared"
        columns[index].markdown(
            f"""
            <div class="match-card">
                <div class="match-card-meta">{badge}</div>
                <div class="match-card-title">{row["Platform"]}</div>
                <div class="match-card-price">{format_currency(row["Final Payable"])} </div>
                <div class="match-card-meta">{row["Items Found"]} items found</div>
                <div class="match-card-meta">Delivery: {row["Delivery"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


load_live_app_env()
st.set_page_config(page_title="SmartCart AI", page_icon=":shopping_trolley:", layout="wide")
initialize_state()
apply_pending_updates()
inject_theme()

st.markdown(
    """
    <div class="hero-card">
        <h1>SmartCart AI</h1>
        <p>Build a grocery basket once, compare platforms clearly, and keep mock and live modes easy to use.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="section-note">
        Mock Catalog is the reliable demo mode. Live Portals uses Amazon and Flipkart browser sessions when available.
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(f"Build: {APP_BUILD}")

with st.container(border=True):
    st.subheader("Basket Builder")
    top1, top2, top3, top4 = st.columns([1.1, 1.1, 1, 1])
    with top1:
        pincode = st.text_input("Pincode", placeholder="Enter delivery pincode")
    with top2:
        recommendation_mode = st.selectbox("Recommendation Mode", ["Cheapest", "Fastest", "Best Value"])
    with top3:
        data_mode = st.selectbox(
            "Data Source",
            ["mock", "live"],
            format_func=lambda value: "Mock Catalog" if value == "mock" else "Live Portals",
        )
    with top4:
        auto_compare = st.toggle("Auto Compare", key="auto_compare_enabled")

    if data_mode != st.session_state.get("previous_data_mode"):
        if data_mode == "live":
            set_empty_live_basket()
        else:
            set_default_mock_basket()
        st.session_state["previous_data_mode"] = data_mode
        st.rerun()

    pincode_error = validate_indian_pincode(pincode)
    if pincode_error:
        st.warning(pincode_error)

    if data_mode == "live":
        with st.expander("Browser Session Setup", expanded=False):
            browser_status = get_browser_provider_status()
            rows = []
            for platform in LIVE_COMPARISON_PLATFORMS:
                details = browser_status[platform]
                rows.append(
                    {
                        "Platform": platform,
                        "Playwright": "Yes" if details["playwright_installed"] else "No",
                        "Saved Session": "Yes" if details["session_saved"] else "No",
                        "Search URL": "Yes" if details["search_url_configured"] else "No",
                        "Selectors": "Yes" if details["selectors_configured"] else "No",
                    }
                )
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.info("Amazon is the strongest live provider right now. Flipkart is enabled too, but some staple grocery searches may still be sparse.")

    quick1, quick2 = st.columns(2)
    with quick1:
        if st.button("Add Item", width="stretch"):
            next_index = st.session_state["item_count"]
            st.session_state["item_count"] += 1
            keys = row_keys(next_index)
            st.session_state[keys["name"]] = ""
            st.session_state[keys["pack"]] = "1 pcs"
            st.session_state[keys["count"]] = 1
            st.rerun()
    with quick2:
        if st.button("Remove Last", width="stretch", disabled=st.session_state["item_count"] <= 1):
            last_index = st.session_state["item_count"] - 1
            keys = row_keys(last_index)
            clear_match_state(last_index)
            st.session_state.pop(keys["name"], None)
            st.session_state.pop(keys["pack"], None)
            st.session_state.pop(keys["count"], None)
            st.session_state["item_count"] -= 1
            st.rerun()

    if data_mode == "mock":
        preset1, preset2 = st.columns([1.4, 1])
        with preset1:
            selected_preset = st.selectbox("Preset Basket", list(PRESET_BASKETS.keys()))
        with preset2:
            if st.button("Load Preset", width="stretch"):
                load_preset_basket(selected_preset)
                st.rerun()

    st.markdown("#### Products")
    for index in range(st.session_state["item_count"]):
        sync_row_state(index)
        keys = row_keys(index)
        current_name = st.session_state.get(keys["name"], "")
        quantity_options = get_quantity_options(current_name)
        st.session_state.setdefault(keys["pack"], quantity_options[0])
        if st.session_state[keys["pack"]] not in quantity_options:
            st.session_state[keys["pack"]] = quantity_options[0]

        col1, col2, col3, col4 = st.columns([3, 1.5, 1, 1.1])
        with col1:
            st.text_input(f"Product {index + 1}", key=keys["name"], placeholder="Enter product name")
        latest_name = st.session_state.get(keys["name"], "").strip()
        quantity_options = get_quantity_options(latest_name)
        if st.session_state.get(keys["pack"], quantity_options[0]) not in quantity_options:
            st.session_state[keys["pack"]] = quantity_options[0]
        with col2:
            st.selectbox(f"Pack Size {index + 1}", options=quantity_options, key=keys["pack"])
        with col3:
            st.selectbox(f"Count {index + 1}", options=list(range(1, 21)), key=keys["count"])
        with col4:
            find_clicked = st.button(f"Find Matches {index + 1}", key=f"find_matches_{index}", width="stretch", disabled=not latest_name)

        if find_clicked and latest_name:
            if pincode_error:
                st.error(pincode_error)
            else:
                options, warnings = collect_product_options(latest_name, pincode, data_mode)
                queue_state_updates(
                    {
                        keys["options"]: options,
                        keys["warnings"]: warnings,
                        keys["searched_name"]: latest_name,
                        keys["selected"]: options[0]["name"] if options else "",
                    }
                )
                st.rerun()

        current_options = st.session_state.get(keys["options"], [])
        searched_name = st.session_state.get(keys["searched_name"], "")
        option_warnings = st.session_state.get(keys["warnings"], [])

        if latest_name and searched_name == latest_name:
            with st.expander(f"Match Picker For Item {index + 1}", expanded=True):
                if current_options:
                    st.success(f"Found {len(current_options)} matches for '{latest_name}'.")
                    for option_position, option in enumerate(current_options):
                        card_col1, card_col2 = st.columns([4.6, 1.4])
                        with card_col1:
                            st.markdown(
                                f"""
                                <div class="match-card">
                                    <div class="match-card-title">{option["name"]}</div>
                                    <div class="match-card-meta">Brand: {option["brand"]} | Category: {option["category"]}</div>
                                    <div class="match-card-meta">Platforms: {", ".join(option["platforms"])}</div>
                                    <div class="match-card-meta">Source: {"Live portal" if option.get("source") == "live" else "Demo suggestion"}</div>
                                    <div class="match-card-price">Starts at {format_currency(option["price"])}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        with card_col2:
                            if st.button(
                                f"Use This Match {index + 1}-{option_position + 1}",
                                key=f"use_match_{index}_{option_position}",
                                width="stretch",
                            ):
                                selected_name = option["name"]
                                selected_compare = option["compare_name"]
                                selected_source = option.get("source", "mock")
                                clear_match_state(index)
                                queue_state_updates(
                                    {
                                        keys["name"]: selected_name,
                                        keys["compare"]: selected_compare,
                                        keys["compare_display"]: selected_name,
                                        keys["source"]: selected_source,
                                    }
                                )
                                st.rerun()

                    if st.button(f"Clear Matches {index + 1}", key=f"clear_matches_{index}", width="stretch"):
                        clear_match_state(index)
                        st.rerun()
                else:
                    message = f"No live matches were found for '{latest_name}'." if data_mode == "live" else f"No matches were found for '{latest_name}'."
                    st.warning(message)

                for warning in option_warnings:
                    st.caption(warning)

    action1, action2 = st.columns([1, 2.4])
    with action1:
        if st.button("Reset Basket", width="stretch"):
            if data_mode == "live":
                set_empty_live_basket()
            else:
                set_default_mock_basket()
            st.rerun()
    with action2:
        compare_clicked = st.button("Compare Basket Now", width="stretch")

product_requests = build_product_requests()
should_compare = compare_clicked or (auto_compare and bool(product_requests))

if not product_requests:
    st.info("Add at least one product to start comparing baskets.")

if should_compare and pincode_error:
    st.error(pincode_error)

if should_compare and product_requests and not pincode_error:
    using_demo_selection = data_mode == "live" and any(request.get("source") == "mock" for request in product_requests)
    compare_mode = data_mode
    compare_requests = product_requests

    if using_demo_selection:
        st.info("Some selected items came from demo suggestions, so live comparison is trying the typed product names directly against Amazon and Flipkart.")
        compare_requests = prepare_requests_for_live_compare(product_requests)

    if data_mode == "live":
        config_status = get_live_configuration_status()
        configured = [platform for platform in LIVE_COMPARISON_PLATFORMS if config_status.get(platform, {}).get("configured")]
        if configured:
            st.info("Live mode is active for: " + ", ".join(configured))
        else:
            st.error("Live mode is selected, but Amazon and Flipkart are not configured for live search yet.")

    selected_platforms = LIVE_COMPARISON_PLATFORMS if compare_mode == "live" else None
    catalogs, provider_warnings = get_catalogs(
        compare_requests,
        pincode,
        compare_mode,
        selected_platforms=selected_platforms,
        fallback_to_mock_on_live_failure=(compare_mode != "live"),
    )
    for warning in provider_warnings:
        st.caption(warning)

    matched_items, totals = compare_product_list(compare_requests, catalogs=catalogs)
    optimized_items, total_optimized_cost = optimize_basket(compare_requests, catalogs=catalogs)
    optimized_split_items, optimized_split_summary = optimize_split_basket(compare_requests, catalogs=catalogs)

    if matched_items:
        recommended_row = get_recommended_platform(totals, len(compare_requests), recommendation_mode)
        comparison_df = pd.DataFrame(totals)[
            ["Platform", "Subtotal", "Delivery Fee", "Discount", "Final Payable", "Items Found", "Delivery", "Savings"]
        ].sort_values(by=["Items Found", "Final Payable"], ascending=[False, True]).reset_index(drop=True)

        render_platform_cards(comparison_df.to_dict("records"), recommended_row)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Basket Items", len(compare_requests), f"{sum(item['item_count'] for item in compare_requests)} units")
        m2.metric("Compared Platforms", len(comparison_df))
        m3.metric("Optimized Item Total", format_currency(total_optimized_cost))
        m4.metric("Recommendation", recommended_row["Platform"] if recommended_row else "N/A")

        overview_tab, plan_tab, details_tab = st.tabs(["Overview", "Basket Plans", "Item Details"])

        with overview_tab:
            chart_df = comparison_df.set_index("Platform")[["Final Payable"]]
            st.bar_chart(chart_df)
            display_df = comparison_df.copy()
            for column in ["Subtotal", "Delivery Fee", "Discount", "Final Payable", "Savings"]:
                display_df[column] = display_df[column].apply(format_currency)
            st.dataframe(display_df, width="stretch", hide_index=True)

        with plan_tab:
            left, right = st.columns(2)
            with left:
                st.subheader("Optimized Item-by-Item Basket")
                optimized_df = pd.DataFrame(optimized_items)[["Product", "Platform", "Quantity Label", "Item Count", "Item Total"]]
                optimized_df["Item Total"] = optimized_df["Item Total"].apply(format_currency)
                st.dataframe(optimized_df, width="stretch", hide_index=True)
            with right:
                st.subheader("Split Basket Summary")
                if optimized_split_items:
                    split_df = pd.DataFrame(optimized_split_items)[["Requested Product", "Matched Product", "Platform", "Item Total", "Delivery"]]
                    split_df["Item Total"] = split_df["Item Total"].apply(format_currency)
                    st.dataframe(split_df, width="stretch", hide_index=True)
                    st.metric("Split Basket Final Payable", format_currency(optimized_split_summary["Final Payable"]))
                else:
                    st.info("A split basket plan is not available for this basket.")

        with details_tab:
            item_df = pd.DataFrame(matched_items)[["Platform", "Requested Product", "Matched Product", "Unit Price", "Quantity Label", "Item Count", "Item Total", "Delivery"]]
            item_df["Unit Price"] = item_df["Unit Price"].apply(format_currency)
            item_df["Item Total"] = item_df["Item Total"].apply(format_currency)
            st.dataframe(item_df, width="stretch", hide_index=True)
    else:
        if data_mode == "live":
            st.warning("No products were found for the current live basket. Try Find Matches again, adjust the product name, or switch to Mock Catalog.")
        else:
            st.warning("No products were found for the current basket.")
