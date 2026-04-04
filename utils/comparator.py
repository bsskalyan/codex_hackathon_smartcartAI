import json
import re

from utils.matcher import match_product, product_similarity


SOURCES = {
    "Blinkit": "data/blinkit.json",
    "Instamart": "data/instamart.json",
    "Amazon": "data/amazon.json",
    "Dmart": "data/dmart.json",
    "Zepto": "data/zetpo.json",
}

PLATFORM_CHARGES = {
    "Blinkit": {"delivery_fee": 15, "discount": 10},
    "Instamart": {"delivery_fee": 18, "discount": 12},
    "Amazon": {"delivery_fee": 25, "discount": 5},
    "Dmart": {"delivery_fee": 10, "discount": 7},
    "Zepto": {"delivery_fee": 14, "discount": 8},
}

WEIGHT_KEYWORDS = {"sugar", "rice", "dal", "atta", "salt", "flour", "paneer", "curd", "butter", "cheese", "tea", "coffee"}
LITRE_KEYWORDS = {"milk", "oil", "juice"}


def load_data(file):
    with open(file, "r") as f:
        return json.load(f)


def get_catalogs_for_comparison(catalogs=None):
    if catalogs is not None:
        return catalogs

    loaded_catalogs = {}
    for platform, path in SOURCES.items():
        loaded_catalogs[platform] = load_data(path)
    return loaded_catalogs


def infer_quantity_unit(product_name):
    normalized_name = product_name.lower()

    if any(keyword in normalized_name for keyword in WEIGHT_KEYWORDS):
        return "kg"

    if any(keyword in normalized_name for keyword in LITRE_KEYWORDS):
        return "litre"

    return "pcs"


def format_quantity_label(product_name, quantity):
    return f"{quantity} {infer_quantity_unit(product_name)}"


def get_quantity_options(product_name):
    unit = infer_quantity_unit(product_name)

    if unit == "kg":
        return ["100 g", "250 g", "500 g", "1 kg", "2 kg", "5 kg"]

    if unit == "litre":
        return ["250 ml", "500 ml", "1 litre", "2 litre", "5 litre"]

    return [f"{count} pcs" for count in range(1, 21)]


def parse_quantity_choice(quantity_choice):
    amount_text, unit = quantity_choice.split(" ", 1)
    amount = float(amount_text)
    normalized_unit = unit.strip().lower()

    if normalized_unit == "g":
        return amount / 1000, "kg"

    if normalized_unit == "ml":
        return amount / 1000, "litre"

    return amount, normalized_unit


def extract_pack_size(product_name, default_unit):
    normalized_name = product_name.lower()

    unit_match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|litre|l|ml)\b", normalized_name)
    if unit_match:
        amount = float(unit_match.group(1))
        unit = unit_match.group(2)

        if unit == "g":
            return amount / 1000, "kg"
        if unit == "ml":
            return amount / 1000, "litre"
        if unit == "l":
            return amount, "litre"

        return amount, unit

    pack_match = re.search(r"(\d+)\s*pack\b", normalized_name)
    if pack_match:
        return float(pack_match.group(1)), "pcs"

    return 1.0, default_unit


def calculate_item_total(price, requested_amount, requested_unit, matched_product_name):
    pack_amount, pack_unit = extract_pack_size(matched_product_name, requested_unit)

    if requested_unit == pack_unit and pack_amount > 0:
        return round(price * (requested_amount / pack_amount), 2)

    return round(price * requested_amount, 2)


def delivery_to_minutes(delivery_text):
    text = delivery_text.lower().strip()

    minute_match = re.search(r"(\d+)\s*min", text)
    if minute_match:
        return int(minute_match.group(1))

    hour_match = re.search(r"(\d+)\s*hour", text)
    if hour_match:
        return int(hour_match.group(1)) * 60

    day_match = re.search(r"(\d+)\s*day", text)
    if day_match:
        return int(day_match.group(1)) * 24 * 60

    return 99999


def find_best_match(products, requested_product):
    scored_matches = []

    for item in products:
        if match_product(requested_product, item["name"]):
            scored_matches.append(
                (
                    product_similarity(requested_product, item["name"]),
                    item,
                )
            )

    if not scored_matches:
        return None

    scored_matches.sort(key=lambda entry: (-entry[0], entry[1]["price"]))
    return scored_matches[0][1]


def compare_products(product_name, catalogs=None):
    results = []
    available_catalogs = get_catalogs_for_comparison(catalogs)

    for platform, products in available_catalogs.items():
        best_match = find_best_match(products, product_name)

        if best_match:
            results.append(
                {
                    "Platform": platform,
                    "Product": best_match["name"],
                    "Price": best_match["price"],
                    "Delivery": best_match["delivery"],
                }
            )

    return sorted(results, key=lambda row: row["Price"])


def compare_product_list(product_requests, catalogs=None):
    matched_items = []
    platform_totals = []
    available_catalogs = get_catalogs_for_comparison(catalogs)

    for platform, products in available_catalogs.items():
        subtotal = 0
        items_found = 0
        delivery = "-"

        for request in product_requests:
            requested_product = request["name"]
            quantity = request["quantity"]
            quantity_unit = request["quantity_unit"]
            quantity_label = request["quantity_label"]
            item_count = request.get("item_count", 1)
            best_match = find_best_match(products, requested_product)

            if best_match:
                pack_total = calculate_item_total(
                    best_match["price"],
                    quantity,
                    quantity_unit,
                    best_match["name"],
                )
                item_total = round(pack_total * item_count, 2)
                matched_items.append(
                    {
                        "Platform": platform,
                        "Requested Product": requested_product,
                        "Matched Product": best_match["name"],
                        "Unit Price": best_match["price"],
                        "Quantity": quantity,
                        "Quantity Label": quantity_label,
                        "Item Count": item_count,
                        "Item Total": item_total,
                        "Delivery": best_match["delivery"],
                    }
                )
                subtotal += item_total
                items_found += 1
                delivery = best_match["delivery"]

        charges = PLATFORM_CHARGES.get(platform, {"delivery_fee": 0, "discount": 0})
        delivery_fee = charges["delivery_fee"] if items_found else 0
        discount = charges["discount"] if items_found else 0
        final_payable = max(subtotal + delivery_fee - discount, 0)

        platform_totals.append(
            {
                "Platform": platform,
                "Subtotal": subtotal,
                "Delivery Fee": delivery_fee,
                "Discount": discount,
                "Final Payable": final_payable,
                "Total Price": final_payable,
                "Items Found": items_found,
                "Delivery": delivery,
                "Delivery Minutes": delivery_to_minutes(delivery),
                "Matched Items": matched_items_for_platform(matched_items, platform),
            }
        )

    complete_platforms = [
        row for row in platform_totals if row["Items Found"] == len(product_requests)
    ]

    best_total = 0
    highest_total = 0

    if complete_platforms:
        best_total = min(row["Final Payable"] for row in complete_platforms)
        highest_total = max(row["Final Payable"] for row in complete_platforms)

    for row in platform_totals:
        is_complete = row["Items Found"] == len(product_requests)
        row["Best"] = "Best" if complete_platforms and row["Final Payable"] == best_total and is_complete else ""
        row["Savings"] = highest_total - row["Final Payable"] if is_complete else 0
        row["Recommendation Score"] = row["Final Payable"] + row["Delivery Minutes"]

    recommended_platform = None
    if complete_platforms:
        recommended_platform = min(
            complete_platforms,
            key=lambda row: (row["Recommendation Score"], row["Total Price"])
        )["Platform"]

    for row in platform_totals:
        row["Recommended"] = "Recommended" if row["Platform"] == recommended_platform else ""

    platform_totals.sort(
        key=lambda row: (row["Items Found"] != len(product_requests), row["Final Payable"])
    )

    return matched_items, platform_totals


def get_recommended_platform(totals, item_count, recommendation_mode):
    complete_totals = [row for row in totals if row["Items Found"] == item_count]

    if not complete_totals:
        return None

    if recommendation_mode == "Cheapest":
        return min(complete_totals, key=lambda row: row["Final Payable"])

    if recommendation_mode == "Fastest":
        return min(
            complete_totals,
            key=lambda row: (row["Delivery Minutes"], row["Final Payable"]),
        )

    return min(
        complete_totals,
        key=lambda row: (row["Recommendation Score"], row["Final Payable"]),
    )


def optimize_basket(product_list, catalogs=None):
    optimized_items = []
    total_optimized_cost = 0
    available_catalogs = get_catalogs_for_comparison(catalogs)

    for product_request in product_list:
        if isinstance(product_request, dict):
            product_name = product_request["name"]
            quantity = product_request["quantity"]
            quantity_unit = product_request["quantity_unit"]
            quantity_label = product_request["quantity_label"]
            item_count = product_request.get("item_count", 1)
        else:
            product_name = product_request
            quantity = 1
            quantity_unit = "pcs"
            quantity_label = "1 pcs"
            item_count = 1

        cheapest_item = None

        for platform, products in available_catalogs.items():
            best_match = find_best_match(products, product_name)

            if not best_match:
                continue

            item_option = {
                "Product": product_name,
                "Matched Product": best_match["name"],
                "Platform": platform,
                "Price": best_match["price"],
                "Quantity Label": quantity_label,
                "Item Count": item_count,
                "Item Total": round(
                    calculate_item_total(
                        best_match["price"],
                        quantity,
                        quantity_unit,
                        best_match["name"],
                    ) * item_count,
                    2,
                ),
                "Delivery": best_match["delivery"],
            }

            if cheapest_item is None or item_option["Item Total"] < cheapest_item["Item Total"]:
                cheapest_item = item_option

        if cheapest_item:
            optimized_items.append(cheapest_item)
            total_optimized_cost += cheapest_item["Item Total"]

    return optimized_items, total_optimized_cost


def optimize_split_basket(product_requests, catalogs=None):
    optimized_items = []
    optimized_subtotal = 0
    used_platforms = set()
    available_catalogs = get_catalogs_for_comparison(catalogs)

    for request in product_requests:
        requested_product = request["name"]
        quantity = request["quantity"]
        quantity_unit = request["quantity_unit"]
        quantity_label = request["quantity_label"]
        item_count = request.get("item_count", 1)
        cheapest_option = None

        for platform, products in available_catalogs.items():
            best_match = find_best_match(products, requested_product)

            if not best_match:
                continue

            option = {
                "Platform": platform,
                "Requested Product": requested_product,
                "Matched Product": best_match["name"],
                "Unit Price": best_match["price"],
                "Quantity": quantity,
                "Quantity Label": quantity_label,
                "Item Count": item_count,
                "Item Total": round(
                    calculate_item_total(
                        best_match["price"],
                        quantity,
                        quantity_unit,
                        best_match["name"],
                    ) * item_count,
                    2,
                ),
                "Delivery": best_match["delivery"],
            }

            if cheapest_option is None or option["Item Total"] < cheapest_option["Item Total"]:
                cheapest_option = option

        if cheapest_option:
            optimized_items.append(cheapest_option)
            optimized_subtotal += cheapest_option["Item Total"]
            used_platforms.add(cheapest_option["Platform"])

    total_delivery_fee = sum(PLATFORM_CHARGES[platform]["delivery_fee"] for platform in used_platforms)
    total_discount = sum(PLATFORM_CHARGES[platform]["discount"] for platform in used_platforms)
    final_payable = max(optimized_subtotal + total_delivery_fee - total_discount, 0)

    return optimized_items, {
        "Subtotal": optimized_subtotal,
        "Delivery Fee": total_delivery_fee,
        "Discount": total_discount,
        "Final Payable": final_payable,
    }


def matched_items_for_platform(matched_items, platform):
    return [
        item["Matched Product"]
        for item in matched_items
        if item["Platform"] == platform
    ]
