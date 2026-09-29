from __future__ import annotations

from urllib.parse import quote_plus


def build_search_url(platform: str, item_name: str) -> str | None:
    query = quote_plus(item_name.strip())
    key = platform.strip().lower()
    templates = {
        "amazon": f"https://www.amazon.in/s?k={query}",
        "flipkart": f"https://www.flipkart.com/search?q={query}",
        "ikea": f"https://www.ikea.com/in/en/search/?q={query}",
        "swiggy": f"https://www.swiggy.com/search?query={query}",
        "zomato": f"https://www.zomato.com/search?q={query}",
        "oyo": f"https://www.oyorooms.com/search?location={query}",
    }
    return templates.get(key)


def normalize_platform(value: str, allowed: list[str]) -> str:
    normalized = value.strip().lower()
    for platform in allowed:
        if normalized == platform.lower():
            return platform
    return allowed[0]
