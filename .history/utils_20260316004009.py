import os
import time, random, timedelta
from datetime import datetime
from config import DAYS_LOOKBACK, OPENING_KEYWORDS, LOCATION_KEYWORDS, OUTPUT_DIR

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def random_delay(min_seconds=2,max_seconds=5):
    time.sleep(random.uniform(min_seconds,max_seconds))

def is_recent_post(timestamp, days=None):
    if days is None:
        days = DAYS_LOOKBACK
    now = datetime.now()
    cutoff_date = now - timedelta(days=days)
    post_date = datetime.fromtimestamp(timestamp)
    return post_date >= cutoff_date

def matches_keywords(text, keywords):
    text = text.lower()
    for keyword in keywords:
        if keyword.lower() in text:
            return True
    return False

def is_relevant_post(caption):
    if not caption:
        return False
    caption = caption.lower()
    has_opening_keyword = matches_keywords(caption, OPENING_KEYWORDS)
    has_location_keyword = matches_keywords(caption, LOCATION_KEYWORDS)
    return has_opening_keyword and has_location_keyword

