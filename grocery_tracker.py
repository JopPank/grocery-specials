from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
import unicodedata
import requests

# Set your Gatineau-area postal code to match local flyers
POSTAL_CODE = "J9J 3X7"
# Add whatever grocery items you want to track here
STAPLES = ["chicken breast", "ground beef", "butter", "eggs"]
ALLOWED_STORES = (
    "IGA",
    "Voilà",
    "METRO",
    "ADONIS",
    "Walmart",
    "Marché Richelieu",
    "Provigo",
    "La Boite à Grains",
    "Loblaws",
    "M&M Food Market",
    "Maxi",
    "Super C",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}


class DealSearchError(Exception):
    pass


def normalize_store_name(name):
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w&]+", " ", normalized, flags=re.ASCII).casefold().split())


def allowed_store_for(merchant):
    merchant_name = normalize_store_name(merchant)
    for store in ALLOWED_STORES:
        allowed_name = normalize_store_name(store)
        if merchant_name == allowed_name or merchant_name.startswith(allowed_name + " "):
            return store
    return None


def is_allowed_store(merchant):
    return allowed_store_for(merchant) is not None


def search_grocery_deals(item_query, postal_code=POSTAL_CODE):
    """Return active, priced flyer matches; raise DealSearchError on failure."""
    url = "https://backflipp.wishabi.com/flipp/items/search"
    params = {"q": item_query, "postal_code": postal_code, "locale": "en-ca"}
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise DealSearchError(f"Could not retrieve specials: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise DealSearchError("Flipp returned an unexpected response (missing flyer items).")

    results = []
    seen = set()
    now = datetime.now(timezone.utc)
    for item in data["items"]:
        if not isinstance(item, dict):
            raise DealSearchError("Flipp returned an invalid flyer item.")
        merchant = item.get("merchant_name")
        title = item.get("name")
        price = item.get("current_price")
        store_category = allowed_store_for(str(merchant)) if merchant else None
        if (
            not merchant
            or not store_category
            or not title
            or price is None
            or price == ""
        ):
            continue
        try:
            amount = Decimal(str(price))
            if not amount.is_finite() or amount < 0:
                raise ValueError("invalid price")
            dates = {}
            for field in ("valid_from", "valid_to"):
                value = item.get(field)
                date = datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
                if date is not None and date.tzinfo is None:
                    raise ValueError("sale date has no timezone")
                dates[field] = date
        except (ValueError, TypeError, AttributeError, InvalidOperation) as exc:
            raise DealSearchError("Flipp returned an invalid price or sale date.") from exc

        if dates["valid_from"] and dates["valid_from"] > now:
            continue
        if dates["valid_to"] and dates["valid_to"] < now:
            continue
        prefix = str(item.get("pre_price_text") or "")
        suffix = str(item.get("post_price_text") or "")
        key = (merchant, title, str(amount), prefix, suffix,
               item.get("sale_story"), item.get("valid_from"), item.get("valid_to"))
        if key in seen:
            continue
        seen.add(key)
        flyer_id = str(item.get("flyer_id") or "")
        results.append({
            "merchant": str(merchant),
            "store_category": store_category,
            "title": str(title),
            "price": f"{amount:.2f}",
            "price_text": " ".join(part for part in (prefix, f"${amount:.2f}", suffix) if part),
            "sale_story": str(item.get("sale_story") or ""),
            "valid_from": dates["valid_from"],
            "valid_to": dates["valid_to"],
            "flyer_url": f"https://flipp.com/en-ca/flyer/{flyer_id}" if flyer_id.isdigit() else "",
        })
    return results


def run_deal_checker():
  print(f"[{datetime.now().strftime('%Y-%m-%d')}] 🛒 LOCAL GROCERY DEAL TRACKER")
  print(f"Postal Code: {POSTAL_CODE}\n" + "=" * 50)
  print("Included stores: " + ", ".join(ALLOWED_STORES))

  for staple in STAPLES:
    print(f"\nSearching deals for: '{staple.upper()}'")
    try:
      deals = search_grocery_deals(staple)
    except DealSearchError as exc:
      print(f"  Error checking {staple}: {exc}")
      continue

    if not deals:
      print("  No active flyer deals found.")
      continue

    # Show top 5 matching flyer deals
    for idx, deal in enumerate(deals[:5], 1):
      print(f"  {idx}. [{deal['merchant']}] {deal['title']} — {deal['price_text']}")


if __name__ == "__main__":
  run_deal_checker()