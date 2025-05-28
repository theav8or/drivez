import asyncio
import random
import logging
import re
import json
import time
import platform
import hashlib
import uuid
from typing import List, Dict, Optional, Tuple, Any, Union, Set
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from enum import Enum, auto

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Page,
    BrowserContext,
    Browser,
    ElementHandle,
    Request as PlaywrightRequest,
    Response as PlaywrightResponse,
    Error as PlaywrightError
)
from fake_useragent import UserAgent
from app.core.config import settings
from app.db.models.car import CarListing as CarListingModel
from app.schemas.car import CarListingCreate

# Custom exceptions
class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass

class CaptchaError(ScraperError):
    """Raised when a CAPTCHA is detected."""
    pass

class RateLimitError(ScraperError):
    """Raised when rate limited by the server."""
    pass

class BrowserState(Enum):
    """Represents the current state of the browser."""
    INITIALIZING = auto()
    IDLE = auto()
    NAVIGATING = auto()
    EXTRACTING = auto()
    CAPTCHA_SOLVING = auto()
    ERROR = auto()

logger = logging.getLogger(__name__)

# Constants for Yad2 API endpoints and configuration
YAD2_API_BASE = "https://www.yad2.co.il/api"
YAD2_LISTINGS_ENDPOINT = f"{YAD2_API_BASE}/feed/feed/list"
YAD2_ITEM_ENDPOINT = f"{YAD2_API_BASE}/item"
YAD2_SEARCH_ENDPOINT = f"{YAD2_API_BASE}/preload/getFeedIndex/vehicles/cars"

# Common headers for API requests
COMMON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9,he;q=0.8",
    "content-type": "application/json",
    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-requested-with": "XMLHttpRequest"
}

class Yad2Scraper:
    def __init__(self, headless: bool = True, slow_mo: int = 100, max_retries: int = 3, 
                 proxy: Optional[str] = None, user_data_dir: Optional[str] = None):
        """Initialize the Yad2Scraper with enhanced configuration.
        
        Args:
            headless: Whether to run the browser in headless mode
            slow_mo: Slows down Playwright operations by the specified milliseconds
            max_retries: Maximum number of retries for failed operations
            proxy: Optional proxy server to use (format: "http://user:pass@host:port")
            user_data_dir: Optional directory to persist browser data (cookies, cache, etc.)
        """
        self.base_url = "https://www.yad2.co.il"
        self.search_url = f"{self.base_url}/vehicles/cars"
        self.timeout = 90000  # 90 seconds timeout
        self.max_retries = max_retries
        self.delay_range = (2, 5)  # Random delay between requests in seconds
        self.processed_urls: Set[str] = set()  # Track processed URLs to avoid duplicates
        self.headless = headless
        self.slow_mo = slow_mo
        self.proxy = proxy
        self.user_data_dir = user_data_dir
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.state = BrowserState.INITIALIZING
        self.last_request_time = 0
        self.request_count = 0
        self.failed_requests = 0
        self.captcha_solved = False
        self.session_id = str(uuid.uuid4())
        
        # Initialize statistics
        self.stats = {
            'requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'captcha_encounters': 0,
            'rate_limited': 0,
            'start_time': datetime.utcnow(),
            'pages_processed': 0,
            'listings_extracted': 0
        }
        
        # Browser context settings - expanded with more options to avoid detection
        self.browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process',
            '--disable-gpu',
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-site-isolation-trials',
            '--disable-notifications',
            '--disable-popup-blocking',
            '--disable-extensions',
            '--disable-translate',
            '--disable-background-networking',
            '--disable-sync',
            '--metrics-recording-only',
            '--mute-audio',
            '--no-default-browser-check',
            '--disable-client-side-phishing-detection',
            '--disable-component-update',
            '--disable-default-apps',
            '--use-fake-ui-for-media-stream',
            '--use-fake-device-for-media-stream',
            '--disable-hang-monitor',
            '--disable-ipc-flooding-protection',
            '--password-store=basic',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-breakpad',
            '--disable-component-extensions-with-background-pages',
            '--disable-session-crashed-bubble',
            '--disable-crash-reporter',
            '--use-mock-keychain',
            '--window-size=1920,1080',
            '--start-maximized',
            '--disable-infobars',
            '--disable-session-crashed-bubble',
            '--disable-sync',
            '--disable-translate',
            '--disable-web-resources',
            '--safebrowsing-disable-auto-update',
            '--safebrowsing-disable-download-protection',
            '--safebrowsing-disable-extension-blacklist',
            '--safebrowsing-disable-install-event',
            '--safebrowsing-disable-update',
            '--safebrowsing-disable-update-prompt'
        ]
        
        # Realistic headers - updated to match modern browsers
        self.headers = {
            **COMMON_HEADERS,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Referer": f"{self.base_url}/"
        }
        
        # Additional headers for API requests
        self.api_headers = {
            **COMMON_HEADERS,
            "referer": f"{self.base_url}/vehicles/cars",
            "origin": self.base_url,
            "x-y2-client": "web",
            "x-y2-client-version": "4.0.0"
        }
    
    async def _get_random_delay(self, min_multiplier: float = 1.0, max_multiplier: float = 2.0) -> float:
        """Return a random delay between requests to avoid being blocked.
        
        Args:
            min_multiplier: Minimum multiplier for the base delay
            max_multiplier: Maximum multiplier for the base delay
            
        Returns:
            float: A random delay in seconds
        """
        base_delay = random.uniform(*self.delay_range)
        return base_delay * random.uniform(min_multiplier, max_multiplier)

    async def _setup_browser(self) -> Tuple[Browser, BrowserContext, Page]:
        """Set up the Playwright browser, context, and page.
        
        Returns:
            Tuple containing (browser, context, page) objects
        """
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser with anti-detection settings
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=self.browser_args,
                slow_mo=self.slow_mo,
                chromium_sandbox=False,
                handle_sigint=True,
                handle_sigterm=True,
                handle_sighup=True,
                devtools=not self.headless
            )
            
            # Create a new browser context with custom viewport and locale
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='en-US,en;q=0.9,he;q=0.8',
                timezone_id='Asia/Jerusalem',
                user_agent=self.headers['User-Agent'],
                bypass_csp=True,
                ignore_https_errors=True,
                java_script_enabled=True,
                has_touch=False,
                is_mobile=False,
                reduced_motion='reduce',
                color_scheme='light',
                permissions=['geolocation']
            )
            
            # Grant permissions if needed
            await self.context.grant_permissions(['geolocation'])
            
            # Add custom headers to all requests
            await self.context.set_extra_http_headers(self.headers)
            
            # Block resources that aren't needed for scraping
            await self.context.route('**/*', self._route_handler)
            
            # Create a new page
            self.page = await self.context.new_page()
            
            # Set viewport size
            await self.page.set_viewport_size({"width": 1920, "height": 1080})
            
            # Set user agent
            await self.page.set_extra_http_headers({
                'User-Agent': self.headers['User-Agent']
            })
            
            # Disable timeout for debugging
            self.page.set_default_timeout(0)
            
            # Randomize viewport size slightly to avoid fingerprinting
            width = random.randint(1200, 1920)
            height = random.randint(800, 1080)
            await self.page.set_viewport_size({"width": width, "height": height})
            
            # Add some random mouse movements to appear more human
            await self._simulate_human_behavior(self.page)
            
            return self.browser, self.context, self.page
            
        except Exception as e:
            logger.error(f"Error setting up browser: {str(e)}", exc_info=True)
            await self._cleanup()
            raise
    
    async def _route_handler(self, route, request):
        """Handle route requests to block unnecessary resources."""
        resource_type = request.resource_type
        
        # Block unnecessary resources to speed up page load
        blocked_resources = [
            'image', 'font', 'stylesheet', 'media', 'other',
            'manifest', 'texttrack', 'websocket', 'xhr'
        ]
        
        if resource_type.lower() in blocked_resources:
            await route.abort()
        else:
            await route.continue_()
    
    async def _simulate_human_behavior(self, page: Page) -> None:
        """Simulate human-like behavior to avoid detection."""
        try:
            # Random mouse movements
            await page.mouse.move(
                random.randint(0, 500),
                random.randint(0, 500)
            )
            
            # Random scroll
            await page.mouse.wheel(
                delta_x=0,
                delta_y=random.randint(100, 500)
            )
            
            # Random delay
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
        except Exception as e:
            logger.warning(f"Error simulating human behavior: {str(e)}")
    
    async def _navigate_to_page(self, page: Page, url: str, retry_count: int = 0) -> bool:
        """Navigate to the specified URL with retry logic and bot detection handling.
        
        Args:
            page: Playwright Page object
            url: URL to navigate to
            retry_count: Current retry attempt count
            
        Returns:
            bool: True if navigation was successful, False otherwise
        """
        if retry_count >= self.max_retries:
            logger.error(f"Max retries ({self.max_retries}) exceeded for URL: {url}")
            return False
            
        try:
            self.state = BrowserState.NAVIGATING
            logger.info(f"Navigating to: {url} (attempt {retry_count + 1}/{self.max_retries})")
            
            # Set up request interception to block unnecessary resources
            await page.route('**/*', self._route_handler)
            
            # Randomize viewport size to appear more human-like
            viewport_width = random.randint(1200, 1920)
            viewport_height = random.randint(800, 1080)
            await page.set_viewport_size({"width": viewport_width, "height": viewport_height})
            
            # Add a random delay before navigation
            await asyncio.sleep(random.uniform(1.5, 3.5))
            
            # Set random user agent for each request
            user_agent = self._get_random_user_agent()
            await page.set_extra_http_headers({"User-Agent": user_agent})
            
            # Clear cookies and local storage to avoid tracking
            await page.context.clear_cookies()
            await page.evaluate('''() => {
                localStorage.clear();
                sessionStorage.clear();
            }''')
            
            # Navigate with realistic parameters
            navigation_options = {
                'wait_until': 'domcontentloaded',
                'timeout': self.timeout,
                'referer': random.choice([
                    'https://www.google.com/',
                    'https://www.bing.com/',
                    'https://duckduckgo.com/',
                    'https://www.yad2.co.il/'
                ])
            }
            
            await page.goto(url, **navigation_options)
            
            # Check for CAPTCHA or bot detection
            captcha_detected = await self._check_for_captcha(page)
            if captcha_detected:
                logger.warning("CAPTCHA detected after navigation")
                self.stats['captcha_encounters'] += 1
                if retry_count < self.max_retries - 1:  # Save last retry for different approach
                    await self._handle_captcha(page)
            
            # Wait for the main content to load with multiple fallback selectors
            content_selectors = [
                'main', 
                '[role="main"]', 
                '#__next', 
                '.app-root', 
                '.main-content',
                'div[data-test-id="feed"]',
                'div[class*="feed"]',
                'div[class*="list"]',
                'div[class*="results"]',
                'div[class*="items"]',
                'div[class*="grid"]'
            ]
            
            content_found = False
            for selector in content_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=10000, state="attached")
                    logger.debug(f"Found content with selector: {selector}")
                    content_found = True
                    break
                except Exception:
                    continue
            
            if not content_found:
                logger.warning("Could not find main content with any selector")
                # Take a screenshot for debugging
                await self._take_debug_screenshot(page, "content_not_found")
                
            # Check if we got redirected to a login or error page
            current_url = page.url
            if 'login' in current_url or 'error' in current_url or 'block' in current_url:
                logger.warning(f"Redirected to potential error/login page: {current_url}")
                return False
            
            self.stats['successful_requests'] += 1
            self.state = BrowserState.IDLE
            return True
            
        except PlaywrightTimeoutError as e:
            logger.warning(f"Timeout loading {url}: {str(e)}")
            if retry_count < self.max_retries:
                await asyncio.sleep(await self._get_random_delay(1.5, 3))
                return await self._navigate_to_page(page, url, retry_count + 1)
            logger.error(f"Failed to load {url} after {self.max_retries} attempts")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to {url}: {str(e)}")
            if retry_count < self.max_retries:
                await asyncio.sleep(await self._get_random_delay(1.5, 3))
                return await self._navigate_to_page(page, url, retry_count + 1)
            return False
    
    async def _handle_bot_detection(self, page: Page) -> bool:
        """Handle various bot detection mechanisms.
        
        Args:
            page: Playwright Page object
            
        Returns:
            bool: True if bot detection was handled, False otherwise
        """
        detection_handled = False
        
        # Check for Cloudflare challenge
        cf_challenge = await page.query_selector("text=Please complete the security check to continue")
        if cf_challenge:
            logger.warning("Cloudflare challenge detected, attempting to solve...")
            try:
                # Wait for the iframe to load
                await page.wait_for_selector('iframe[src*="challenges.cloudflare.com"]', timeout=10000)
                
                # Switch to the iframe
                frame = page.frame_locator('iframe[src*="challenges.cloudflare.com"]')
                
                # Click the checkbox
                await frame.locator('input[type="checkbox"]').click(timeout=10000)
                
                # Wait for verification
                await asyncio.sleep(5)
                detection_handled = True
                
            except Exception as e:
                logger.warning(f"Error solving Cloudflare challenge: {str(e)}")
        
        # Check for reCAPTCHA
        recaptcha = await page.query_selector("iframe[src*='recaptcha/api2/bframe']")
        if recaptcha and not detection_handled:
            logger.warning("reCAPTCHA detected, manual intervention required")
            # For now, just wait and hope for the best
            await asyncio.sleep(10)
            detection_handled = True
        
        # Check for other bot detection messages
        bot_messages = [
            "Please verify you are a human",
            "Access Denied",
            "Security Check",
            "Bot detected",
            "Rate limit exceeded"
        ]
        
        for message in bot_messages:
            if await page.query_selector(f"text/{message}"):
                logger.warning(f"Bot detection message found: {message}")
                detection_handled = True
                break
        
        # If we detected something, take a screenshot for debugging
        if detection_handled:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"yad2_bot_detection_{timestamp}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"Saved screenshot of bot detection to {screenshot_path}")
            except Exception as e:
                logger.warning(f"Failed to take screenshot: {str(e)}")
        
        return detection_handled
        
    async def _cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if hasattr(self, 'page') and self.page and not self.page.is_closed():
                try:
                    await self.page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {str(e)}")
            
            if hasattr(self, 'context') and self.context:
                try:
                    await self.context.close()
                except Exception as e:
                    logger.warning(f"Error closing context: {str(e)}")
            
            if hasattr(self, 'browser') and self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    logger.warning(f"Error closing browser: {str(e)}")
            
            if hasattr(self, 'playwright') and self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    logger.warning(f"Error stopping playwright: {str(e)}")
                    
            # Reset all attributes to None
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
    
    async def _extract_listing_data(self, item: ElementHandle) -> Optional[Dict[str, Any]]:
        """Extract data from a single listing element.
        
        Args:
            item: Playwright ElementHandle for the listing
            
        Returns:
            Optional[Dict]: Dictionary containing the extracted listing data, or None if extraction failed
        """
        try:
            # Extract basic information
            title_elem = await item.query_selector('[data-test-id="title"], .title, .feed-item-title')
            title = await title_elem.text_content() if title_elem else ""
            title = title.strip() if title else ""
            
            # Extract price
            price_elem = await item.query_selector('[data-test-id="price"], .price, .feed-item-price')
            price_text = await price_elem.text_content() if price_elem else ""
            price = int(re.sub(r'[^0-9]', '', price_text or "")) if price_text else 0
            
            # Extract URL and ID
            link_elem = await item.query_selector('a[href*="/item/"]')
            if not link_elem:
                link_elem = await item.query_selector('a')
                
            url = await link_elem.get_attribute('href') if link_elem else ""
            if url and not url.startswith('http'):
                url = urljoin(self.base_url, url)
                
            # Extract source ID from URL
            source_id = ""
            if url:
                # Try to extract ID from URL like /item/ABC123
                match = re.search(r'/item/([^/]+)', url)
                if match:
                    source_id = match.group(1)
                else:
                    # Fallback to last part of URL
                    source_id = url.split('/')[-1].split('?')[0]
            
            # Create listing dictionary with basic info
            listing = {
                'source': 'yad2',
                'source_id': source_id,
                'url': url,
                'title': title,
                'price': price,
                'year': 0,  # Will be updated from details
                'mileage': 0,  # Will be updated from details
                'location': "",  # Will be updated from details
                'description': "",  # Will be updated from details
                'fuel_type': "",  # Will be updated from details
                'transmission': "",  # Will be updated from details
                'body_type': "",  # Will be updated from details
                'color': "",  # Will be updated from details
                'brand': "",  # Will be extracted from title
                'model': "",  # Will be extracted from title
                'raw_data': {}
            }
            
            # Try to extract brand and model from title
            if title:
                # Common pattern: "Brand Model Year" or "Brand Model"
                parts = title.split()
                if parts:
                    listing['brand'] = parts[0]
                    if len(parts) > 1:
                        # Try to find year (usually at the end)
                        if parts[-1].isdigit() and len(parts[-1]) == 4:
                            try:
                                listing['year'] = int(parts[-1])
                                listing['model'] = ' '.join(parts[1:-1])
                            except (ValueError, IndexError):
                                listing['model'] = ' '.join(parts[1:])
                        else:
                            listing['model'] = ' '.join(parts[1:])
            
            # Extract details if available
            details_container = await item.query_selector('.feed_item_info, .details, .feed-item-details')
            if details_container:
                details = {}
                detail_items = await details_container.query_selector_all('.field, .detail')
                
                for detail in detail_items:
                    try:
                        label_elem = await detail.query_selector('.field_title, .detail-label')
                        value_elem = await detail.query_selector('.value, .detail-value')
                        
                        if label_elem and value_elem:
                            label = (await label_elem.text_content() or "").strip().lower()
                            value = (await value_elem.text_content() or "").strip()
                            
                            if label and value:
                                details[label] = value
                                
                                # Map details to our fields
                                if 'year' in label:
                                    try:
                                        listing['year'] = int(re.sub(r'[^0-9]', '', value))
                                    except (ValueError, TypeError):
                                        pass
                                elif 'mileage' in label or 'km' in label:
                                    try:
                                        listing['mileage'] = int(re.sub(r'[^0-9]', '', value))
                                    except (ValueError, TypeError):
                                        pass
                                elif 'location' in label or 'city' in label or 'area' in label:
                                    listing['location'] = value
                                elif 'fuel' in label:
                                    listing['fuel_type'] = value
                                elif 'transmission' in label or 'gear' in label:
                                    listing['transmission'] = value
                                elif 'body' in label or 'type' in label:
                                    listing['body_type'] = value
                                elif 'color' in label:
                                    listing['color'] = value
                    except Exception as e:
                        logger.warning(f"Error extracting detail: {str(e)}")
                        continue
                
                # Update raw data with extracted details
                listing['raw_data'] = details
            
            # Add timestamp
            listing['scraped_at'] = datetime.utcnow().isoformat()
            
            return listing
            
        except Exception as e:
            logger.warning(f"Error extracting listing data: {str(e)}", exc_info=True)
            return None
    
    async def _extract_page_listings(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all listings from the current page.
        
        Args:
            page: Playwright Page object
            
        Returns:
            List of extracted listings
        """
        listings = []
        
        # First, check if we're on a search results page or a single listing
        is_search_page = await self._is_search_results_page(page)
        
        if not is_search_page:
            logger.info("Not a search results page, trying to extract single listing")
            listing = await self._extract_single_listing(page)
            if listing:
                listings.append(listing)
            return listings
            
        # If we're on a search results page, try to extract multiple listings
        logger.info("Detected search results page, extracting multiple listings")
        
        # Try to find listings container
        container_selectors = [
            'div[data-test-id="feed"]',
            'div[class*="feed"]',
            'div[class*="list"]',
            'div[class*="results"]',
            'div[class*="items"]',
            'div[class*="grid"]',
            'main',
            'div[role="main"]',
            '#__next',
            '.app-root',
            '.main-content'
        ]
        
        container = None
        for selector in container_selectors:
            try:
                container = await page.query_selector(selector)
                if container:
                    logger.info(f"Found container with selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"Error finding container with selector {selector}: {str(e)}")
        
        if not container:
            logger.warning("Could not find listings container")
            return []
            
        # Take a screenshot of the container for debugging
        try:
            await container.screenshot(path='yad2_listings_container.png')
            logger.info("Saved container screenshot to yad2_listings_container.png")
        except Exception as e:
            logger.warning(f"Error taking container screenshot: {str(e)}")
        
        # Try different listing item selectors
        item_selectors = [
            'div[data-test-id*="feed-item"]',
            'div[class*="feed-item"]',
            'div[class*="feeditem"]',
            'div[class*="list-item"]',
            'div[class*="result-item"]',
            'div[class*="item"][data-test]',
            'div[class*="card"]',
            'article',
            'section',
            'li[class*="item"]',
            'div[role="article"]',
            'div[class*="product"]',
            'div[class*="listing"]'
        ]
        
        items = []
        for selector in item_selectors:
            try:
                # Try to find items within the container
                found_items = await container.query_selector_all(selector)
                if found_items:
                    logger.info(f"Found {len(found_items)} potential listings with selector: {selector}")
                    
                    # Sample a few items to verify they look like listings
                    sample_size = min(3, len(found_items))
                    valid_samples = 0
                    
                    for i in range(sample_size):
                        try:
                            item = found_items[i]
                            text = (await item.inner_text()).strip()
                            logger.debug(f"Sample item {i+1} text: {text[:100]}...")
                            
                            # Check for common listing elements
                            has_price = await item.query_selector('[class*="price"], [class*="Price"], .price, .Price')
                            has_title = await item.query_selector('[class*="title"], [class*="Title"], .title, .Title')
                            has_link = await item.query_selector('a[href]')
                            
                            if has_price or has_title or has_link:
                                valid_samples += 1
                                logger.info(f"Item {i+1} looks like a listing (price: {bool(has_price)}, title: {bool(has_title)}, link: {bool(has_link)})")
                            
                        except Exception as e:
                            logger.debug(f"Error examining sample item: {str(e)}")
                    
                    # If most samples look like valid listings, use this selector
                    if valid_samples > 0 and (valid_samples / sample_size) >= 0.5:
                        items = found_items
                        logger.info(f"Using selector: {selector}")
                        break
                    
            except Exception as e:
                logger.warning(f"Error with selector '{selector}': {str(e)}")
        
        if not items:
            logger.warning("No listing items found on the page")
            return []
            
        # Extract data from each listing
        extracted = 0
        for i, item in enumerate(items):
            try:
                # Scroll the item into view
                await item.scroll_into_view_if_needed()
                await asyncio.sleep(0.2)  # Small delay for any lazy loading
                
                # Try to extract the listing data
                listing_data = await self._extract_listing_data(item)
                if listing_data:
                    listings.append(listing_data)
                    extracted += 1
                    
                    # Log progress
                    if extracted % 5 == 0:
                        logger.info(f"Extracted {extracted} listings so far...")
                        
            except Exception as e:
                logger.warning(f"Error extracting listing {i+1}: {str(e)}")
                continue
        
        logger.info(f"Successfully extracted {extracted} out of {len(items)} listings")
        
        # If we still don't have listings, save the page for debugging
        if not listings:
            try:
                # Take a screenshot of the visible area
                await page.screenshot(path='yad2_no_listings.png')
                logger.info("Saved screenshot to yad2_no_listings.png")
                
                # Save the page HTML
                html = await page.content()
                with open('yad2_page_content.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.info("Saved page content to yad2_page_content.html")
                
                # Log the page URL
                logger.info(f"Current URL: {page.url}")
                
            except Exception as e:
                logger.warning(f"Error while saving debug information: {str(e)}")
        
        return listings
    
    async def _extract_listings_from_api(self, page: Page) -> List[Dict[str, Any]]:
        """Attempt to extract listings from the Yad2 API.
        
        Args:
            page: Playwright Page object
            
        Returns:
            List[Dict]: List of extracted listings from the API
        """
        listings = []
        try:
            # Try to find API request data in the page
            api_data = await page.evaluate('''() => {
                return window.__NEXT_DATA__?.props?.pageProps?.initialState?.feed?.feed || [];
            }''')
            
            if not api_data or not isinstance(api_data, list) or len(api_data) == 0:
                logger.warning("No API data found in page")
                return listings
                
            logger.info(f"Found {len(api_data)} listings in API data")
            
            # Process API data
            for item in api_data:
                try:
                    listing = self._parse_api_listing(item)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.warning(f"Error parsing API listing: {str(e)}")
                    continue
            
            return listings
            
        except Exception as e:
            logger.error(f"Error extracting listings from API: {str(e)}", exc_info=True)
            return listings
    
    def _parse_api_listing(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single listing from the API response.
        
        Args:
            item: Raw listing data from the API
            
        Returns:
            Optional[Dict]: Parsed listing data, or None if parsing failed
        """
        try:
            # Extract basic information
            listing_id = item.get('id', '')
            title = item.get('title', '')
            price = item.get('price', 0)
            
            # Extract URL
            url = item.get('link', '')
            if url and not url.startswith('http'):
                url = urljoin(self.base_url, url)
            
            # Extract additional details
            year = item.get('year', 0)
            mileage = item.get('mileage', 0)
            location = item.get('location', '')
            description = item.get('description', '')
            
            # Extract car details
            details = item.get('details', {})
            fuel_type = details.get('fuel_type', '')
            transmission = details.get('transmission', '')
            body_type = details.get('body_type', '')
            color = details.get('color', '')
            
            # Extract brand and model from title
            brand = item.get('manufacturer', '')
            model = item.get('model', '')
            
            if not brand and title:
                parts = title.split()
                if parts:
                    brand = parts[0]
            
            # Create the listing dictionary
            listing = {
                'source': 'yad2',
                'source_id': str(listing_id),
                'url': url,
                'title': title,
                'price': price,
                'year': int(year) if year else 0,
                'mileage': int(re.sub(r'[^0-9]', '', str(mileage))) if mileage else 0,
                'location': location,
                'description': description,
                'fuel_type': fuel_type,
                'transmission': transmission,
                'body_type': body_type,
                'color': color,
                'brand': brand,
                'model': model,
                'raw_data': item,
                'scraped_at': datetime.utcnow().isoformat()
            }
            
            return listing
            
        except Exception as e:
            logger.warning(f"Error parsing API listing: {str(e)}")
            return None
    
    async def _get_next_page_url(self, page: Page, current_page: int) -> Optional[str]:
        """Find the URL for the next page of results.
        
        Args:
            page: Playwright Page object
            current_page: Current page number (0-based)
            
        Returns:
            Optional[str]: URL of the next page, or None if no more pages
        """
        try:
            # First, try to find the next page button
            next_btn = await page.query_selector('a[data-role="next_page"], a[aria-label*="Next"], a[title*="Next"]')
            if next_btn:
                href = await next_btn.get_attribute('href')
                if href and '/vehicles/cars' in href:
                    return urljoin(self.base_url, href)
            
            # Try to find pagination links
            pages = await page.query_selector_all('.pagination a, .pagination-link, [data-test-id*="pagination"]')
            for page_el in pages:
                page_num = await page_el.text_content()
                if page_num and page_num.strip().isdigit() and int(page_num.strip()) == current_page + 2:  # +2 because pages are 1-based
                    href = await page_el.get_attribute('href')
                    if href and '/vehicles/cars' in href:
                        return urljoin(self.base_url, href)
                        
            # Try to find next button with arrow
            next_arrow = await page.query_selector('a.pagination-next, .next-page, [data-test-id*="next"]')
            if next_arrow:
                href = await next_arrow.get_attribute('href')
                if href and '/vehicles/cars' in href:
                    return urljoin(self.base_url, href)
            
            # If no next page found, return None
            logger.info(f"No next page link found after page {current_page + 1}")
            return None
            
        except Exception as e:
            logger.warning(f"Error finding next page URL: {str(e)}")
            return None
    
    async def _auto_scroll(self, page: Page) -> None:
        """Auto-scroll the page to load lazy-loaded content.
        
        Args:
            page: Playwright Page object
        """
        try:
            # Get the total scroll height
            total_height = await page.evaluate('document.body.scrollHeight')
            viewport_height = await page.evaluate('window.innerHeight')
            
            # Scroll down in increments
            current_position = 0
            scroll_step = random.randint(300, 700)  # Random scroll step to appear more human
            
            while current_position < total_height:
                # Scroll down
                await page.evaluate(f'window.scrollTo(0, {current_position})')
                
                # Random delay between scrolls
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
                # Update positions
                current_position += scroll_step
                total_height = await page.evaluate('document.body.scrollHeight')
                
                # Randomly change scroll direction occasionally
                if random.random() < 0.1:  # 10% chance
                    current_position = max(0, current_position - random.randint(100, 300))
                    
                # Randomly take a break
                if random.random() < 0.2:  # 20% chance
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    
        except Exception as e:
            logger.warning(f"Error during auto-scroll: {str(e)}")
    
    async def scrape(self, search_params: Optional[Dict] = None) -> List[Dict]:
        """Main method to scrape Yad2 car listings.
        
        Args:
            search_params: Optional dictionary of search parameters
                - manufacturer: Car manufacturer (e.g., 'Toyota')
                - model: Car model (e.g., 'Corolla')
                - year_from: Minimum year
                - year_to: Maximum year
                - price_from: Minimum price
                - price_to: Maximum price
                - mileage_from: Minimum mileage
                - mileage_to: Maximum mileage
                - location: Location (city/area)
                - page: Page number (starts from 1)
                - max_pages: Maximum number of pages to scrape (default: 10)
                
        Returns:
            List of scraped car listings
        """
        all_listings = []
        search_params = search_params or {}
        
        try:
            logger.info("Starting Yad2 scraper...")
            
            # Set up the browser
            logger.info("Setting up browser...")
            self.browser, self.context, self.page = await self._setup_browser()
            logger.info("Browser setup complete")
            
            # Build the search URL
            logger.info(f"Using search parameters: {search_params}")
            search_url = self._build_search_url(search_params)
            logger.info(f"Built search URL: {search_url}")
            
            # Navigate to the search page
            logger.info("Navigating to search page...")
            if not await self._navigate_to_page(self.page, search_url):
                logger.error("Failed to navigate to the search page")
                return []
            logger.info("Successfully navigated to search page")
            
            # Take a screenshot for debugging
            try:
                await self.page.screenshot(path='yad2_search_page.png')
                logger.info("Saved screenshot of search page to yad2_search_page.png")
            except Exception as e:
                logger.warning(f"Failed to take screenshot: {str(e)}")
                
            # Extract listings from the first page
            logger.info("Extracting listings from page 1...")
            page_listings = await self._extract_page_listings(self.page)
            logger.info(f"Found {len(page_listings)} listings on page 1")
            
            if page_listings:
                all_listings.extend(page_listings)
            else:
                logger.warning("No listings found on the first page")
                
                # Try to scroll to trigger lazy loading
                logger.info("Attempting to scroll to trigger lazy loading...")
                await self._auto_scroll(self.page)
                
                # Try extracting again after scroll
                logger.info("Re-attempting to extract listings after scroll...")
                page_listings = await self._extract_page_listings(self.page)
                if page_listings:
                    all_listings.extend(page_listings)
                    logger.info(f"Found {len(page_listings)} listings after scroll")
            
            # Try to extract from API if still no listings found
            if not all_listings:
                logger.info("No listings found in HTML, trying API...")
                api_listings = await self._extract_listings_from_api(self.page)
                if api_listings:
                    all_listings.extend(api_listings)
                    logger.info(f"Found {len(api_listings)} listings via API")
                else:
                    logger.warning("No listings found via API either")
            
            # Handle pagination if we found listings on the first page
            if all_listings:
                max_pages = search_params.get('max_pages', 3)  # Default to 3 pages for testing
                for page_num in range(2, max_pages + 1):
                    logger.info(f"Checking for page {page_num}...")
                    next_page_url = await self._get_next_page_url(self.page, page_num - 2)
                    
                    if not next_page_url:
                        logger.info("No more pages to scrape")
                        break
                        
                    logger.info(f"Found next page URL: {next_page_url}")
                    
                    # Add a random delay between page loads
                    delay = await self._get_random_delay(1.0, 3.0)
                    logger.info(f"Waiting {delay:.1f} seconds before next page...")
                    await asyncio.sleep(delay)
                    
                    # Navigate to the next page
                    logger.info(f"Navigating to page {page_num}...")
                    if not await self._navigate_to_page(self.page, next_page_url):
                        logger.warning(f"Failed to load page {page_num}")
                        break
                        
                    logger.info(f"Successfully navigated to page {page_num}")
                    
                    # Extract listings from current page
                    logger.info(f"Extracting listings from page {page_num}...")
                    page_listings = await self._extract_page_listings(self.page)
                    
                    if not page_listings:
                        logger.warning(f"No listings found on page {page_num}")
                        
                        # If we don't find listings, try to scroll down to trigger lazy loading
                        logger.info("Attempting to scroll to trigger lazy loading...")
                        await self._auto_scroll(self.page)
                        
                        # Try extracting again after scroll
                        logger.info("Re-attempting to extract listings after scroll...")
                        page_listings = await self._extract_page_listings(self.page)
                        if not page_listings:
                            logger.warning(f"Still no listings found on page {page_num} after scroll")
                            break
                    
                    all_listings.extend(page_listings)
                    logger.info(f"Found {len(page_listings)} listings on page {page_num}")
                    
                    # Random delay before next page to avoid rate limiting
                    delay = await self._get_random_delay(2.0, 5.0)
                    logger.info(f"Waiting {delay:.1f} seconds before next page...")
                    await asyncio.sleep(delay)
            
            logger.info(f"Scraping complete. Found {len(all_listings)} listings in total")
            
            # Save the listings to the database
            if all_listings:
                logger.info("Saving listings to database...")
                await self.normalize_and_store(all_listings)
                logger.info("Listings saved to database")
            else:
                logger.warning("No listings to save to database")
                
            return all_listings
            
        except Exception as e:
            logger.error(f"Error during scraping: {str(e)}", exc_info=True)
            return []
            
        finally:
            # Clean up resources
            logger.info("Cleaning up resources...")
            await self._cleanup()
            logger.info("Cleanup complete")
    
    def _build_search_url(self, params: Dict) -> str:
        """Build the search URL with the given parameters.
        
        Args:
            params: Dictionary of search parameters
            
        Returns:
            str: The complete search URL
        """
        base_url = f"{self.base_url}/vehicles/cars"
        
        if not params:
            return base_url
        
        # Convert parameters to URL query string
        query_parts = []
        
        # Manufacturer and model
        if 'manufacturer' in params:
            query_parts.append(f'manufacturer={params["manufacturer"].lower()}')
        if 'model' in params:
            query_parts.append(f'model={params["model"].lower()}')
            
        # Year range
        if 'year_from' in params or 'year_to' in params:
            year_from = params.get('year_from', 1900)
            year_to = params.get('year_to', datetime.now().year + 1)
            query_parts.append(f'year={year_from}-{year_to}')
            
        # Price range
        if 'price_from' in params or 'price_to' in params:
            price_from = params.get('price_from', 0)
            price_to = params.get('price_to', 1000000)
            query_parts.append(f'price={price_from}-{price_to}')
            
        # Mileage range
        if 'mileage_from' in params or 'mileage_to' in params:
            mileage_from = params.get('mileage_from', 0)
            mileage_to = params.get('mileage_to', 1000000)
            query_parts.append(f'mileage={mileage_from}-{mileage_to}')
            
        # Location
        if 'location' in params:
            query_parts.append(f'area={params["location"].lower()}')
            
        # Page number
        if 'page' in params and int(params['page']) > 1:
            query_parts.append(f'page={params["page"]}')
        
        # Combine all query parameters
        if query_parts:
            return f"{base_url}?{'&'.join(query_parts)}"
            
        return base_url


# Example usage
async def main():
    """Example usage of the Yad2Scraper class."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create scraper instance
    scraper = Yad2Scraper(headless=False)  # Set headless=False to see the browser
    
    try:
        # Define search parameters
        search_params = {
            'manufacturer': 'Toyota',
            'model': 'Corolla',
            'year_from': 2015,
            'price_to': 100000,
            'max_pages': 3  # Limit to 3 pages for testing
        }
        
        # Start scraping
        logger.info("Starting Yad2 scraper...")
        listings = await scraper.scrape(search_params)
        
        # Print results
        logger.info(f"Scraped {len(listings)} listings")
        for i, listing in enumerate(listings[:5], 1):  # Print first 5 listings
            logger.info(f"\nListing {i}:")
            logger.info(f"Title: {listing.get('title')}")
            logger.info(f"Price: {listing.get('price')} ILS")
            logger.info(f"Year: {listing.get('year')}")
            logger.info(f"Mileage: {listing.get('mileage')} km")
            logger.info(f"Location: {listing.get('location')}")
            logger.info(f"URL: {listing.get('url')}")
        
        return listings
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        return []
    finally:
        # Make sure to clean up
        await scraper._cleanup()


if __name__ == "__main__":
    # Run the scraper
    asyncio.run(main())

    async def _get_next_page_url(self, page, current_page: int) -> Optional[str]:
        """Find the URL for the next page of results."""
        try:
            # Look for pagination links
            next_btn = await page.query_selector('a[data-role="next_page"]')
            if next_btn:
                href = await next_btn.get_attribute('href')
                if href and '/vehicles/cars' in href:
                    return urljoin(self.base_url, href)
            
            # Alternative pagination method - look for page numbers
            pages = await page.query_selector_all('.pagination a, .pagination-link')
            for page_el in pages:
                page_num = await page_el.text_content()
                if page_num and page_num.strip().isdigit() and int(page_num.strip()) == current_page + 1:
                    href = await page_el.get_attribute('href')
                    if href and '/vehicles/cars' in href:
                        return urljoin(self.base_url, href)
                    
            # Alternative method - look for next button with arrow
            next_arrow = await page.query_selector('a.pagination-next, .next-page')
            if next_arrow:
                href = await next_arrow.get_attribute('href')
                if href and '/vehicles/cars' in href:
                    return urljoin(self.base_url, href)
            
            logger.warning(f"Could not find next page link for page {current_page + 1}")
            return None
            
        except Exception as e:
            logger.warning(f"Error finding next page URL: {str(e)}")
            return None

    async def _extract_page_listings(self, page) -> List[Dict]:
        """Extract all listings from the current page."""
        listings = []
        try:
            # Try multiple selectors to find listings
            selectors = [
                '[data-test-id="feed_item"]',
                '.feeditem:has(.feeditem-content)',
                '.feed_item',
                '.feed-item',
                '.car-feed-item'
            ]
            
            items = []
            for selector in selectors:
                items = await page.query_selector_all(selector)
                if items:
                    logger.info(f"Found {len(items)} listings with selector: {selector}")
                    break
            
            if not items:
                logger.warning("No listings found on the page")
                return listings
            
            logger.info(f"Processing {len(items)} listings...")
            
            for item in items:
                try:
                    listing_data = await self._extract_listing_data(item)
                    if listing_data:
                        listings.append(listing_data)
                except Exception as e:
                    logger.warning(f"Error extracting listing: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting page listings: {str(e)}")
        
        return listings

    async def _extract_listing_data(self, item) -> Optional[Dict]:
        """Extract data from a single listing element with enhanced error handling and data extraction.
        
        Args:
            item: The Playwright ElementHandle representing a single listing
            
        Returns:
            Optional[Dict]: Dictionary containing the extracted listing data, or None if extraction fails
        """
        try:
            self.state = BrowserState.EXTRACTING
            logger.debug("Starting to extract listing data")
            
            # Initialize default listing data
            listing = {
                'source': 'yad2',
                'source_id': "",
                'url': "",
                'title': "",
                'price': 0,
                'year': 0,
                'mileage': 0,
                'engine_volume': 0,
                'hand': 0,
                'location': "",
                'description': "",
                'fuel_type': "",
                'transmission': "",
                'body_type': "",
                'color': "",
                'brand': "",
                'model': "",
                'test_date': "",
                'next_test': "",
                'owners': 0,
                'features': [],
                'images': [],
                'seller_type': "",  # private/dealer
                'seller_rating': 0.0,
                'scraped_at': datetime.utcnow().isoformat(),
                'raw_data': {}
            }

            # Extract title if available
            try:
                title_elem = await item.query_selector('[data-test-id="title"], .title, .feed-item-title, h2, h3')
                if title_elem:
                    title = await title_elem.text_content()
                    listing['title'] = ' '.join(title.split()) if title else ""
            except Exception as e:
                logger.warning(f"Error extracting title: {str(e)}")

            # Extract price with better handling for different formats
            try:
                price_elem = await item.query_selector('[data-test-id="price"], .price, .feed-item-price, [class*="price"], [class*="Price"]')
                if price_elem:
                    price_text = await price_elem.text_content()
                    if price_text:
                        # Handle different price formats: "₪123,456", "123,456 ₪", "123456"
                        price_clean = re.sub(r'[^\d]', '', price_text)
                        if price_clean and price_clean.isdigit():
                            listing['price'] = int(price_clean)
            except Exception as e:
                logger.warning(f"Error extracting price: {str(e)}")

            # Extract URL with better error handling
            try:
                link_elem = await item.query_selector('a[href*="/item/"]')
                if not link_elem:
                    link_elem = await item.query_selector('a[href*="vehicles"], a[href*="car"]')
                
                if link_elem:
                    url = await link_elem.get_attribute('href')
                    if url:
                        if not url.startswith('http'):
                            url = urljoin(self.base_url, url)
                        listing['url'] = url
                        
                        # Extract source ID from URL with multiple fallback patterns
                        url_parts = url.split('?')
                        clean_url = url_parts[0]
                        
                        # Try different URL patterns
                        if '/item/' in clean_url:
                            # Format: /item/ABC123
                            match = re.search(r'/item/([^/]+)', clean_url)
                            if match:
                                listing['source_id'] = match.group(1)
                        elif '/vehicles/' in clean_url:
                            # Format: /vehicles/ABC123
                            parts = clean_url.split('/')
                            if len(parts) > 2:
                                listing['source_id'] = parts[-1] or parts[-2]
                        else:
                            # Fallback to last non-empty part of URL
                            parts = [p for p in clean_url.split('/') if p]
                            if parts:
                                listing['source_id'] = parts[-1]
            except Exception as e:
                logger.warning(f"Error extracting URL: {str(e)}")

            # Extract brand and model from title with improved parsing
            if listing['title']:
                try:
                    # Common patterns:
                    # "2020 Toyota Corolla Hybrid"
                    # "Toyota Corolla 2020"
                    # "Toyota Corolla Hybrid 2.0 2020"
                    
                    # Try to find year first (usually at the beginning or end)
                    year_match = re.search(r'\b(19|20)\d{2}\b', listing['title'])
                    if year_match:
                        listing['year'] = int(year_match.group(0))
                    
                    # Remove year and clean up
                    title_clean = re.sub(r'\b(19|20)\d{2}\b', '', listing['title']).strip()
                    parts = title_clean.split()
                    
                    if parts:
                        listing['brand'] = parts[0]
                        if len(parts) > 1:
                            # Find model end (before engine size or trim)
                            model_parts = []
                            for part in parts[1:]:
                                # Stop at engine size (e.g., 2.0, 1.6L) or trim (e.g., Executive, Luxury)
                                if re.match(r'^\d+(\.\d+)?[LlTtGgKk]?$', part) or part.isupper():
                                    break
                                model_parts.append(part)
                            
                            if model_parts:
                                listing['model'] = ' '.join(model_parts).strip()
                except Exception as e:
                    logger.warning(f"Error parsing brand/model from title: {str(e)}")

            # Extract details from the details container with improved parsing
            try:
                # Try multiple possible selectors for the details container
                details_selectors = [
                    '.feed_item_info', 
                    '.details', 
                    '.feed-item-details',
                    '[class*="details"]',
                    '.info',
                    '.specs',
                    '.specifications'
                ]
                
                details_container = None
                for selector in details_selectors:
                    details_container = await item.query_selector(selector)
                    if details_container:
                        break
                
                if details_container:
                    details = {}
                    detail_items = await details_container.query_selector_all('.field, .detail, .spec, .info-item, [class*="detail"], [class*="spec"]')
                    
                    for detail in detail_items:
                        try:
                            # Try different selectors for label and value
                            label_selectors = ['.field_title', '.detail-label', '.spec-label', 'dt', 'strong', 'b']
                            value_selectors = ['.value', '.detail-value', '.spec-value', 'dd', 'span']
                            
                            label_elem = None
                            value_elem = None
                            
                            # Find label element
                            for selector in label_selectors:
                                label_elem = await detail.query_selector(selector)
                                if label_elem:
                                    break
                            
                            # Find value element (try next sibling if label was found)
                            if label_elem:
                                value_elem = await label_elem.evaluate_handle('el => el.nextElementSibling')
                                if not value_elem or await value_elem.evaluate('el => el.nodeType !== 1'):  # Not an element node
                                    value_elem = None
                            
                            # If no value found, try specific selectors
                            if not value_elem:
                                for selector in value_selectors:
                                    value_elem = await detail.query_selector(selector)
                                    if value_elem:
                                        break
                            
                            if label_elem and value_elem:
                                try:
                                    label = (await label_elem.text_content() or "").strip().lower()
                                    value = (await value_elem.text_content() or "").strip()
                                    
                                    if label and value:
                                        details[label] = value
                                        
                                        # Map details to our fields with better pattern matching
                                        if any(x in label for x in ['year', 'שנה', 'שנתון']):
                                            try:
                                                year_match = re.search(r'\b(19|20)\d{2}\b', value)
                                                if year_match:
                                                    listing['year'] = int(year_match.group(0))
                                            except (ValueError, TypeError):
                                                pass
                                                
                                        elif any(x in label for x in ['mileage', 'ק"מ', 'קילומטראז', 'kilometers']):
                                            try:
                                                km = re.sub(r'[^\d]', '', value)
                                                if km and km.isdigit():
                                                    listing['mileage'] = int(km)
                                            except (ValueError, TypeError):
                                                pass
                                                
                                        elif any(x in label for x in ['location', 'מיקום', 'עיר', 'area', 'אזור']):
                                            listing['location'] = value
                                            
                                        elif any(x in label for x in ['fuel', 'דלק', 'סוג דלק']):
                                            listing['fuel_type'] = value
                                            
                                        elif any(x in label for x in ['transmission', 'gear', 'תיבת הילוכים', 'גיר']):
                                            listing['transmission'] = value
                                            
                                        elif any(x in label for x in ['body', 'type', 'סוג רכב', 'סוג']):
                                            listing['body_type'] = value
                                            
                                        elif any(x in label for x in ['color', 'צבע', 'צבע רכב']):
                                            listing['color'] = value
                                            
                                        elif any(x in label for x in ['engine', 'נפח מנוע', 'מנוע']):
                                            try:
                                                # Extract engine volume in CC (e.g., "2.0L" -> 2000)
                                                engine_match = re.search(r'(\d+(?:\.\d+)?)', value.replace(',', '.'))
                                                if engine_match:
                                                    engine_float = float(engine_match.group(1))
                                                    listing['engine_volume'] = int(engine_float * 1000)  # Convert to CC
                                            except (ValueError, TypeError):
                                                pass
                                                
                                        elif any(x in label for x in ['hand', 'יד', 'בעלים']):
                                            try:
                                                # Extract number (e.g., "יד 1" -> 1)
                                                hand_match = re.search(r'\d+', value)
                                                if hand_match:
                                                    listing['hand'] = int(hand_match.group(0))
                                            except (ValueError, TypeError):
                                                pass
                                except Exception as e:
                                    logger.debug(f"Error processing detail item: {str(e)}")
                                    continue
                        except Exception as e:
                            logger.debug(f"Error extracting detail element: {str(e)}")
                            continue
                    
                    # Update raw data with extracted details
                    listing['raw_data'] = details
                    
                    # Extract description if available
                    try:
                        desc_elem = await item.query_selector('.description, .feed-item-desc, [class*="description"], [class*="desc"]')
                        if desc_elem:
                            desc = await desc_elem.text_content()
                            if desc:
                                listing['description'] = ' '.join(desc.split())
                    except Exception as e:
                        logger.debug(f"Error extracting description: {str(e)}")
                    
                    # Extract seller type (private/dealer)
                    try:
                        seller_elem = await item.query_selector('.seller-type, .seller, [class*="seller"]')
                        if seller_elem:
                            seller_text = (await seller_elem.text_content() or "").lower()
                            if any(x in seller_text for x in ['dealer', 'סוחר', 'חברה']):
                                listing['seller_type'] = 'dealer'
                            elif any(x in seller_text for x in ['private', 'פרטי']):
                                listing['seller_type'] = 'private'
                    except Exception as e:
                        logger.debug(f"Error extracting seller type: {str(e)}")
                    
                    # Extract images if available
                    try:
                        img_elems = await item.query_selector_all('img[src*="yad2.co.il"], img[src*="yad2.co.il"], [class*="image"] img')
                        for img in img_elems:
                            try:
                                src = await img.get_attribute('src') or await img.get_attribute('data-src')
                                if src and src not in listing['images']:
                                    if not src.startswith('http'):
                                        src = urljoin(self.base_url, src)
                                    listing['images'].append(src)
                            except Exception:
                                continue
                    except Exception as e:
                        logger.debug(f"Error extracting images: {str(e)}")
                    
                    # Extract features if available
                    try:
                        feature_elems = await item.query_selector_all('.feature, .tag, .badge, [class*="feature"], [class*="tag"]')
                        for feat in feature_elems:
                            try:
                                feat_text = await feat.text_content()
                                if feat_text and feat_text.strip() and len(feat_text.strip()) < 50:  # Sanity check
                                    clean_feat = ' '.join(feat_text.strip().split())
                                    if clean_feat not in listing['features']:
                                        listing['features'].append(clean_feat)
                            except Exception:
                                continue
                    except Exception as e:
                        logger.debug(f"Error extracting features: {str(e)}")
            except Exception as e:
                logger.warning(f"Error processing details container: {str(e)}")
            
            # Validate required fields
            if not listing['source_id'] or not listing['url']:
                logger.debug(f"Skipping listing with missing required fields: {listing}")
                return None
                
            # Update statistics
            self.stats['listings_extracted'] += 1
            if self.stats['listings_extracted'] % 10 == 0:
                logger.info(f"Extracted {self.stats['listings_extracted']} listings so far")
            
            return listing
            
        except Exception as e:
            logger.error(f"Error extracting listing data: {str(e)}", exc_info=True)
            return None
        finally:
            self.state = BrowserState.IDLE

    async def normalize_and_store(self, listings: List[Dict]) -> None:
        """Normalize and store the scraped listings in the database."""
        if not listings:
            return
            
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            saved_count = 0
            updated_count = 0
            
            for listing in listings:
                try:
                    if not listing.get('source_id'):
                        logger.warning("Skipping listing without source_id")
                        continue
                    
                    # Check if listing already exists
                    existing = db.query(CarListingModel).filter(
                        CarListingModel.source == 'yad2',
                        CarListingModel.source_id == listing.get('source_id')
                    ).first()
                    
                    if not existing:
                        # Create new listing
                        db_listing = CarListingModel(
                            source='yad2',
                            source_id=listing.get('source_id'),
                            url=listing.get('url'),
                            title=listing.get('title'),
                            price=listing.get('price', 0),
                            mileage=listing.get('mileage', 0),
                            year=listing.get('year'),
                            location=listing.get('location', ''),
                            description=listing.get('description', ''),
                            fuel_type=listing.get('fuel_type', ''),
                            transmission=listing.get('transmission', ''),
                            body_type=listing.get('body_type', ''),
                            color=listing.get('color', ''),
                            brand=listing.get('brand', ''),
                            model=listing.get('model', ''),
                            raw_data=listing.get('raw_data', {})
                        )
                        db.add(db_listing)
                        saved_count += 1
                    else:
                        # Update existing listing
                        existing.price = listing.get('price', existing.price)
                        existing.mileage = listing.get('mileage', existing.mileage)
                        existing.raw_data = listing.get('raw_data', existing.raw_data)
                        updated_count += 1
                    
                    # Commit in batches of 10
                    if (saved_count + updated_count) % 10 == 0:
                        db.commit()
                        
                except Exception as e:
                    logger.error(f"Error saving listing: {str(e)}", exc_info=True)
                    db.rollback()
            
            # Final commit
            db.commit()
            logger.info(f"Successfully saved {saved_count} new listings and updated {updated_count} existing ones")
            
        except Exception as e:
            logger.error(f"Error in database operation: {str(e)}", exc_info=True)
            db.rollback()
        finally:
            db.close()
