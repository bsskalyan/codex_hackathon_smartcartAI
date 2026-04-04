import datetime
import hashlib
import hmac
import json
import os

import requests


def _sign(key, message):
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(secret_key, date_stamp, region_name, service_name):
    key_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    key_region = hmac.new(key_date, region_name.encode("utf-8"), hashlib.sha256).digest()
    key_service = hmac.new(key_region, service_name.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()


def _get_env(name, default=""):
    return os.getenv(name, default).strip()


def _is_placeholder(value):
    lowered = value.strip().lower()
    return (
        not lowered
        or "your_" in lowered
        or "your-" in lowered
    )


def _build_headers(payload, access_key, secret_key, host, region):
    service = "ProductAdvertisingAPI"
    endpoint = "/paapi5/searchitems"
    content_encoding = "amz-1.0"
    content_type = "application/json; charset=utf-8"
    target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"

    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    canonical_headers = (
        f"content-encoding:{content_encoding}\n"
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:{target}\n"
    )
    signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
    canonical_request = (
        f"POST\n{endpoint}\n\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n{payload_hash}"
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    signing_key = _get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization_header = (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    return {
        "Content-Encoding": content_encoding,
        "Content-Type": content_type,
        "Host": host,
        "X-Amz-Date": amz_date,
        "X-Amz-Target": target,
        "Authorization": authorization_header,
    }


def _normalize_amazon_items(payload):
    items = payload.get("SearchResult", {}).get("Items", [])
    normalized = []

    for item in items:
        title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue")
        offers = item.get("OffersV2", {}).get("Listings") or item.get("Offers", {}).get("Listings") or []
        price_value = None

        if offers:
            price_info = offers[0].get("Price") or {}
            price_value = price_info.get("Amount")

            if price_value is None:
                display_amount = price_info.get("DisplayAmount", "")
                cleaned = "".join(char for char in display_amount if char.isdigit() or char == ".")
                if cleaned:
                    price_value = float(cleaned)

        if title and price_value is not None:
            normalized.append(
                {
                    "name": title,
                    "price": float(price_value),
                    "delivery": "1 day",
                }
            )

    return normalized


def search_amazon_products(product_requests):
    access_key = _get_env("AMAZON_PAAPI_ACCESS_KEY")
    secret_key = _get_env("AMAZON_PAAPI_SECRET_KEY")
    partner_tag = _get_env("AMAZON_PAAPI_PARTNER_TAG")
    host = _get_env("AMAZON_PAAPI_HOST", "webservices.amazon.in")
    region = _get_env("AMAZON_PAAPI_REGION", "eu-west-1")
    marketplace = _get_env("AMAZON_PAAPI_MARKETPLACE", "www.amazon.in")

    if _is_placeholder(access_key) or _is_placeholder(secret_key) or _is_placeholder(partner_tag):
        raise ValueError("Amazon PA-API credentials are not configured")

    query = ", ".join(request["name"] for request in product_requests)
    payload = json.dumps(
        {
            "Keywords": query,
            "Marketplace": marketplace,
            "PartnerTag": partner_tag,
            "PartnerType": "Associates",
            "SearchIndex": "All",
            "ItemCount": 10,
            "Resources": [
                "ItemInfo.Title",
                "OffersV2.Listings.Price",
            ],
        }
    )

    headers = _build_headers(payload, access_key, secret_key, host, region)
    response = requests.post(f"https://{host}/paapi5/searchitems", data=payload, headers=headers, timeout=20)
    response.raise_for_status()
    return _normalize_amazon_items(response.json())
