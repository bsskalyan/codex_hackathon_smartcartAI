import pandas as pd
import streamlit as st

from providers.catalog_provider import get_catalogs
from utils.comparator import (
    compare_product_list,
    get_quantity_options,
    get_recommended_platform,
    optimize_basket,
    optimize_split_basket,
    parse_quantity_choice,
)
from utils.env_loader import load_live_app_env


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


def initialize_state():
    if "item_count" not in st.session_state:
        st.session_state.item_count = 2

    defaults = [
        ("milk", "1 litre", 1),
        ("bread", "1 pcs", 2),
    ]
    for index, (name, pack_size, count) in enumerate(defaults):
        st.session_state.setdefault(f"product_name_{index}", name)
        st.session_state.setdefault(f"product_pack_size_{index}", pack_size)
        st.session_state.setdefault(f"product_count_{index}", count)


def clear_basket():
    current_items = st.session_state.get("item_count", 1)
    for index in range(current_items):
        st.session_state.pop(f"product_name_{index}", None)
        st.session_state.pop(f"product_pack_size_{index}", None)
        st.session_state.pop(f"product_count_{index}", None)

    st.session_state.item_count = 1
    st.session_state.product_name_0 = ""
    st.session_state.product_pack_size_0 = "1 pcs"
    st.session_state.product_count_0 = 1


def load_preset_basket(preset_name):
    preset_items = PRESET_BASKETS[preset_name]
    clear_basket()
    st.session_state.item_count = len(preset_items)

    for index, item in enumerate(preset_items):
        st.session_state[f"product_name_{index}"] = item["name"]
        st.session_state[f"product_pack_size_{index}"] = item["pack_size"]
        st.session_state[f"product_count_{index}"] = item["count"]


def build_product_requests(item_count):
    product_requests = []

    for index in range(item_count):
        name = st.session_state.get(f"product_name_{index}", "").strip()
        quantity_choice = st.session_state.get(f"product_pack_size_{index}", "1 pcs")
        selected_count = st.session_state.get(f"product_count_{index}", 1)

        if name:
            quantity_value, quantity_unit = parse_quantity_choice(quantity_choice)
            product_requests.append(
                {
                    "name": name,
                    "quantity": quantity_value,
                    "quantity_unit": quantity_unit,
                    "quantity_label": quantity_choice,
                    "item_count": selected_count,
                }
            )

    return product_requests


def format_currency(value):
    if float(value).is_integer():
        return f"Rs {int(value)}"
    return f"Rs {value:.2f}"


def inject_theme():
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(99, 102, 241, 0.18), transparent 30%),
                radial-gradient(circle at top right, rgba(45, 212, 191, 0.18), transparent 28%),
                radial-gradient(circle at bottom, rgba(56, 189, 248, 0.16), transparent 26%),
                linear-gradient(180deg, #f4f8ff 0%, #eef6fb 46%, #edf7f5 100%);
            color: #152538;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.78);
            border: 1px solid rgba(125, 145, 180, 0.18);
            border-radius: 20px;
            box-shadow: 0 18px 50px rgba(53, 92, 136, 0.08);
            backdrop-filter: blur(10px);
        }
        .hero-card {
            padding: 1.6rem 1.8rem;
            border-radius: 24px;
            background: linear-gradient(135deg, #243b53 0%, #355c7d 42%, #2a9d8f 100%);
            color: #f7fbff;
            box-shadow: 0 24px 60px rgba(36, 59, 83, 0.24);
            margin-bottom: 1rem;
        }
        .hero-card h1 {
            margin: 0;
            font-size: 2.4rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }
        .hero-card p {
            margin: 0.6rem 0 0;
            font-size: 1rem;
            max-width: 760px;
        }
        .pill-row {
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
            margin-top: 1rem;
        }
        .pill {
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 999px;
            padding: 0.45rem 0.8rem;
            font-size: 0.92rem;
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
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div {
            border-radius: 12px;
            border-color: rgba(125, 145, 180, 0.25);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.65);
            color: #35506b;
            border: 1px solid rgba(125, 145, 180, 0.14);
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #355c7d, #2a9d8f);
            color: #f7fbff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_platform_spotlights(totals, recommended_row, best_row):
    st.markdown("#### Platform Spotlight")
    spotlight_columns = st.columns(min(len(totals), 5))

    for index, row in enumerate(totals[:5]):
        badge = "Recommended" if recommended_row and row["Platform"] == recommended_row["Platform"] else "In Play"
        if best_row and row["Platform"] == best_row["Platform"]:
            badge = "Lowest Full Basket"

        spotlight_columns[index].markdown(
            f"""
            <div style="padding: 1rem; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(238,246,251,0.94)); border: 1px solid rgba(125, 145, 180, 0.16); min-height: 145px; box-shadow: 0 14px 30px rgba(53, 92, 125, 0.06);">
                <div style="font-size: 0.82rem; color: #6b7c93;">{badge}</div>
                <div style="font-size: 1.25rem; font-weight: 800; color: #18324a; margin-top: 0.2rem;">{row["Platform"]}</div>
                <div style="font-size: 1.1rem; font-weight: 700; color: #2a9d8f; margin-top: 0.5rem;">{format_currency(row["Final Payable"])} </div>
                <div style="font-size: 0.9rem; color: #486581; margin-top: 0.35rem;">{row["Items Found"]} items found</div>
                <div style="font-size: 0.9rem; color: #486581;">ETA: {row["Delivery"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


load_live_app_env()

st.set_page_config(page_title="SmartCart AI", page_icon=":shopping_trolley:", layout="wide")
initialize_state()
inject_theme()

st.markdown(
    """
    <div class="hero-card">
        <h1>SmartCart AI</h1>
        <p>Build a grocery basket, compare platforms in real time, and see whether one store or a split order wins on price and convenience.</p>
        <div class="pill-row">
            <span class="pill">Live basket updates</span>
            <span class="pill">Colorful comparison dashboard</span>
            <span class="pill">Split-order recommendations</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="section-note">
        Change products, pack sizes, filters, and recommendation mode to see the dashboard react instantly. Use a preset basket if you want something interactive to try right away.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.subheader("Basket Builder")
    top_col1, top_col2, top_col3, top_col4 = st.columns([1.1, 1.1, 1, 1])

    with top_col1:
        pincode = st.text_input("Pincode", placeholder="Enter delivery pincode")

    with top_col2:
        recommendation_mode = st.selectbox(
            "Recommendation Mode",
            ["Cheapest", "Fastest", "Best Value"],
        )

    with top_col3:
        data_mode = st.selectbox(
            "Data Source",
            ["mock", "live"],
            format_func=lambda value: "Mock Catalog" if value == "mock" else "Live Portals",
        )

    with top_col4:
        auto_compare = st.toggle("Auto Compare", value=True)

    quick_col1, quick_col2 = st.columns([1, 1])
    with quick_col1:
        if st.button("Add Item", use_container_width=True):
            next_index = st.session_state.item_count
            st.session_state.item_count += 1
            st.session_state[f"product_name_{next_index}"] = ""
            st.session_state[f"product_pack_size_{next_index}"] = "1 pcs"
            st.session_state[f"product_count_{next_index}"] = 1
            st.rerun()

    with quick_col2:
        remove_disabled = st.session_state.item_count <= 1
        if st.button("Remove Last", use_container_width=True, disabled=remove_disabled):
            last_index = st.session_state.item_count - 1
            st.session_state.pop(f"product_name_{last_index}", None)
            st.session_state.pop(f"product_pack_size_{last_index}", None)
            st.session_state.pop(f"product_count_{last_index}", None)
            st.session_state.item_count -= 1
            st.rerun()

    if data_mode == "mock":
        preset_col1, preset_col2 = st.columns([1.4, 1])
        with preset_col1:
            selected_preset = st.selectbox("Preset Basket", list(PRESET_BASKETS.keys()))

        with preset_col2:
            if st.button("Load Preset", use_container_width=True):
                load_preset_basket(selected_preset)
                st.rerun()

    st.markdown("#### Products")
    for index in range(st.session_state.item_count):
        row_col1, row_col2, row_col3 = st.columns([3, 1.5, 1])
        current_name = st.session_state.get(f"product_name_{index}", "")
        quantity_options = get_quantity_options(current_name)
        current_choice = st.session_state.get(f"product_pack_size_{index}", quantity_options[0])

        if current_choice not in quantity_options:
            st.session_state[f"product_pack_size_{index}"] = quantity_options[0]

        with row_col1:
            st.text_input(
                f"Product {index + 1}",
                key=f"product_name_{index}",
                placeholder="Enter product name",
            )

        with row_col2:
            st.selectbox(
                f"Pack Size {index + 1}",
                options=quantity_options,
                key=f"product_pack_size_{index}",
            )

        with row_col3:
            st.selectbox(
                f"Count {index + 1}",
                options=list(range(1, 21)),
                key=f"product_count_{index}",
            )

    action_col1, action_col2 = st.columns([1, 2.4])
    with action_col1:
        if st.button("Reset Basket", use_container_width=True):
            clear_basket()
            st.rerun()
    with action_col2:
        compare_clicked = st.button("Compare Basket Now", use_container_width=True)

product_requests = build_product_requests(st.session_state.item_count)
should_compare = compare_clicked or (auto_compare and bool(product_requests))

if not product_requests:
    st.info("Add at least one product to start comparing baskets.")

if should_compare and product_requests:
    catalogs, provider_warnings = get_catalogs(product_requests, pincode, data_mode)

    if data_mode == "live":
        st.info("Live mode is enabled. Platforms without configured endpoints automatically fall back to mock catalog data.")

    for warning in provider_warnings:
        st.caption(warning)

    matched_items, totals = compare_product_list(product_requests, catalogs=catalogs)
    optimized_split_items, optimized_split_summary = optimize_split_basket(product_requests, catalogs=catalogs)
    optimized_items, total_optimized_cost = optimize_basket(product_requests, catalogs=catalogs)

    if matched_items:
        recommended_row = get_recommended_platform(
            totals,
            len(product_requests),
            recommendation_mode,
        )
        best_row = next((row for row in totals if row["Best"] == "Best"), None)

        for row in totals:
            row["Recommended"] = (
                recommendation_mode
                if recommended_row and row["Platform"] == recommended_row["Platform"]
                else ""
            )

        comparison_df = pd.DataFrame(totals)[
            [
                "Platform",
                "Subtotal",
                "Delivery Fee",
                "Discount",
                "Final Payable",
                "Items Found",
                "Delivery",
                "Best",
                "Recommended",
                "Savings",
            ]
        ]
        comparison_df = comparison_df.sort_values(
            by=["Items Found", "Final Payable"],
            ascending=[False, True],
        ).reset_index(drop=True)

        render_platform_spotlights(comparison_df.to_dict("records"), recommended_row, best_row)

        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
        with summary_col1:
            st.metric(
                "Basket Items",
                len(product_requests),
                f"{sum(request['item_count'] for request in product_requests)} units",
            )
        with summary_col2:
            if best_row:
                st.metric("Best Price", format_currency(best_row["Final Payable"]))
            else:
                st.metric("Best Price", "N/A")
        with summary_col3:
            if recommended_row:
                st.metric("Recommended", recommended_row["Platform"], recommended_row["Delivery"])
            else:
                st.metric("Recommended", "N/A")
        with summary_col4:
            if best_row:
                savings = best_row["Final Payable"] - total_optimized_cost
                st.metric("Potential Item Savings", format_currency(max(savings, 0)))
            else:
                st.metric("Potential Item Savings", format_currency(0))

        if recommended_row:
            st.success(
                f"Recommended for {recommendation_mode.lower()}: {recommended_row['Platform']} at "
                f"{format_currency(recommended_row['Final Payable'])} with {recommended_row['Delivery']} delivery."
            )

        overview_tab, plan_tab, details_tab = st.tabs(
            ["Overview", "Basket Plans", "Item Details"]
        )

        with overview_tab:
            platform_options = comparison_df["Platform"].tolist()
            selected_platforms = st.multiselect(
                "Focus Platforms",
                options=platform_options,
                default=platform_options,
            )
            filtered_df = comparison_df[comparison_df["Platform"].isin(selected_platforms)].copy()

            if filtered_df.empty:
                st.warning("Select at least one platform to view the comparison.")
            else:
                chart_df = filtered_df.set_index("Platform")[["Final Payable"]]
                st.bar_chart(chart_df)

                display_df = filtered_df.copy()
                display_df["Subtotal"] = display_df["Subtotal"].apply(format_currency)
                display_df["Delivery Fee"] = display_df["Delivery Fee"].apply(format_currency)
                display_df["Discount"] = display_df["Discount"].apply(format_currency)
                display_df["Final Payable"] = display_df["Final Payable"].apply(format_currency)
                display_df["Savings"] = display_df["Savings"].apply(format_currency)
                st.dataframe(display_df, use_container_width=True, hide_index=True)

        with plan_tab:
            plan_col1, plan_col2 = st.columns(2)

            with plan_col1:
                st.subheader("Optimized Item-by-Item Basket")
                optimized_df = pd.DataFrame(optimized_items)[
                    ["Product", "Platform", "Quantity Label", "Item Count", "Item Total"]
                ]
                optimized_df["Item Total"] = optimized_df["Item Total"].apply(format_currency)
                st.dataframe(optimized_df, use_container_width=True, hide_index=True)
                st.metric("Optimized Item Subtotal", format_currency(total_optimized_cost))

            with plan_col2:
                st.subheader("Split Basket Summary")
                if optimized_split_items:
                    split_item_df = pd.DataFrame(optimized_split_items)[
                        [
                            "Requested Product",
                            "Matched Product",
                            "Platform",
                            "Unit Price",
                            "Quantity Label",
                            "Item Count",
                            "Item Total",
                            "Delivery",
                        ]
                    ]
                    split_item_df["Unit Price"] = split_item_df["Unit Price"].apply(format_currency)
                    split_item_df["Item Total"] = split_item_df["Item Total"].apply(format_currency)
                    st.dataframe(split_item_df, use_container_width=True, hide_index=True)

                    split_metric_col1, split_metric_col2 = st.columns(2)
                    split_metric_col3, split_metric_col4 = st.columns(2)
                    split_metric_col1.metric("Subtotal", format_currency(optimized_split_summary["Subtotal"]))
                    split_metric_col2.metric("Delivery Fee", format_currency(optimized_split_summary["Delivery Fee"]))
                    split_metric_col3.metric("Discount", format_currency(optimized_split_summary["Discount"]))
                    split_metric_col4.metric("Final Payable", format_currency(optimized_split_summary["Final Payable"]))
                else:
                    st.info("A split basket plan is not available for this selection yet.")

            st.subheader("Final Suggestion")
            if best_row and optimized_split_items:
                best_platform_price = best_row["Final Payable"]
                split_basket_price = optimized_split_summary["Final Payable"]

                if split_basket_price < best_platform_price:
                    difference = best_platform_price - split_basket_price
                    st.success(
                        f"Split Basket wins at {format_currency(split_basket_price)}, saving "
                        f"{format_currency(difference)} compared with buying everything from {best_row['Platform']}."
                    )
                elif split_basket_price > best_platform_price:
                    difference = split_basket_price - best_platform_price
                    st.info(
                        f"{best_row['Platform']} is better for the full cart at {format_currency(best_platform_price)}, "
                        f"which is {format_currency(difference)} cheaper than splitting the order."
                    )
                else:
                    st.info(
                        f"Both approaches land at {format_currency(best_platform_price)}. Choose "
                        f"{best_row['Platform']} for convenience or split the basket for flexible sourcing."
                    )
            elif best_row:
                st.info(
                    f"{best_row['Platform']} has the lowest complete basket price at "
                    f"{format_currency(best_row['Final Payable'])}."
                )
            elif optimized_split_items:
                st.info(
                    f"No single platform has every requested product, so the split basket is the best available plan at "
                    f"{format_currency(optimized_split_summary['Final Payable'])}."
                )

        with details_tab:
            st.subheader("Matched Item Price Details")
            item_df = pd.DataFrame(matched_items)[
                [
                    "Platform",
                    "Requested Product",
                    "Matched Product",
                    "Unit Price",
                    "Quantity Label",
                    "Item Count",
                    "Item Total",
                    "Delivery",
                ]
            ]
            item_df = item_df.sort_values(by=["Platform", "Requested Product"]).reset_index(drop=True)
            item_df["Unit Price"] = item_df["Unit Price"].apply(format_currency)
            item_df["Item Total"] = item_df["Item Total"].apply(format_currency)
            st.dataframe(item_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No products were found for the current basket.")


