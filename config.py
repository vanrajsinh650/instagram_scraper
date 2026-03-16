import os
import json
from dotenv import load_dotenv

load_dotenv()

INSTAGRAM_CREDENTIALS = {
    "username": os.environ.get("INSTAGRAM_USERNAME", ""),
    "password": os.environ.get("INSTAGRAM_PASSWORD", ""),
}

SCRAPE_MODE = os.environ.get("SCRAPE_MODE", "both")


def _parse_list_env(key, default):
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return [item.strip() for item in raw.split(",") if item.strip()]


SEARCH_QUERIES = _parse_list_env("SEARCH_QUERIES", [
    "new cafe ahmedabad",
    "cafe opening ahmedabad",
    "restaurant opening ahmedabad",
    "cafe coming soon ahmedabad",
    "sg highway cafe",
    "bopal cafe opening",
])

HASHTAGS = _parse_list_env("HASHTAGS", [
    "newcafeahmedabad",
    "ahmedabadcafe",
    "cafeopeningsoon",
    "ahmedabadnewcafe",
    "grandopeningahmedabad",
    "ahmedabadfoodie",
    "newrestaurantahmedabad",
    "ahmedabadfoodblogger",
])

OPENING_KEYWORDS = _parse_list_env("OPENING_KEYWORDS", [
    "opening soon", "coming soon", "grand opening", "soft launch",
    "now open", "newly opened", "just opened", "open soon",
    "launching soon", "new opening", "we are open", "newly launched",
    "grand launch", "opening shortly", "open now", "new cafe",
    "new restaurant", "cafe launch", "restaurant launch",
])

LOCATION_KEYWORDS = _parse_list_env("LOCATION_KEYWORDS", [
    "ahmedabad", "amdavad", "sg highway", "prahlad nagar",
    "satellite", "navrangpura", "cg road", "bopal", "south bopal",
    "thaltej", "vejalpur", "vastrapur", "gota", "chandkheda",
    "maninagar", "paldi", "iscon", "bodakdev", "ambli",
    "science city", "drive in", "law garden", "ellisbridge",
])

DAYS_LOOKBACK = int(os.environ.get("DAYS_LOOKBACK", 90))
MAX_POSTS_PER_SOURCE = int(os.environ.get("MAX_POSTS_PER_SOURCE", 80))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 15))

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "new_cafe_ahmedabad.xlsx")

HEADLESS = os.environ.get("HEADLESS", "false").lower() == "true"
AUTH_STATE_PATH = os.environ.get("AUTH_STATE_PATH", "state.json")

WEB_SEARCH_QUERIES = _parse_list_env("WEB_SEARCH_QUERIES", [
    "new cafe opening ahmedabad 2025",
    "upcoming cafe ahmedabad 2025",
    "new restaurant opening ahmedabad",
    "cafe grand opening ahmedabad",
    "newly opened cafe ahmedabad",
    "best new cafe ahmedabad",
])

MAX_WEB_RESULTS = int(os.environ.get("MAX_WEB_RESULTS", 10))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "x-ig-app-id": "936619743392459",
    "Referer": "https://www.instagram.com/",
    "X-Requested-With": "XMLHttpRequest",
}
