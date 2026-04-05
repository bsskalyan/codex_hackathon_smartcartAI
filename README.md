# SmartCart AI

SmartCart AI is a Streamlit-based grocery basket comparison app. It helps a user build a cart, compare prices across multiple platforms, and decide whether buying from one platform or splitting the basket is the better option.

## Why I Designed This App

Quick-commerce and grocery apps make it easy to order products, but they also create a new problem: the cheapest item is not always the cheapest basket.

When a real user shops online, they usually care about more than one thing:

- total basket cost
- delivery speed
- delivery fees
- discounts
- availability of all items in one place
- whether splitting the basket across platforms saves money

I designed SmartCart AI to solve that decision in one dashboard. Instead of checking each app separately, the user can enter a basket once and compare the overall outcome.

## What The App Does

- lets the user build a grocery basket with multiple items
- supports quantity-aware shopping such as `1 litre`, `500 g`, `2 pcs`
- compares basket pricing across supported platforms
- calculates subtotal, delivery fee, discount, and final payable amount
- recommends a best single-platform option
- generates an optimized item-by-item basket plan
- generates a split-basket recommendation when buying from multiple platforms is cheaper
- supports both mock data and partial live integrations

## Vendor List

- Blinkit
- Instamart
- Amazon
- Dmart
- Zepto
- Flipkart
- BigBasket

## Current Integrated Platforms

- Blinkit
- Instamart
- Amazon
- Dmart
- Zepto

## Current UI Features

- colorful, eye-friendly Streamlit dashboard
- live basket updates with `Auto Compare`
- add and remove item rows dynamically
- mock-data preset baskets
- platform spotlight cards
- comparison charts and tables
- optimized basket and split basket tabs

## Project Structure

- [app.py](/d:/codex/codex_smartcartAI/codex_hackathon_smartcartAI/app.py): main Streamlit app and UI
- [providers/catalog_provider.py](/d:/codex/codex_smartcartAI/codex_hackathon_smartcartAI/providers/catalog_provider.py): mock/live catalog loading and provider fallback logic
- [providers/browser_automation.py](/d:/codex/codex_smartcartAI/codex_hackathon_smartcartAI/providers/browser_automation.py): Playwright-based browser-session support
- [providers/amazon_paapi.py](/d:/codex/codex_smartcartAI/codex_hackathon_smartcartAI/providers/amazon_paapi.py): Amazon PA-API integration
- [utils/comparator.py](/d:/codex/codex_smartcartAI/codex_hackathon_smartcartAI/utils/comparator.py): basket comparison, totals, and optimization logic
- [utils/matcher.py](/d:/codex/codex_smartcartAI/codex_hackathon_smartcartAI/utils/matcher.py): fuzzy product matching
- [scripts/browser_session_login.py](/d:/codex/codex_smartcartAI/codex_hackathon_smartcartAI/scripts/browser_session_login.py): helper script to save logged-in browser sessions
- [data](/d:/codex/codex_smartcartAI/codex_hackathon_smartcartAI/data): mock JSON catalogs

## How To Run

Install dependencies:

```bash
pip install -r requirements.txt
```

If you want browser-session live mode:

```bash
python -m playwright install chromium
```

Run the app:

```bash
streamlit run app.py --server.port 8503
```

Open:

```text
http://localhost:8503
```

## How To Use The App

1. Open the app in the browser.
2. Enter a `Pincode`.
3. Choose a `Recommendation Mode`:
   - `Cheapest`
   - `Fastest`
   - `Best Value`
4. Choose a `Data Source`:
   - `Mock Catalog`
   - `Live Portals`
5. Add products, pack sizes, and counts.
6. Use `Add Item` or `Remove Last` to adjust the basket.
7. Use `Reset Basket` to clear the basket.
8. Turn on `Auto Compare` if you want instant updates while editing.
9. Review the comparison, optimized basket, and split basket tabs.

## Mock Mode

Mock mode is the easiest way to demo the app.

It includes:

- local static platform catalogs
- preset baskets
- no external login required
- stable and repeatable comparison results

## Live Mode

Live mode currently supports two integration styles:

- direct API or endpoint mode
- browser-session mode using Playwright

### 1. API Or Endpoint Mode

This is the original live design.

You can configure provider endpoints in `.env`:

```env
LIVE_BLINKIT_SEARCH_URL=https://your-endpoint/search?query={query}&pincode={pincode}
LIVE_INSTAMART_SEARCH_URL=https://your-endpoint/search?query={query}&pincode={pincode}
LIVE_DMART_SEARCH_URL=https://your-endpoint/search?query={query}&pincode={pincode}
LIVE_ZEPTO_SEARCH_URL=https://your-endpoint/search?query={query}&pincode={pincode}
```

Amazon also supports PA-API:

```env
AMAZON_PAAPI_ACCESS_KEY=your_access_key
AMAZON_PAAPI_SECRET_KEY=your_secret_key
AMAZON_PAAPI_PARTNER_TAG=your_partner_tag
AMAZON_PAAPI_HOST=webservices.amazon.in
AMAZON_PAAPI_REGION=eu-west-1
AMAZON_PAAPI_MARKETPLACE=www.amazon.in
```

### 2. Browser-Session Mode

This is useful when there is no easy public API and the user can log into the website manually.

How it works:

1. Install Playwright.
2. Open the provider login page in an automated browser.
3. Log in manually.
4. Save the browser session to `.sessions`.
5. Let SmartCart reuse that session to search products.

Save a session example:

```bash
python scripts/browser_session_login.py --platform "Blinkit" --session-path ".sessions/blinkit_session.json"
```

Other examples:

```bash
python scripts/browser_session_login.py --platform "Amazon" --session-path ".sessions/amazon_session.json"
python scripts/browser_session_login.py --platform "Zepto" --session-path ".sessions/zepto_session.json"
python scripts/browser_session_login.py --platform "Dmart" --session-path ".sessions/dmart_session.json"
python scripts/browser_session_login.py --platform "Instamart" --session-path ".sessions/instamart_session.json"
python scripts/browser_session_login.py --platform "Flipkart" --session-path ".sessions/flipkart_session.json"
python scripts/browser_session_login.py --platform "BigBasket" --session-path ".sessions/bigbasket_session.json"
```

Then configure browser search support in `.env`.

Example for Amazon:

```env
BROWSER_AMAZON_LOGIN_URL=https://www.amazon.in/ap/signin
BROWSER_AMAZON_SEARCH_URL=https://www.amazon.in/s?k={query}
BROWSER_AMAZON_PRODUCT_CARD_SELECTOR=[data-component-type="s-search-result"]
BROWSER_AMAZON_NAME_SELECTOR=[data-cy="title-recipe"] a h2 span
BROWSER_AMAZON_PRICE_SELECTOR=.a-price .a-offscreen
BROWSER_AMAZON_DELIVERY_SELECTOR=[data-cy="delivery-recipe"]
BROWSER_AMAZON_WAIT_SELECTOR=[data-component-type="s-search-result"]
```

For Blinkit, Zepto, Dmart, and Instamart, you also need provider-specific search URLs and CSS selectors.
The same browser-session pattern can also be used for Flipkart and BigBasket.

## Quantity Behavior

The app infers more natural quantity units for some products:

- `milk`, `oil`, `juice` -> `litre`
- `sugar`, `rice`, `dal`, `atta`, `salt`, `flour` -> `kg`
- other items -> `pcs`

Examples:

- `milk` + `1 litre`
- `sugar` + `2 kg`
- `bread` + `3 pcs`

## What The User Sees

After comparison, the app can show:

- platform comparison overview
- platform spotlight cards
- best price summary
- recommended platform
- potential savings
- optimized basket plan
- split basket plan
- matched item price details
- final suggestion

## Current Working Status

At the current stage of the project:

- mock mode is stable
- Amazon browser-session live mode is partially working
- Blinkit may be blocked by Cloudflare depending on IP/session
- Instamart is not fully configured yet
- Dmart browser session exists but still needs live selector wiring and validation
- Zepto browser session exists but still needs live selector wiring and validation
- Flipkart has been added to the project and currently works in mock mode
- BigBasket has been added to the project and currently works in mock mode

## Limitations

- live mode is not fully production-ready yet
- some platforms may block automated browsing
- browser sessions can expire
- OTP, CAPTCHA, or anti-bot systems may interrupt login flows
- provider page structures can change at any time
- fuzzy matching can still return related but imperfect products
- Amazon browser results are improved, but still need stronger grocery-specific filtering
- some providers still fall back to mock data when live config is missing
- the app currently depends on manually configured CSS selectors for browser scraping

## Why These Limitations Exist

This project combines price comparison, fuzzy matching, and live commerce-site access. That is naturally difficult because:

- every provider has a different UI
- many providers do not expose easy public APIs
- browser automation is fragile compared to official APIs
- grocery product names are noisy and inconsistent across platforms

So the hardest part is not the UI or math. The hardest part is reliable live data collection and clean product matching.

## Next Updates

Planned and recommended next upgrades:

- improve Amazon result filtering for grocery relevance
- fully wire Dmart live browser search
- fully wire Zepto live browser search
- add Instamart browser-session support end to end
- add Flipkart live browser-session configuration
- add BigBasket live browser-session configuration
- improve provider-specific selectors and search strategies
- strengthen product matching using category-aware filters
- detect and suppress obviously bad matches
- cache live search results for faster comparison
- add better status messages for blocked or expired sessions
- optionally add a small backend service for provider automation instead of keeping everything in Streamlit

## Recommended Demo Flow

If you want the safest demo:

1. Start with `Mock Catalog`.
2. Use a preset basket.
3. Show platform comparison and split basket logic.
4. Switch to `Live Portals`.
5. Demonstrate Amazon browser-session results as the current live example.

## Summary

SmartCart AI is designed to answer a practical shopping question:

`Where should I buy my full cart for the best real outcome?`

The app already demonstrates the full comparison experience well in mock mode and has started supporting real live-provider flows through browser sessions. The strongest next step is improving and stabilizing provider-specific live integrations.
