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
    """Checks if any keyword is present in the text."""
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
            
    caption = caption.lower()
    has_opening_keyword = matches_keywords(caption, OPENING_KEYWORDS)
    has_location_keyword = matches_keywords(caption, LOCATION_KEYWORDS)
    return has_opening_keyword and has_location_keyword

def extract_emails(text):
    """Extracts email addresses from text using regex."""
    if not text:
        return []
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(email_pattern, text)))

def extract_phones(text):
    """Extracts 10-digit Indian phone numbers."""
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

def clean_text(text, max_length=500):
    """Truncates text and removes newlines for Excel compatibility."""
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', str(text)).strip()
    # Truncate to max length
    return cleaned[:max_length] + '...' if len(cleaned) > max_length else cleaned
