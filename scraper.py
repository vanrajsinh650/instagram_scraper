import os
import json
import logging
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from config import (
    HASHTAGS, SEARCH_QUERIES, MAX_POSTS_PER_SOURCE, 
    INSTAGRAM_CREDENTIALS, HEADLESS, AUTH_STATE_PATH
)
from utils import random_delay, is_recent_post, is_relevant_post

logger = logging.getLogger(__name__)

class InstagramScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.intercepted_posts = []

    def start_browser(self):
        """Initializes the Playwright Chromium browser."""
        self.playwright = sync_playwright().start()
        
        logger.info(f"Launching Chromium Browser (Headless: {HEADLESS})...")
        self.browser = self.playwright.chromium.launch(headless=HEADLESS)
        
        # Load saved cookies if they exist to bypass login
        if os.path.exists(AUTH_STATE_PATH):
            logger.info("Found saved session state. Loading cookies...")
            self.context = self.browser.new_context(storage_state=AUTH_STATE_PATH, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        else:
            self.context = self.browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
        # Intercept background API requests Instagram makes while we scroll
        self.context.route("**/*", self._intercept_route)
        self.page = self.context.new_page()

    def _intercept_route(self, route):
        """Inspects all network requests. If Instagram is downloading a GraphQL post payload, we steal it without rendering."""
        request = route.request
        
        # Pass all requests natively
        route.continue_()
        
        # We listen to the response on these requests instead of blocking them
        # (This is handled in the background, we just allow the route to proceed here)

    def _handle_response(self, response):
        """Listener that catches JSON responses as Instagram downloads them during scroll."""
        if "graphql/query" in response.url or "api/v1/tags/web_info" in response.url or "api/v1/fbsearch/topsearch" in response.url:
            try:
                json_data = response.json()
                self._parse_intercepted_json(json_data)
            except Exception:
                pass # Not JSON or empty

    def _parse_intercepted_json(self, data):
        """Extracts posts from the raw GraphQL/API JSON we caught in the background."""
        edges = []
        
        # Hashtag initial load
        if "data" in data and "recent" in data["data"]:
            edges = data["data"]["recent"].get("sections", [])
        # Hashtag pagination
        elif "data" in data and "hashtag" in data["data"]:
            edges = data["data"]["hashtag"].get("edge_hashtag_to_media", {}).get("edges", [])
            
        for edge in edges:
            node = edge.get("node", {})
            # Handle sections structure
            if "layout_content" in edge:
                medias = edge["layout_content"].get("medias", [])
                for m in medias:
                    if "media" in m:
                        self._process_post_node(m["media"])
            else:
                self._process_post_node(node)

    def _process_post_node(self, node):
        """Validates and saves a post from JSON."""
        if not node: return
        
        # Try different dictionary structures depending on the API endpoint
        shortcode = node.get("code") or node.get("shortcode")
        timestamp = node.get("taken_at") or node.get("taken_at_timestamp")
        
        # Get caption safely
        caption = ""
        if "caption" in node and isinstance(node["caption"], dict) and "text" in node["caption"]:
            caption = node["caption"]["text"]
        elif "edge_media_to_caption" in node and "edges" in node["edge_media_to_caption"]:
            edges = node["edge_media_to_caption"]["edges"]
            if edges and len(edges) > 0 and "node" in edges[0]:
                caption = edges[0]["node"].get("text", "")
        
        if not shortcode or not timestamp or node.get("is_video"):
            return
            
        if not is_recent_post(timestamp):
            return
            
        if not is_relevant_post(caption):
            return
            
        # Avoid duplicates
        if not any(p["url"] == f"https://www.instagram.com/p/{shortcode}" for p in self.intercepted_posts):
            self.intercepted_posts.append({
                "url": f"https://www.instagram.com/p/{shortcode}",
                "timestamp": timestamp,
                "caption": caption,
                "source": "intercepted"
            })

    def login(self):
        """Logs into Instagram using Playwright and saves the state."""
        logger.info("Navigating to Instagram...")
        self.page.goto("https://www.instagram.com/")
        
        # Wait for page to load
        try:
            # If we are already logged in (cookies worked), we will see the home/search icon
            self.page.wait_for_selector("svg[aria-label='Search'], svg[aria-label='Home']", timeout=5000)
            logger.info("Already logged in via saved cookies!")
            return True
        except PlaywrightTimeoutError:
            pass # We need to log in
            
        if not INSTAGRAM_CREDENTIALS.get("username") or not INSTAGRAM_CREDENTIALS.get("password"):
            logger.error("No credentials provided in .env! Playwright cannot login automatically.")
            return False

        logger.info("Typing credentials and logging in...")
        
        try:
            # Accept cookies if the popup appears (EU/UK)
            try:
                self.page.click("button:has-text('Allow all cookies'), button:has-text('Accept')", timeout=3000)
            except Exception:
                pass
                
            self.page.wait_for_selector("input[name='username']", timeout=10000)
            self.page.fill("input[name='username']", INSTAGRAM_CREDENTIALS["username"])
            self.page.fill("input[name='password']", INSTAGRAM_CREDENTIALS["password"])
            self.page.click("button[type='submit']")
            
            # Wait for successful login (navigates or shows Save Info dialog)
            try:
                self.page.wait_for_selector("svg[aria-label='Search'], svg[aria-label='Home'], button:has-text('Save Info'), button:has-text('Not Now')", timeout=15000)
            except PlaywrightTimeoutError:
                logger.error("Login failed or Instagram showed a challenge (e.g. 2FA or suspicious attempt). Check the browser window!")
                return False
                
            # Click "Not Now" on save info/notifications
            try:
                self.page.click("button:has-text('Not Now')", timeout=3000)
            except Exception:
                pass
                
            # Save the state for next time
            self.context.storage_state(path=AUTH_STATE_PATH)
            logger.info("Login successful. Session saved to %s", AUTH_STATE_PATH)
            return True
            
        except Exception as e:
            logger.error("Failed to execute login sequence: %s", e)
            return False

    def scrape_hashtag(self, hashtag):
        logger.info("Scraping hashtag: %s", hashtag)
        
        # Attach the JSON listener specifically for this run
        self.intercepted_posts = []
        self.page.on("response", self._handle_response)
        
        target_url = f"https://www.instagram.com/explore/tags/{hashtag}/"
        logger.info(f"Navigating to {target_url}")
        
        try:
            self.page.goto(target_url, wait_until="networkidle")
            random_delay(2, 4)
            
            # Scroll down repeatedly to force Instagram to load more posts via the API
            scrolls = 0
            while len(self.intercepted_posts) < MAX_POSTS_PER_SOURCE and scrolls < 5:
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self.page.wait_for_timeout(random.randint(2000, 4000)) # wait 2-4 seconds for network
                scrolls += 1
                logger.info("Scrolled %d times. Caught %d valid relevant posts so far.", scrolls, len(self.intercepted_posts))
                
        except Exception as e:
            logger.error("Error navigating timeline for hashtag %s: %s", hashtag, e)
            
        # Clean up the listener so it doesn't double-count on the next query
        self.page.remove_listener("response", self._handle_response)
        
        # Tag the source
        for post in self.intercepted_posts:
            post["source"] = f"hashtag:{hashtag}"
            
        return self.intercepted_posts

    def scrape_search(self, query):
        logger.info("Scraping search query: %s", query)
        
        self.intercepted_posts = []
        self.page.on("response", self._handle_response)
        
        try:
            # Use Instagram's native search
            self.page.goto("https://www.instagram.com/", wait_until="networkidle")
            
            # Click search icon
            self.page.click("svg[aria-label='Search']")
            self.page.wait_for_selector("input[placeholder='Search']", timeout=5000)
            
            # Type slowly like a human
            self.page.type("input[placeholder='Search']", query, delay=100)
            random_delay(2, 4)
            
            # Instagram will fire background XHR requests to search users, our _handle_response will catch some 
            # But search is harder to parse directly from the search bar drop down.
            # Usually people do searches to find specific users. The interceptor is designed mostly for feeds.
            
            # As a fallback or hybrid, we could click the top result and scrape their feed.
            logger.info("Pausing to let search results load...")
            self.page.wait_for_timeout(3000)
            
        except Exception as e:
            logger.error("Error searching query %s: %s", query, e)
            
        self.page.remove_listener("response", self._handle_response)
        
        for post in self.intercepted_posts:
            post["source"] = f"search:{query}"
            
        return self.intercepted_posts

    def run(self):
        all_results = []
        
        logger.info("Initializing Playwright pipeline...")
        self.start_browser()
        
        if not self.login():
            logger.error("Authentication failed or blocked. Aborting scrape.")
            self.close()
            return []
        
        for hashtag in HASHTAGS:
            results = self.scrape_hashtag(hashtag)
            all_results.extend(results)
            random_delay(2, 5)

        for query in SEARCH_QUERIES:
            # Search query scraping requires clicking profiles which is slightly more complex, 
            # the _handle_response might catch some initial previews if the API structure matches.
            results = self.scrape_search(query)
            all_results.extend(results)
            random_delay(2, 5)

        self.close()
        logger.info("Finished scraping. Collected %d valid items.", len(all_results))
        return all_results
        
    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()