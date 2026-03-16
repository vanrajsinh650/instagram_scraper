import os
import json
import logging
import random
import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from config import (
    HASHTAGS, SEARCH_QUERIES, MAX_POSTS_PER_SOURCE,
    INSTAGRAM_CREDENTIALS, HEADLESS, AUTH_STATE_PATH
)
from utils import (
    random_delay, is_recent_post, is_relevant_post,
    extract_emails, extract_phones, extract_cafe_name,
    extract_address, clean_text
)

logger = logging.getLogger(__name__)


class InstagramScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.api_posts = []
        self.seen_shortcodes = set()
        self.profile_cache = {}

    def start_browser(self):
        self.playwright = sync_playwright().start()
        logger.info("Launching Chromium (headless=%s)...", HEADLESS)
        self.browser = self.playwright.chromium.launch(headless=HEADLESS)

        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        if os.path.exists(AUTH_STATE_PATH):
            logger.info("Loading saved session...")
            self.context = self.browser.new_context(storage_state=AUTH_STATE_PATH, user_agent=ua)
        else:
            self.context = self.browser.new_context(user_agent=ua)
        self.page = self.context.new_page()

    def _handle_response(self, response):
        url = response.url
        if "instagram.com" in url and any(p in url for p in (
            "graphql/query", "api/graphql", "api/v1/tags",
            "api/v1/fbsearch", "top_serp", "web_info"
        )):
            try:
                body = response.text()
                if len(body) > 500:
                    self._parse_api_json(json.loads(body))
            except Exception:
                pass

    def _parse_api_json(self, data):
        # NEW format: top_serp returns media_grid.sections directly
        media_grid = data.get("media_grid", {})
        if isinstance(media_grid, dict) and "sections" in media_grid:
            for section in media_grid["sections"]:
                lc = section.get("layout_content", {})
                for m in lc.get("medias", []):
                    if "media" in m:
                        self._process_node(m["media"])

        # OLD format: data.recent.sections / data.top.sections
        d = data.get("data", {})
        if isinstance(d, dict):
            for key in ("recent", "top"):
                if key in d:
                    for section in d[key].get("sections", []):
                        lc = section.get("layout_content", {})
                        for m in lc.get("medias", []):
                            if "media" in m:
                                self._process_node(m["media"])

            # OLD format: data.hashtag.edge_hashtag_to_media.edges
            if "hashtag" in d:
                ht = d["hashtag"]
                for key in ("edge_hashtag_to_media", "edge_hashtag_to_top_posts"):
                    for edge in ht.get(key, {}).get("edges", []):
                        self._process_node(edge.get("node", {}))

        # Search results format — users/places with media
        if "media_infos" in data:
            for mi in data["media_infos"]:
                self._process_node(mi)

    def _process_node(self, node):
        if not node:
            return
        shortcode = node.get("code") or node.get("shortcode")
        ts = node.get("taken_at") or node.get("taken_at_timestamp")
        if not shortcode or shortcode in self.seen_shortcodes:
            return

        caption = ""
        cap = node.get("caption")
        if isinstance(cap, dict):
            caption = cap.get("text", "")
        elif "edge_media_to_caption" in node:
            c_edges = node["edge_media_to_caption"].get("edges", [])
            if c_edges and "node" in c_edges[0]:
                caption = c_edges[0]["node"].get("text", "")

        # skip if too old
        if ts and not is_recent_post(ts):
            return

        # cap per source
        if len(self.api_posts) >= MAX_POSTS_PER_SOURCE:
            return

        owner = node.get("user") or node.get("owner") or {}
        username = owner.get("username", "")

        self.seen_shortcodes.add(shortcode)
        self.api_posts.append({
            "shortcode": shortcode,
            "url": f"https://www.instagram.com/p/{shortcode}/",
            "timestamp": ts,
            "caption": caption,
            "username": username,
            "source": "",
        })

    def login(self):
        logger.info("Navigating to Instagram...")
        self.page.goto("https://www.instagram.com/", timeout=60000)

        try:
            self.page.wait_for_selector("svg[aria-label='Search'], svg[aria-label='Home']", timeout=8000)
            logger.info("Logged in via saved cookies.")
            self._dismiss_dialogs()
            return True
        except PlaywrightTimeoutError:
            pass

        if not INSTAGRAM_CREDENTIALS.get("username") or not INSTAGRAM_CREDENTIALS.get("password"):
            logger.error("No credentials in .env.")
            return False

        logger.info("Logging in...")
        try:
            try:
                self.page.click("button:has-text('Allow all cookies'), button:has-text('Accept')", timeout=3000)
            except Exception:
                pass
            try:
                self.page.click("button:has-text('Log in')", timeout=3000)
            except Exception:
                pass

            self.page.wait_for_selector("input[name='username'], svg[aria-label='Search']", timeout=20000)

            if self.page.locator("input[name='username']").count() > 0:
                self.page.type("input[name='username']", INSTAGRAM_CREDENTIALS["username"], delay=80)
                self.page.type("input[name='password']", INSTAGRAM_CREDENTIALS["password"], delay=80)
                self.page.keyboard.press("Enter")

            self.page.wait_for_selector("svg[aria-label='Search'], svg[aria-label='Home'], button:has-text('Not Now')", timeout=20000)
            self._dismiss_dialogs()
            self.context.storage_state(path=AUTH_STATE_PATH)
            logger.info("Login successful.")
            return True
        except Exception as e:
            logger.error("Login failed: %s", e)
            return False

    def _dismiss_dialogs(self):
        for _ in range(3):
            try:
                self.page.click("button:has-text('Not Now')", timeout=2000)
                self.page.wait_for_timeout(500)
            except Exception:
                break

    def _scrape_profile(self, username):
        if username in self.profile_cache:
            return self.profile_cache[username]

        result = {"full_name": "", "bio": "", "external_link": "", "phones": [], "emails": []}
        if not username:
            return result

        try:
            self.page.goto(f"https://www.instagram.com/{username}/", timeout=20000)
            self.page.wait_for_selector("header section", timeout=10000)
            time.sleep(1)

            try:
                meta = self.page.locator("meta[property='og:title']")
                if meta.count() > 0:
                    content = meta.get_attribute("content") or ""
                    if "(@" in content:
                        result["full_name"] = content.split("(@")[0].strip()
            except Exception:
                pass

            try:
                meta_d = self.page.locator("meta[property='og:description']")
                if meta_d.count() > 0:
                    desc = meta_d.get_attribute("content") or ""
                    if " - " in desc:
                        bio = desc.split(" - ", 1)[1]
                        bio = re.sub(r"See Instagram photos and videos.*$", "", bio).strip()
                        if bio:
                            result["bio"] = bio
            except Exception:
                pass

            try:
                for link in self.page.locator("header section a[href*='http']").all():
                    href = link.get_attribute("href") or ""
                    if "instagram.com" not in href and href.startswith("http"):
                        result["external_link"] = href
                        break
            except Exception:
                pass

            combined = f"{result['full_name']} {result['bio']}"
            result["phones"] = extract_phones(combined)
            result["emails"] = extract_emails(combined)

        except Exception as e:
            logger.warning("  Profile failed @%s: %s", username, e)

        self.profile_cache[username] = result
        return result

    def scrape_hashtag(self, hashtag):
        logger.info("=== Hashtag: #%s ===", hashtag)
        self.api_posts = []
        local_seen = set()
        self.page.on("response", self._handle_response)

        try:
            self.page.goto(f"https://www.instagram.com/explore/tags/{hashtag}/", timeout=60000)
            self.page.wait_for_selector("main", timeout=60000)
            time.sleep(2)

            stall = 0
            last = 0
            for scroll in range(6):
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self.page.wait_for_timeout(random.randint(2000, 3500))
                current = len(self.api_posts)
                logger.info("  Scroll %d/6 — %d relevant posts caught", scroll + 1, current)
                if current == last:
                    stall += 1
                    if stall >= 2:
                        break
                else:
                    stall = 0
                last = current
        except Exception as e:
            logger.error("Hashtag error #%s: %s", hashtag, e)

        self.page.remove_listener("response", self._handle_response)

        for p in self.api_posts:
            p["source"] = f"#{hashtag}"
        return list(self.api_posts)

    def scrape_search(self, query):
        logger.info("=== Search: '%s' ===", query)
        self.api_posts = []
        self.page.on("response", self._handle_response)

        try:
            self.page.goto("https://www.instagram.com/", timeout=60000)
            self.page.wait_for_selector("svg[aria-label='Search']", timeout=30000)
            self.page.click("svg[aria-label='Search']")
            self.page.wait_for_selector("input[placeholder='Search']", timeout=5000)
            self.page.type("input[placeholder='Search']", query, delay=80)
            time.sleep(3)

            try:
                result = self.page.locator("a[href*='/explore/tags/'], a[href*='/locations/']").first
                if result.is_visible(timeout=3000):
                    result.click()
                    self.page.wait_for_selector("main", timeout=30000)
                    time.sleep(2)
                    for scroll in range(4):
                        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        self.page.wait_for_timeout(random.randint(2000, 3500))
                        logger.info("  Scroll %d/4 — %d relevant posts", scroll + 1, len(self.api_posts))
            except Exception:
                logger.info("  No clickable result for '%s'", query)
        except Exception as e:
            logger.error("Search error '%s': %s", query, e)

        self.page.remove_listener("response", self._handle_response)

        for p in self.api_posts:
            p["source"] = f"search:{query}"
        return list(self.api_posts)

    def run(self):
        logger.info("Starting Instagram scraper...")
        self.start_browser()

        if not self.login():
            logger.error("Auth failed.")
            self.close()
            return []

        all_posts = []

        for tag in HASHTAGS:
            posts = self.scrape_hashtag(tag)
            all_posts.extend(posts)
            random_delay(2, 4)

        for q in SEARCH_QUERIES:
            posts = self.scrape_search(q)
            all_posts.extend(posts)
            random_delay(2, 4)

        # deduplicate
        seen = set()
        unique = []
        for p in all_posts:
            if p["url"] not in seen:
                seen.add(p["url"])
                unique.append(p)

        logger.info("Found %d unique relevant posts. Enriching profiles...", len(unique))

        # profile enrichment — cached so same username is visited only once
        for idx, post in enumerate(unique, 1):
            username = post.get("username", "")
            logger.info("  Enriching %d/%d — @%s", idx, len(unique), username or "?")
            profile = self._scrape_profile(username)

            caption = post.get("caption", "")
            all_phones = list(set(profile["phones"] + extract_phones(caption)))
            all_emails = list(set(profile["emails"] + extract_emails(caption)))
            cafe_name = profile["full_name"] or extract_cafe_name(caption, username)

            post["cafe_name"] = clean_text(cafe_name, 100)
            post["phone"] = ", ".join(all_phones)
            post["email"] = ", ".join(all_emails)
            post["address"] = extract_address(caption)
            post["bio"] = clean_text(profile["bio"], 300)
            post["external_link"] = profile.get("external_link", "")
            random_delay(1, 2)

        self.close()
        logger.info("Done. %d enriched results.", len(unique))
        return unique

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()