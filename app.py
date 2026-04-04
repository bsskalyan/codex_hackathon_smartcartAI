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


def build_product_requests(item_count):
    product_requests = []

    for index in range(item_count):
        name = st.session_state.get(f"product_name_{index}", "").strip()
        quantity_choice = st.session_state.get(f"product_pack_size_{index}", "1 pcs")
        item_count = st.session_state.get(f"product_count_{index}", 1)

        if name:
            quantity_value, quantity_unit = parse_quantity_choice(quantity_choice)
            product_requests.append(
                {
                    "name": name,
                    "quantity": quantity_value,
                    "quantity_unit": quantity_unit,
                    "quantity_label": quantity_choice,
                    "item_count": item_count,
                }
            )

    return product_requests


def format_currency(value):
    if float(value).is_integer():
        return f"Rs {int(value)}"
    return f"Rs {value:.2f}"


if "item_count" not in st.session_state:
    st.session_state.item_count = 1

load_live_app_env()


st.set_page_config(page_title="SmartCart AI", page_icon="🛒", layout="wide")

st.title("🛒 SmartCart AI")
st.caption("Compare basket prices and find the smartest way to buy your cart.")

with st.container(border=True):
    st.subheader("🧾 Basket Input")
    top_col1, top_col2, top_col3 = st.columns(3)

    with top_col1:
        pincode = st.text_input("Pincode")

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

    st.markdown("#### Products")
    for index in range(st.session_state.item_count):
        row_col1, row_col2, row_col3 = st.columns([3, 1.4, 1])
        current_name = st.session_state.get(f"product_name_{index}", "")
        quantity_options = get_quantity_options(current_name)

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

    add_col, search_col = st.columns([1, 2])
    with add_col:
        if st.button("➕ Add Item", use_container_width=True):
            st.session_state.item_count += 1
            st.rerun()
    with search_col:
        search_clicked = st.button("🔎 Compare Basket", use_container_width=True)

if search_clicked:
    product_requests = build_product_requests(st.session_state.item_count)

    if not product_requests:
        st.warning("⚠️ Please enter at least one product.")
    else:
        catalogs, provider_warnings = get_catalogs(product_requests, pincode, data_mode)

        if data_mode == "live":
            st.info("Live mode is enabled. Platforms without configured live endpoints will fall back to mock data.")

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

            st.subheader("📊 Platform Comparison")
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
            comparison_df["Subtotal"] = comparison_df["Subtotal"].apply(format_currency)
            comparison_df["Delivery Fee"] = comparison_df["Delivery Fee"].apply(format_currency)
            comparison_df["Discount"] = comparison_df["Discount"].apply(format_currency)
            comparison_df["Final Payable"] = comparison_df["Final Payable"].apply(format_currency)
            comparison_df["Savings"] = comparison_df["Savings"].apply(format_currency)
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)

            summary_col1, summary_col2, summary_col3 = st.columns(3)

            with summary_col1:
                if best_row:
                    st.metric("Best Price", format_currency(best_row["Final Payable"]))
                else:
                    st.metric("Best Price", "N/A")

            with summary_col2:
                if best_row:
                    st.metric(
                        "Best Single Platform",
                        f"{best_row['Platform']}",
                        format_currency(best_row["Final Payable"]),
                    )
                else:
                    st.metric("Best Single Platform", "N/A")

            with summary_col3:
                if best_row:
                    cheapest_single_platform_total = best_row["Final Payable"]
                    savings = cheapest_single_platform_total - total_optimized_cost
                    st.metric("Savings", format_currency(max(savings, 0)))
                else:
                    st.metric("Savings", format_currency(0))

            if recommended_row:
                st.success(
                    f"⭐ Recommended ({recommendation_mode}): "
                    f"{recommended_row['Platform']} | {format_currency(recommended_row['Final Payable'])} | {recommended_row['Delivery']}"
                )

            if best_row:
                cheapest_single_platform_total = best_row["Final Payable"]
                savings = cheapest_single_platform_total - total_optimized_cost

                if savings > 0:
                    st.success(f"You saved ₹{savings}")
                elif savings == 0:
                    st.info("No savings from basket optimization.")
                else:
                    st.warning(
                        f"Optimized basket costs ₹{abs(savings)} more than the cheapest single-platform option."
                    )
            else:
                st.warning("⚠️ No single platform has all requested products, so savings cannot be calculated.")

            st.subheader("🧠 Optimized Basket Plan")
            optimized_df = pd.DataFrame(optimized_items)[["Product", "Platform", "Quantity Label", "Item Count", "Item Total"]]
            optimized_df["Item Total"] = optimized_df["Item Total"].apply(format_currency)
            st.dataframe(optimized_df, use_container_width=True, hide_index=True)

            st.subheader("🛍️ Item Price Details")
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

            if optimized_split_items:
                st.subheader("🚚 Split Basket Summary")
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
                split_item_df = split_item_df.sort_values(by=["Platform", "Requested Product"]).reset_index(drop=True)
                split_item_df["Unit Price"] = split_item_df["Unit Price"].apply(format_currency)
                split_item_df["Item Total"] = split_item_df["Item Total"].apply(format_currency)
                st.dataframe(split_item_df, use_container_width=True, hide_index=True)

                split_platform_df = (
                    pd.DataFrame(optimized_split_items)
                    .groupby("Platform", as_index=False)
                    .agg(
                        Products=("Requested Product", lambda values: ", ".join(values)),
                        Subtotal=("Item Total", "sum"),
                    )
                )
                split_platform_df["Delivery Fee"] = split_platform_df["Platform"].apply(
                    lambda platform: format_currency(
                        next(row["Delivery Fee"] for row in totals if row["Platform"] == platform)
                    )
                )
                split_platform_df["Discount"] = split_platform_df["Platform"].apply(
                    lambda platform: format_currency(
                        next(row["Discount"] for row in totals if row["Platform"] == platform)
                    )
                )
                split_platform_df["Subtotal"] = split_platform_df["Subtotal"].apply(format_currency)

                st.caption("How the split basket is calculated across platforms")
                st.dataframe(split_platform_df, use_container_width=True, hide_index=True)

                split_col1, split_col2, split_col3, split_col4 = st.columns(4)
                split_col1.metric("Subtotal", format_currency(optimized_split_summary["Subtotal"]))
                split_col2.metric("Delivery Fee", format_currency(optimized_split_summary["Delivery Fee"]))
                split_col3.metric("Discount", format_currency(optimized_split_summary["Discount"]))
                split_col4.metric("Final Payable", format_currency(optimized_split_summary["Final Payable"]))

            st.subheader("✅ Final Suggestion")
            if best_row and optimized_split_items:
                best_platform_price = best_row["Final Payable"]
                split_basket_price = optimized_split_summary["Final Payable"]

                if split_basket_price < best_platform_price:
                    difference = best_platform_price - split_basket_price
                    st.success(
                        f"Split Basket is the best option because it costs {format_currency(split_basket_price)}, "
                        f"which is {format_currency(difference)} cheaper than buying everything from {best_row['Platform']}."
                    )
                elif split_basket_price > best_platform_price:
                    difference = split_basket_price - best_platform_price
                    st.info(
                        f"{best_row['Platform']} is the best option because its final payable is {format_currency(best_platform_price)}, "
                        f"which is {format_currency(difference)} cheaper than the split basket."
                    )
                else:
                    st.info(
                        f"Both options cost the same at {format_currency(best_platform_price)}. "
                        f"You can choose {best_row['Platform']} for convenience or the split basket if you prefer item-wise sourcing."
                    )
            elif best_row:
                st.info(
                    f"{best_row['Platform']} is the best option because it has the lowest complete basket price at "
                    f"{format_currency(best_row['Final Payable'])}."
                )
            elif optimized_split_items:
                st.info(
                    f"Split Basket is the best available option because no single platform has all requested products. "
                    f"Its final payable is {format_currency(optimized_split_summary['Final Payable'])}."
                )
        else:
            st.warning("🔍 No products found.")
