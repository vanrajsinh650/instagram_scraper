import os
import re
import random
import time
from datetime import datetime, timedelta
from config import OPENING_KEYWORDS, LOCATION_KEYWORDS


def ensure_output_dir():
    dir_name = "output"
    os.makedirs(dir_name, exist_ok=True)


def random_delay(min_seconds=2, max_seconds=5):
    time.sleep(random.uniform(min_seconds, max_seconds))


def is_recent_post(timestamp, days=None):
    if days is None:
        from config import DAYS_LOOKBACK
        days = DAYS_LOOKBACK

    now = datetime.now()
    cutoff_date = now - timedelta(days=days)

    if isinstance(timestamp, str) and not timestamp.isdigit():
        return False

    post_date = datetime.fromtimestamp(int(timestamp))
    return post_date >= cutoff_date


def matches_keywords(text, keywords):
    if not text:
        return False
    text = text.lower()
    for keyword in keywords:
        if keyword.lower() in text:
            return True
    return False


def is_relevant_post(caption):
    if not caption:
        return False

    caption_lower = caption.lower()
    has_opening_keyword = matches_keywords(caption_lower, OPENING_KEYWORDS)
    has_location_keyword = matches_keywords(caption_lower, LOCATION_KEYWORDS)
    return has_opening_keyword and has_location_keyword


def extract_emails(text):
    if not text:
        return []
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(email_pattern, text)))


def extract_phones(text):
    if not text:
        return []

    phone_pattern = r'(?:(?:\+|0{0,2})91[\s-]?)?[789]\d{9}'
    raw_phones = re.findall(phone_pattern, text)

    clean_phones = []
    for p in raw_phones:
        clean_num = re.sub(r'\D', '', p)
        if len(clean_num) > 10:
            clean_num = clean_num[-10:]
        if len(clean_num) == 10:
            clean_phones.append(clean_num)

    return list(set(clean_phones))


def extract_cafe_name(caption, username=None):
    if not caption:
        return username or ""

    lines = caption.strip().split("\n")

    # Strategy 1: look for text between quotes or 'at' markers
    at_match = re.search(r'(?:@|at\s+|welcome\s+to\s+|introducing\s+)([A-Z][A-Za-z0-9\s&\'-]{2,30})', caption)
    if at_match:
        name = at_match.group(1).strip()
        if len(name) > 2 and not name.lower().startswith(("http", "www")):
            return name

    # Strategy 2: look for quoted names
    quote_match = re.search(r'["\u201c]([A-Za-z0-9\s&\'-]{2,40})["\u201d]', caption)
    if quote_match:
        return quote_match.group(1).strip()

    # Strategy 3: first line is often the cafe name if short and title-cased
    first_line = lines[0].strip()
    # Remove common emoji/hashtag noise from start
    first_line_clean = re.sub(r'^[\U00010000-\U0010ffff\s\u2600-\u27bf]+', '', first_line, flags=re.UNICODE).strip()
    if 2 < len(first_line_clean) < 40 and not first_line_clean.startswith(("#", "http")):
        word_count = len(first_line_clean.split())
        if word_count <= 6:
            return first_line_clean

    # Strategy 4: look for "Cafe X" or "X Cafe" patterns
    cafe_pattern = re.search(
        r'((?:[A-Z][a-z]+\s+){0,3}(?:cafe|restaurant|bistro|kitchen|eatery|lounge|bar|brewery|bakery)(?:\s+[A-Z][a-z]+){0,2})',
        caption,
        re.IGNORECASE
    )
    if cafe_pattern:
        return cafe_pattern.group(1).strip()

    return username or ""


def clean_text(text, max_length=500):
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', str(text)).strip()
    return cleaned[:max_length] + '...' if len(cleaned) > max_length else cleaned
