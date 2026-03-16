import os
import json

# Fallback config file
CONFIG_FILE = "config.json"

def _load_config_file():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Warning: Failed to parse config.json. Using env vars defaults.")
    return {}

_file_config = _load_config_file()

INSTAGRAM_CREDENTIALS = {
    "username": os.environ.get("INSTAGRAM_USERNAME", _file_config.get("INSTAGRAM_USERNAME", "")),
    "password": os.environ.get("INSTAGRAM_PASSWORD", _file_config.get("INSTAGRAM_PASSWORD", "")),
}

SCRAPE_MODE = os.environ.get("SCRAPE_MODE", _file_config.get("SCRAPE_MODE", "both"))

SEARCH_QUERIES = _file_config.get("SEARCH_QUERIES", [
    "new cafe ahmedabad",
    "cafe opening ahmedabad",
    "restaurant opening ahmedabad",
    "cafe coming soon ahmedabad",
    "sg highway cafe",
    "bopal cafe opening"
])

HASHTAGS = _file_config.get("HASHTAGS", [
    "newcafeahmedabad",
    "ahmedabadcafe",
    "cafeopeningsoon",
    "ahmedabadnewcafe",
    "grandopeningahmedabad",
    "ahmedabadfoodie",
    "newrestaurantahmedabad",
    "ahmedabadfoodblogger"
])

OPENING_KEYWORDS = _file_config.get("OPENING_KEYWORDS", [
    "opening soon", "coming soon", "grand opening", "soft launch",
    "now open", "newly opened", "just opened", "open soon",
    "launching soon", "new opening", "we are open", "newly launched",
    "grand launch", "opening shortly", "open now", "new cafe",
])

LOCATION_KEYWORDS = _file_config.get("LOCATION_KEYWORDS", [
    "ahmedabad", "amdavad", "sg highway", "prahlad nagar",
    "satellite", "navrangpura", "cg road", "bopal", "south bopal",
    "thaltej", "vejalpur", "vastrapur", "gota", "chandkheda",
    "maninagar", "paldi", "iscon",
])

DAYS_LOOKBACK = int(os.environ.get("DAYS_LOOKBACK", _file_config.get("DAYS_LOOKBACK", 90)))
MAX_POSTS_PER_SOURCE = int(os.environ.get("MAX_POSTS_PER_SOURCE", _file_config.get("MAX_POSTS_PER_SOURCE", 80)))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", _file_config.get("REQUEST_TIMEOUT", 15)))

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", _file_config.get("OUTPUT_DIR", "output"))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", _file_config.get("OUTPUT_FILE", "new_cafe_ahmedabad.xlsx"))

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
