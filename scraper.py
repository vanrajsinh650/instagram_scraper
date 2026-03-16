import logging
import time
import requests
from requests.exceptions import RequestException
from config import HEADERS, HASHTAGS, SEARCH_QUERIES, MAX_POSTS_PER_SOURCE, INSTAGRAM_CREDENTIALS, REQUEST_TIMEOUT
from utils import random_delay, is_recent_post, is_relevant_post

logger = logging.getLogger(__name__)

class InstagramScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.csrf_token = None

    def _get_csrf_token(self):
        try:
            response = self.session.get("https://www.instagram.com/", timeout=REQUEST_TIMEOUT)
            self.csrf_token = response.cookies.get("csrftoken")
            if self.csrf_token:
                self.session.headers.update({"x-csrftoken": self.csrf_token})
                logger.info("Retrieved CSRF token.")
            else:
                logger.warning("Could not retrieve CSRF token. Request might fail.")
        except RequestException as e:
            logger.error("Failed to fetch CSRF token: %s", e)

    def login(self):
        """Authenticate with Instagram using credentials present in config."""
        if not INSTAGRAM_CREDENTIALS.get("username") or not INSTAGRAM_CREDENTIALS.get("password"):
            logger.warning("No credentials found. Proceeding with unauthenticated session.")
            return False

        self._get_csrf_token()

        try:
            timestamp = int(time.time())
            # Safely encode the password utilizing Instagram's expected format
            enc_password = f"#PWD_INSTAGRAM_BROWSER:0:{timestamp}:{INSTAGRAM_CREDENTIALS['password']}"
            
            payload = {
                "username": INSTAGRAM_CREDENTIALS["username"],
                "enc_password": enc_password,
                "queryParams": "{}",
                "optIntoOneTap": "false",
            }
            
            headers = {
                "x-requested-with": "XMLHttpRequest",
                "Referer": "https://www.instagram.com/accounts/login/",
            }
            
            if self.csrf_token:
                headers["x-csrftoken"] = self.csrf_token

            login_url = "https://www.instagram.com/accounts/login/ajax/"
            response = self.session.post(login_url, data=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            
            if response.status_code == 200 and response.json().get("authenticated"):
                logger.info("Login successful. Authenticated as %s", INSTAGRAM_CREDENTIALS["username"])
                return True
            else:
                logger.error("Login failed. Status error or not authenticated: %s", response.text)
                return False

        except RequestException as e:
            logger.error("Login request failed: %s", e)
            return False

    def scrape_hashtag(self, hashtag):
        logger.info("Scraping hashtag: %s", hashtag)
        results = []
        try:
            url = f"https://www.instagram.com/explore/hashtag/{hashtag}?__a=1&__d=dis"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.warning("Failed to fetch hashtag %s: HTTP %s", hashtag, response.status_code)
                return results

            data = response.json()
            # Safely navigate JSON structure
            posts = data.get("graphql", {}).get("hashtag", {}).get("edge_hashtag_to_top_posts", {}).get("edges", [])
            
            for post in posts:
                post_data = post.get("node", {})
                
                if post_data.get("is_video"):
                    continue
                    
                timestamp = post_data.get("taken_at_timestamp")
                if not timestamp or not is_recent_post(timestamp):
                    continue
                    
                edges = post_data.get("edge_media_to_caption", {}).get("edges", [])
                caption = edges[0]["node"]["text"] if edges else ""
                
                if not is_relevant_post(caption):
                    continue

                results.append({
                    "url": f"https://www.instagram.com/p/{post_data.get('shortcode')}",
                    "timestamp": timestamp,
                    "caption": caption,
                    "source": f"hashtag:{hashtag}",
                })
                
                if len(results) >= MAX_POSTS_PER_SOURCE:
                    break

        except RequestException as e:
            logger.error("Network error while scraping hashtag %s: %s", hashtag, e)
        except Exception as e:
            logger.error("Data parsing error for hashtag %s: %s", hashtag, e)

        return results

    def scrape_search(self, search_query):
        logger.info("Scraping search query: %s", search_query)
        results = []
        try:
            url = f"https://www.instagram.com/web/search/topsearch/?query={search_query}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.warning("Failed search query %s. HTTP %s", search_query, response.status_code)
                return results

            users = response.json().get("users", [])
            
            for user_item in users:
                user = user_item.get("user", {})
                if user.get("is_private"):
                    continue
                    
                username = user.get("username")
                if not username:
                    continue

                # Add conservative delay between profile reads
                random_delay(1, 3) 
                profile_url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
                profile_resp = self.session.get(profile_url, timeout=REQUEST_TIMEOUT)
                
                if profile_resp.status_code != 200:
                    continue

                profile_data = profile_resp.json().get("graphql", {}).get("user", {})
                timeline = profile_data.get("edge_owner_to_timeline_media", {}).get("edges", [])
                
                for post_edge in timeline:
                    post_node = post_edge.get("node", {})
                    
                    if post_node.get("is_video"):
                        continue
                        
                    timestamp = post_node.get("taken_at_timestamp")
                    if not timestamp or not is_recent_post(timestamp):
                        continue
                        
                    caption_edges = post_node.get("edge_media_to_caption", {}).get("edges", [])
                    caption = caption_edges[0]["node"]["text"] if caption_edges else ""
                    
                    if not is_relevant_post(caption):
                        continue

                    results.append({
                        "url": f"https://www.instagram.com/p/{post_node.get('shortcode')}",
                        "timestamp": timestamp,
                        "caption": caption,
                        "source": f"search:{search_query}",
                    })
                    
                    if len(results) >= MAX_POSTS_PER_SOURCE:
                        break

        except RequestException as e:
            logger.error("Network error while scraping search query %s: %s", search_query, e)
        except Exception as e:
            logger.error("Parsing error scraping search query %s: %s", search_query, e)
            
        return results

    def run(self):
        all_results = []
        
        logger.info("Starting up scraper pipeline...")
        self.login()
        
        for hashtag in HASHTAGS:
            results = self.scrape_hashtag(hashtag)
            all_results.extend(results)
            random_delay(2, 5)

        for query in SEARCH_QUERIES:
            results = self.scrape_search(query)
            all_results.extend(results)
            random_delay(2, 5)

        logger.info("Finished scraping. Collected %d valid items.", len(all_results))
        return all_results