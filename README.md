# SmartCart AI

SmartCart AI is a Streamlit app for comparing grocery baskets across multiple platforms and helping users decide where to buy at the best overall value.

## Why We Designed This App

Online grocery shopping is not just about finding the lowest price for one item. People usually care about:

- total basket cost
- delivery speed
- delivery fees
- discounts
- whether splitting the basket across platforms is cheaper

SmartCart AI was designed to solve that problem in one place. It compares products across platforms, calculates the final payable amount, and recommends the better buying strategy.

## What The App Does

- compares multiple grocery products across platforms
- supports quantity-based shopping
- uses fuzzy matching to match similar product names
- calculates subtotal, delivery fee, discount, and final payable amount
- shows the best single-platform option
- builds an optimized basket plan
- builds a split basket plan
- compares split basket cost vs best platform cost

## Platforms Included

- Blinkit
- Instamart
- Amazon
- Dmart
- Zepto

## Project Structure

- [app.py](/d:/codex/SmartCartAI/smartcart-ai/LIVE_APP/app.py): Streamlit user interface
- [utils/comparator.py](/d:/codex/SmartCartAI/smartcart-ai/LIVE_APP/utils/comparator.py): comparison, pricing, and optimization logic
- [utils/matcher.py](/d:/codex/SmartCartAI/smartcart-ai/LIVE_APP/utils/matcher.py): fuzzy product matching
- [data](/d:/codex/SmartCartAI/smartcart-ai/LIVE_APP/data): mock platform catalog JSON files

## How To Use

1. Run the app with Streamlit.
2. Enter the `Pincode`.
3. Select the `Recommendation Mode`.
4. Enter a product name in the product row.
5. Select quantity from the dropdown.
6. Click `Add Item` to add another product row.
7. Click `Compare Basket`.

## Quantity Behavior

The app also interprets quantity in a more natural way for some products:

- `milk`, `oil`, `juice` -> quantity is treated as `litre`
- `sugar`, `rice`, `dal`, `atta`, `salt`, `flour` -> quantity is treated as `kg`
- other products default to `pcs`

Examples:

- `milk` + quantity `1` -> `1 litre`
- `sugar` + quantity `2` -> `2 kg`
- `bread` + quantity `3` -> `3 pcs`

## What You Will See

After searching, the app shows:

- `Platform Comparison`
- `Best Price`
- `Best Single Platform`
- `Savings`
- `Optimized Basket Plan`
- `Item Price Details`
- `Split Basket Summary`
- `Final Suggestion`

## Example

If you enter:

- milk -> 1
- sugar -> 2
- bread -> 1

the app will:

- find the closest matching products across all platforms
- calculate each platform's final payable amount
- generate an optimized basket plan
- generate a split basket plan
- tell you whether the split basket or the best single platform is the better choice

## Data Source

This project currently uses local mock JSON data only. No external API is required.

## Run The App

```bash
cd LIVE_APP
streamlit run app.py
```
