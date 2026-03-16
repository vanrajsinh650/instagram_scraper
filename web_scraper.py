import logging
import random
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from config import WEB_SEARCH_QUERIES, MAX_WEB_RESULTS, HEADLESS, LOCATION_KEYWORDS
from utils import extract_phones, extract_emails, extract_address, clean_text, random_delay

logger = logging.getLogger(__name__)


class WebScraper:
    def __init__(self, browser_context=None, page=None):
        self.context = browser_context
        self.page = page
        self.owns_browser = browser_context is None
        self.playwright = None
        self.browser = None

    def start_browser(self):
        if self.page:
            return
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=HEADLESS)
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.context = self.browser.new_context(user_agent=ua)
        self.page = self.context.new_page()

    def _google_search(self, query):
        results = []
        search_url = f"https://www.google.com/search?q={query}&num=15"
        logger.info("  Google search: %s", query)

        try:
            self.page.goto(search_url, timeout=30000)
            self.page.wait_for_selector("#search", timeout=15000)
            random_delay(1, 2)

            # dismiss consent if it appears
            try:
                self.page.click("button:has-text('Accept all'), button:has-text('I agree')", timeout=2000)
                self.page.wait_for_timeout(1000)
            except Exception:
                pass

            links = self.page.locator("#search a[href^='http']").all()
            for link in links:
                href = link.get_attribute("href") or ""
                if not href or "google.com" in href:
                    continue

                title = ""
                try:
                    title = link.locator("h3").first.inner_text()
                except Exception:
                    try:
                        title = link.inner_text().strip()
                    except Exception:
                        pass

                if not title or len(title) < 3:
                    continue

                # skip irrelevant domains
                skip = ("youtube.com", "facebook.com", "twitter.com", "pinterest.com", "reddit.com")
                if any(s in href for s in skip):
                    continue

                results.append({"url": href, "title": title})

                if len(results) >= MAX_WEB_RESULTS:
                    break

        except Exception as e:
            logger.error("  Google search failed: %s", e)

        logger.info("  Found %d result links.", len(results))
        return results

    def _scrape_result_page(self, url, title):
        record = {
            "cafe_name": "",
            "phone": "",
            "email": "",
            "address": "",
            "source_url": url,
            "source_title": title,
            "found_via": "Web",
        }

        try:
            self.page.goto(url, timeout=20000)
            self.page.wait_for_selector("body", timeout=10000)
            random_delay(1, 2)

            # grab all visible text from the page
            body_text = ""
            try:
                body_text = self.page.locator("body").inner_text()
            except Exception:
                pass

            if not body_text:
                return None

            # check if page is about ahmedabad
            text_lower = body_text.lower()
            if not any(loc in text_lower for loc in LOCATION_KEYWORDS):
                return None

            # extract cafe name from title or h1
            name = ""
            try:
                h1 = self.page.locator("h1").first
                if h1.is_visible(timeout=2000):
                    name = h1.inner_text().strip()
            except Exception:
                pass

            if not name:
                name = title

            # clean up name — remove common suffixes
            name = re.sub(r'\s*[-|,].*$', '', name).strip()
            name = re.sub(r'\s*(reviews?|menu|photos?|address|contact|zomato|justdial).*$', '', name, flags=re.IGNORECASE).strip()

            if len(name) < 2 or len(name) > 80:
                return None

            record["cafe_name"] = clean_text(name, 80)
            record["phone"] = ", ".join(extract_phones(body_text))
            record["email"] = ", ".join(extract_emails(body_text))
            record["address"] = extract_address(body_text)

            # at least name + one contact field to be useful
            if record["phone"] or record["email"] or record["address"]:
                return record

            return None

        except Exception as e:
            logger.warning("  Page scrape failed for %s: %s", url, e)
            return None

    def run(self):
        logger.info("Starting web scraper...")
        self.start_browser()

        all_results = []
        seen_urls = set()

        for query in WEB_SEARCH_QUERIES:
            logger.info("=== Web search: '%s' ===", query)
            links = self._google_search(query)

            for idx, link in enumerate(links, 1):
                url = link["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                logger.info("  Visiting %d/%d: %s", idx, len(links), url[:80])
                record = self._scrape_result_page(url, link["title"])
                if record:
                    all_results.append(record)
                    logger.info("    -> Found: %s | Phone: %s", record["cafe_name"], record["phone"] or "none")
                random_delay(2, 4)

            random_delay(3, 5)

        # deduplicate by cafe name
        seen_names = set()
        unique = []
        for r in all_results:
            norm = r["cafe_name"].lower().strip()
            if norm not in seen_names:
                seen_names.add(norm)
                unique.append(r)

        logger.info("Web scraper complete. %d unique results.", len(unique))

        if self.owns_browser:
            self.close()

        return unique

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
