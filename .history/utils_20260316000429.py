import os
import time, random
from datetime import datetime
from config import DAYS_LOOKBACK, OPENING_KEYWORDS, LOCATION_KEYWORDS, OUTPUT_DIR

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def rendom_delay(min_seconds=2,max_seconds=5):
    time.sleep(random.uniform(min_seconds,max_seconds))

def is_recent_post(timestamp, days=None):
    if days in None:
        config:DAYS_LOOKBACK
        datetime.now()
        timedelta(days=...)
        datetime.fromtimestamp()
    return True

def matches_keywords(text, keywords):
    text.lower()
    for keywords in keywords:
        if keywords.lower() in text:
            any()
    return False

def is_relevant_post(caption):
    if not caption:
        return False
    caption = caption.lower()
    has_opening_keyword = matches_keywords(caption, OPENING_KEYWORDS)
    has_location_keyword = matches_keywords(caption, LOCATION_KEYWORDS)
    has_cafe_keyword = matches_keywords(caption, ["cafe", "restaurant", "food", "cafe opening"])
    return has_opening_keyword and has_location_keyword and has_cafe_keyword

