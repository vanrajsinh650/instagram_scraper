import os

INSTAGRAM_CREDENTIALS = {
    "username": os.environ.get("INSTAGRAM_USERNAME"),
    "password": os.environ.get("INSTAGRAM_PASSWORD"),
}

SCRAPE_MODE = "both"

SEARCH_QUERIES = [
    "new cafe ahmedabad",
    "cafe opening ahmedabad",
    "restaurant opening ahmedabad",
    "cafe coming soon ahmedabad",
    "sg highway cafe",
    "bopal cafe opening"
]

HASHTAGS = [
    "newcafeahmedabad",
    "ahmedabadcafe",
    "cafeopeningsoon",
    "ahmedabadnewcafe",
    "grandopeningahmedabad",
    "ahmedabadfoodie",
    "newrestaurantahmedabad",
    "ahmedabadfoodblogger",
    "ahmedabadfoodies",
    "ahmedabadfoodlovers",
    "ahmedabadfoodguide",
    "ahmedabadfoodscene",
    "ahmedabadfoodcrawl",
    "ahmedabadfoodhunt",
    "ahmedabadfoodlover",
    "ahmedabadfoodiesquad",
    "ahmedabadfoodiesclub",
    "ahmedabadfoodiesgroup",
    "ahmedabadfoodiescommunity",
    "ahmedabadfoodiesnetwork",
    "ahmedabadfood",
]

OPENING_KEYWORDS = [
    "opening soon", "coming soon", "grand opening", "soft launch",
    "now open", "newly opened", "just opened", "open soon",
    "launching soon", "new opening", "we are open", "newly launched",
    "grand launch", "opening shortly", "open now", "new cafe",
]

LOCATION_KEYWORDS = [
    "ahmedabad", "amdavad", "sg highway", "prahlad nagar",
    "satellite", "navrangpura", "cg road", "bopal", "south bopal",
    "thaltej", "vejalpur", "vastrapur", "gota", "chandkheda",
    "maninagar", "paldi", "iscon",
]

DAYS_LOOKBACK = 90
MAX_POSTS_PER_SOURCE = 80
REQUEST_TIMEOUT = 15
OUTPUT_DIR = "output"
OUTPUT_FILE = "new_cafe_ahmedabad.csv"

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

