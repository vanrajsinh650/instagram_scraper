import os
import time, random
from datetime import datetime
from config import DAYS_LOOKBACK, OPENING_KEYWORDS, LOCATION_KEYWORDS, OUTPUT_DIR

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def rendom_delay(min_seconds=2,)