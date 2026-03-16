import os
import json
import logging
import random
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from config import (
    HASHTAGS, SEARCH_QUERIES, MAX_POSTS_PER_SOURCE,
    INSTAGRAM_CREDENTIALS, HEADLESS, AUTH_STATE_PATH
)
from utils import (
    random_delay, is_recent_post, is_relevant_post,
    extract_emails, extract_phones, extract_cafe_name, clean_text
)

logger = logging.getLogger(__name__)


class InstagramScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.intercepted_posts = []
        self.seen_shortcodes = set()

    def start_browser(self):
        self.playwright = sync_playwright().start()

        logger.info("Launching Chromium Browser (Headless: %s)...", HEADLESS)
        self.browser = self.playwright.chromium.launch(headless=HEADLESS)

        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        if os.path.exists(AUTH_STATE_PATH):
            logger.info("Found saved session state. Loading cookies...")
            self.context = self.browser.new_context(
                storage_state=AUTH_STATE_PATH, user_agent=ua
            )
        else:
            self.context = self.browser.new_context(user_agent=ua)

        self.page = self.context.new_page()

    def _handle_response(self, response):
        api_patterns = [
            "graphql/query",
            "api/v1/tags/web_info",
            "api/v1/fbsearch/topsearch",
            "api/v1/tags",
        ]
        if any(pattern in response.url for pattern in api_patterns):
            try:
                json_data = response.json()
                self._parse_intercepted_json(json_data)
            except Exception:
                pass

    def _parse_intercepted_json(self, data):
        edges = []

        # Hashtag initial load — sections format
        if isinstance(data.get("data"), dict) and "recent" in data["data"]:
            edges = data["data"]["recent"].get("sections", [])
        # Hashtag pagination — edge format
        elif isinstance(data.get("data"), dict) and "hashtag" in data["data"]:
            ht = data["data"]["hashtag"]
            edges = ht.get("edge_hashtag_to_media", {}).get("edges", [])
        # Top posts section
        if isinstance(data.get("data"), dict) and "top" in data.get("data", {}):
            top_sections = data["data"]["top"].get("sections", [])
            edges.extend(top_sections)

        for edge in edges:
            if "layout_content" in edge:
                medias = edge["layout_content"].get("medias", [])
                for m in medias:
                    if "media" in m:
                        self._process_post_node(m["media"])
            else:
                node = edge.get("node", {})
                self._process_post_node(node)

    def _process_post_node(self, node):
        if not node:
            return

        shortcode = node.get("code") or node.get("shortcode")
        timestamp = node.get("taken_at") or node.get("taken_at_timestamp")

        if not shortcode or not timestamp:
            return

        if shortcode in self.seen_shortcodes:
            return

        caption = ""
        if isinstance(node.get("caption"), dict) and "text" in node["caption"]:
            caption = node["caption"]["text"]
        elif "edge_media_to_caption" in node:
            cap_edges = node["edge_media_to_caption"].get("edges", [])
            if cap_edges and "node" in cap_edges[0]:
                caption = cap_edges[0]["node"].get("text", "")

        if not is_recent_post(timestamp):
            return

        if not is_relevant_post(caption):
            return

        # Extract username from the node
        username = ""
        owner = node.get("user") or node.get("owner") or {}
        username = owner.get("username", "")

        self.seen_shortcodes.add(shortcode)
        self.intercepted_posts.append({
            "shortcode": shortcode,
            "url": f"https://www.instagram.com/p/{shortcode}/",
            "timestamp": timestamp,
            "caption": caption,
            "username": username,
            "source": "intercepted",
        })

    def login(self):
        logger.info("Navigating to Instagram...")
        self.page.goto("https://www.instagram.com/", timeout=60000)

        try:
            self.page.wait_for_selector(
                "svg[aria-label='Search'], svg[aria-label='Home']", timeout=8000
            )
            logger.info("Already logged in via saved cookies.")
            return True
        except PlaywrightTimeoutError:
            pass

        if not INSTAGRAM_CREDENTIALS.get("username") or not INSTAGRAM_CREDENTIALS.get("password"):
            logger.error("No credentials in .env. Cannot login.")
            return False

        logger.info("Typing credentials and logging in...")

        try:
            # Dismiss cookie banners
            try:
                self.page.click(
                    "button:has-text('Allow all cookies'), button:has-text('Accept')",
                    timeout=3000
                )
            except Exception:
                pass

            # Click existing "Log in" button if on landing page
            try:
                self.page.click("button:has-text('Log in')", timeout=3000)
            except Exception:
                pass

            try:
                self.page.wait_for_selector(
                    "input[name='username'], svg[aria-label='Search'], svg[aria-label='Home']",
                    timeout=20000
                )
            except PlaywrightTimeoutError:
                logger.error("Could not find login fields or home screen.")
                return False

            if self.page.locator("input[name='username']").count() > 0:
                self.page.type("input[name='username']", INSTAGRAM_CREDENTIALS["username"], delay=80)
                self.page.type("input[name='password']", INSTAGRAM_CREDENTIALS["password"], delay=80)
                self.page.keyboard.press("Enter")
            else:
                logger.info("Skipped credentials — Instagram loaded directly.")

            try:
                self.page.wait_for_selector(
                    "svg[aria-label='Search'], svg[aria-label='Home'], "
                    "button:has-text('Save Info'), button:has-text('Not Now')",
                    timeout=15000
                )
            except PlaywrightTimeoutError:
                logger.error("Login failed or challenged. Pausing 60s for manual intervention...")
                self.page.wait_for_timeout(60000)
                return False

            # Dismiss "Save Info" / "Notifications" prompts
            for _ in range(3):
                try:
                    self.page.click("button:has-text('Not Now')", timeout=2000)
                except Exception:
                    break

            self.context.storage_state(path=AUTH_STATE_PATH)
            logger.info("Login successful. Session saved to %s", AUTH_STATE_PATH)
            return True

        except Exception as e:
            logger.error("Login sequence failed: %s", e)
            return False

    def _enrich_post_with_profile(self, post):
        username = post.get("username", "")
        caption = post.get("caption", "")

        # Extract contact info from caption first
        phones_from_caption = extract_phones(caption)
        emails_from_caption = extract_emails(caption)
        cafe_name = extract_cafe_name(caption, username)

        bio_text = ""
        full_name = ""

        if username:
            try:
                profile_url = f"https://www.instagram.com/{username}/"
                logger.info("Visiting profile: %s", profile_url)
                self.page.goto(profile_url, timeout=30000)

                try:
                    self.page.wait_for_selector("header section", timeout=10000)
                except PlaywrightTimeoutError:
                    logger.warning("Profile page did not load for %s", username)
                    post["cafe_name"] = cafe_name
                    post["phone"] = ", ".join(phones_from_caption)
                    post["email"] = ", ".join(emails_from_caption)
                    return

                random_delay(1, 2)

                # Extract full name from profile header
                try:
                    name_el = self.page.locator("header section span[class] >> nth=0")
                    if name_el.count() > 0:
                        full_name = name_el.inner_text().strip()
                except Exception:
                    pass

                # Try the meta tag approach for full name
                if not full_name:
                    try:
                        meta_title = self.page.locator("meta[property='og:title']")
                        if meta_title.count() > 0:
                            content = meta_title.get_attribute("content") or ""
                            # Format: "Full Name (@username) • Instagram photos and videos"
                            if "(@" in content:
                                full_name = content.split("(@")[0].strip()
                    except Exception:
                        pass

                # Extract bio text
                try:
                    bio_el = self.page.locator("header section div[class] span[class]")
                    bio_parts = []
                    for i in range(min(bio_el.count(), 5)):
                        txt = bio_el.nth(i).inner_text().strip()
                        if txt and len(txt) > 1:
                            bio_parts.append(txt)
                    bio_text = " ".join(bio_parts)
                except Exception:
                    pass

                # Fallback: try the meta description for bio
                if not bio_text:
                    try:
                        meta_desc = self.page.locator("meta[property='og:description']")
                        if meta_desc.count() > 0:
                            bio_text = meta_desc.get_attribute("content") or ""
                    except Exception:
                        pass

            except Exception as e:
                logger.warning("Could not scrape profile for %s: %s", username, e)

        # Merge contact info from bio + caption
        all_phones = list(set(phones_from_caption + extract_phones(bio_text)))
        all_emails = list(set(emails_from_caption + extract_emails(bio_text)))

        # Determine best cafe name
        if full_name and len(full_name) > 1:
            cafe_name = full_name
        elif not cafe_name or cafe_name == username:
            cafe_name = extract_cafe_name(bio_text, username)

        post["cafe_name"] = clean_text(cafe_name, 100)
        post["phone"] = ", ".join(all_phones)
        post["email"] = ", ".join(all_emails)
        post["bio"] = clean_text(bio_text, 300)

    def scrape_hashtag(self, hashtag):
        logger.info("Scraping hashtag: #%s", hashtag)

        self.intercepted_posts = []
        self.seen_shortcodes = set()
        self.page.on("response", self._handle_response)

        target_url = f"https://www.instagram.com/explore/tags/{hashtag}/"
        logger.info("Navigating to %s", target_url)

        try:
            self.page.goto(target_url, timeout=60000)

            logger.info("Waiting for page content to load...")
            self.page.wait_for_selector("main, article", timeout=60000)
            random_delay(2, 4)

            scrolls = 0
            max_scrolls = 8
            last_count = 0
            stall_count = 0

            while len(self.intercepted_posts) < MAX_POSTS_PER_SOURCE and scrolls < max_scrolls:
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self.page.wait_for_timeout(random.randint(2500, 4500))
                scrolls += 1

                current_count = len(self.intercepted_posts)
                logger.info(
                    "Scroll %d/%d — caught %d relevant posts.",
                    scrolls, max_scrolls, current_count
                )

                if current_count == last_count:
                    stall_count += 1
                    if stall_count >= 3:
                        logger.info("No new posts after 3 scrolls. Moving on.")
                        break
                else:
                    stall_count = 0
                last_count = current_count

        except Exception as e:
            logger.error("Error scraping hashtag %s: %s", hashtag, e)

        self.page.remove_listener("response", self._handle_response)

        for post in self.intercepted_posts:
            post["source"] = f"hashtag:#{hashtag}"

        return list(self.intercepted_posts)

    def scrape_search(self, query):
        logger.info("Scraping search query: '%s'", query)

        self.intercepted_posts = []
        self.seen_shortcodes = set()
        self.page.on("response", self._handle_response)

        try:
            self.page.goto("https://www.instagram.com/", timeout=60000)
            self.page.wait_for_selector("svg[aria-label='Search']", timeout=60000)

            self.page.click("svg[aria-label='Search']")
            self.page.wait_for_selector("input[placeholder='Search']", timeout=5000)

            self.page.type("input[placeholder='Search']", query, delay=80)
            random_delay(2, 4)

            self.page.wait_for_timeout(3000)

            # Try clicking on the first hashtag or place result
            try:
                result_link = self.page.locator("a[href*='/explore/tags/'], a[href*='/locations/']").first
                if result_link.is_visible(timeout=3000):
                    result_link.click()
                    self.page.wait_for_selector("main, article", timeout=30000)
                    random_delay(2, 3)

                    # Scroll to load more posts
                    for scroll in range(5):
                        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        self.page.wait_for_timeout(random.randint(2500, 4000))
                        logger.info(
                            "Search scroll %d/5 — caught %d relevant posts.",
                            scroll + 1, len(self.intercepted_posts)
                        )
            except Exception:
                logger.info("No clickable search result found for '%s'.", query)

        except Exception as e:
            logger.error("Error during search '%s': %s", query, e)

        self.page.remove_listener("response", self._handle_response)

        for post in self.intercepted_posts:
            post["source"] = f"search:{query}"

        return list(self.intercepted_posts)

    def run(self):
        all_results = []

        logger.info("Initializing Playwright pipeline...")
        self.start_browser()

        if not self.login():
            logger.error("Authentication failed. Aborting scrape.")
            self.close()
            return []

        # Phase 1: Collect posts from hashtags
        for hashtag in HASHTAGS:
            results = self.scrape_hashtag(hashtag)
            all_results.extend(results)
            random_delay(3, 6)

        # Phase 2: Collect posts from search queries
        for query in SEARCH_QUERIES:
            results = self.scrape_search(query)
            all_results.extend(results)
            random_delay(3, 6)

        # Deduplicate across all sources
        seen = set()
        unique_results = []
        for post in all_results:
            if post["url"] not in seen:
                seen.add(post["url"])
                unique_results.append(post)
        all_results = unique_results

        logger.info(
            "Phase 1 complete — collected %d unique relevant posts. "
            "Starting Phase 2: profile enrichment...",
            len(all_results)
        )

        # Phase 3: Visit each post's profile to extract name and contact
        for idx, post in enumerate(all_results, 1):
            logger.info("Enriching post %d/%d — @%s", idx, len(all_results), post.get("username", "?"))
            self._enrich_post_with_profile(post)
            random_delay(2, 4)

        self.close()
        logger.info("Scraping complete. Collected %d enriched results.", len(all_results))
        return all_results

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()