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

    try:
        post_date = datetime.fromtimestamp(int(timestamp))
        return post_date >= cutoff_date
    except (ValueError, OSError):
        return False


def matches_keywords(text, keywords):
    if not text:
        return False
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False


def is_relevant_post(caption):
    if not caption:
        return False
    # only require opening/cafe keywords — location is implicit from hashtags
    return matches_keywords(caption, OPENING_KEYWORDS)


def is_relevant_post_strict(caption):
    if not caption:
        return False
    return matches_keywords(caption, OPENING_KEYWORDS) and matches_keywords(caption, LOCATION_KEYWORDS)


def extract_emails(text):
    if not text:
        return []
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(pattern, text)))


def extract_phones(text):
    if not text:
        return []

    pattern = r'(?:(?:\+|0{0,2})91[\s-]?)?[789]\d{9}'
    raw = re.findall(pattern, text)

    clean = []
    for p in raw:
        num = re.sub(r'\D', '', p)
        if len(num) > 10:
            num = num[-10:]
        if len(num) == 10:
            clean.append(num)
    return list(set(clean))


def extract_cafe_name(caption, username=None):
    if not caption:
        return username or ""

    lines = caption.strip().split("\n")

    at_match = re.search(r'(?:@|at\s+|welcome\s+to\s+|introducing\s+)([A-Z][A-Za-z0-9\s&\'-]{2,30})', caption)
    if at_match:
        name = at_match.group(1).strip()
        if len(name) > 2 and not name.lower().startswith(("http", "www")):
            return name

    quote_match = re.search(r'["\u201c]([A-Za-z0-9\s&\'-]{2,40})["\u201d]', caption)
    if quote_match:
        return quote_match.group(1).strip()

    first_line = lines[0].strip()
    first_line_clean = re.sub(r'^[\U00010000-\U0010ffff\s\u2600-\u27bf]+', '', first_line, flags=re.UNICODE).strip()
    if 2 < len(first_line_clean) < 40 and not first_line_clean.startswith(("#", "http")):
        word_count = len(first_line_clean.split())
        if word_count <= 6:
            return first_line_clean

    cafe_match = re.search(
        r'((?:[A-Z][a-z]+\s+){0,3}(?:cafe|restaurant|bistro|kitchen|eatery|lounge|bar|brewery|bakery)(?:\s+[A-Z][a-z]+){0,2})',
        caption, re.IGNORECASE
    )
    if cafe_match:
        return cafe_match.group(1).strip()

    return username or ""


def extract_address(text):
    if not text:
        return ""
    pin_match = re.search(r'(.{10,80}380\d{3}.{0,30})', text)
    if pin_match:
        addr = re.sub(r'\s+', ' ', pin_match.group(1).strip())
        return addr[:150]

    addr_match = re.search(r'(?:address|location|located at)[:\s]+(.{10,120})', text, re.IGNORECASE)
    if addr_match:
        return addr_match.group(1).strip().split('\n')[0][:150]
    return ""


def clean_text(text, max_length=500):
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', str(text)).strip()
    return cleaned[:max_length] + '...' if len(cleaned) > max_length else cleaned
