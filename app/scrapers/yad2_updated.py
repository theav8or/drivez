import asyncio
import hashlib
import json
import logging
import os
import platform
import random
import re
import time
import traceback
import uuid
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from fake_useragent import UserAgent
from pydantic import BaseModel
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    ElementHandle,
    Page,
    Playwright,
    Request as PlaywrightRequest,
    Response as PlaywrightResponse,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
)

# Local imports
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
    async def __aenter__(self):
        """Async context manager entry point."""
        await self._setup_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit point.
        
        Args:
            exc_type: Exception type if an exception was raised, None otherwise
            exc_val: Exception instance if an exception was raised, None otherwise
            exc_tb: Traceback if an exception was raised, None otherwise
        """
        try:
            await self._cleanup()
        except Exception as e:
            logger.error(f"Error during context manager exit: {str(e)}", exc_info=True)
            # Don't suppress the original exception if there was one
            if exc_val is None:
                raise

    def __init__(self, headless: bool = True, slow_mo: int = 100, max_retries: int = 3, 
                 proxy: Optional[str] = None, user_data_dir: Optional[str] = None, db = None):
        """Initialize the Yad2Scraper with enhanced configuration.
        
        Args:
            headless: Whether to run the browser in headless mode
            slow_mo: Slows down Playwright operations by the specified milliseconds
            max_retries: Maximum number of retries for failed operations
            proxy: Optional proxy server to use (format: "http://user:pass@host:port")
            user_data_dir: Optional directory to persist browser data (cookies, cache, etc.)
            db: Optional database session for direct database operations
        """
        self.db = db  # Store the database session
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
        
        # Initialize UserAgent for generating random user agents
        self.user_agent = UserAgent()
        
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
        
        # Set up headers for requests
        self.headers = {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
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
            '--disable-infobars',
            '--window-size=1366,768',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-web-security',
            '--disable-site-isolation-trials',
            '--disable-blink-features=AutomationControlled'
        ]
    
    def _get_random_user_agent(self) -> str:
        """Generate a random user agent string.
        
        Returns:
            str: A random user agent string
        """
        return self.user_agent.random
        
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

    async def _cleanup_resources(self):
        """Clean up browser resources."""
        try:
            # Close page if it exists and is not closed
            if hasattr(self, 'page') and self.page:
                try:
                    if not self.page.is_closed():
                        await self.page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {str(e)}")
                finally:
                    self.page = None
            
            # Close context if it exists
            if hasattr(self, 'context') and self.context:
                try:
                    await self.context.close()
                except Exception as e:
                    logger.warning(f"Error closing context: {str(e)}")
                finally:
                    self.context = None
                
            # Close browser if it exists
            if hasattr(self, 'browser') and self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    logger.warning(f"Error closing browser: {str(e)}")
                finally:
                    self.browser = None
                
            # Stop Playwright if it exists
            if hasattr(self, 'playwright') and self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    logger.warning(f"Error stopping Playwright: {str(e)}")
                finally:
                    self.playwright = None
                    
            # Add a small delay to ensure resources are properly released
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"Unexpected error during cleanup: {str(e)}")
        finally:
            # Ensure all references are cleared
            if hasattr(self, 'page'):
                self.page = None
            if hasattr(self, 'context'):
                self.context = None
            if hasattr(self, 'browser'):
                self.browser = None
            if hasattr(self, 'playwright'):
                self.playwright = None
    
    async def _setup_browser(self) -> Tuple[Browser, BrowserContext, Page]:
        """
        Set up the Playwright browser, context, and page with anti-detection measures.
        
        Returns:
            Tuple containing (browser, context, page) objects
        """
        max_retries = 3
        last_error = None
        
        # Clean up any existing resources first
        await self._cleanup_resources()
        
        for attempt in range(max_retries):
            self.playwright = None
            self.browser = None
            self.context = None
            self.page = None
            
            try:
                # Initialize Playwright
                logger.info(f"Initializing Playwright (attempt {attempt + 1}/{max_retries})...")
                self.playwright = await async_playwright().start()
                
                # Enhanced browser launch options with anti-detection measures
                launch_options = {
                    'headless': self.headless,
                    'timeout': 120000,  # 120 second timeout for browser launch
                    'handle_sigint': False,  # Don't let Playwright handle SIGINT
                    'handle_sigterm': False,  # Don't let Playwright handle SIGTERM
                    'handle_sighup': False,   # Don't let Playwright handle SIGHUP
                    'slow_mo': self.slow_mo,  # Add delays between actions to appear more human-like
                    'args': [
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-infobars',
                        '--window-size=1366,768',
                        '--start-maximized',
                        '--disable-gpu',
                        '--single-process',
                        '--no-zygote',
                        '--disable-web-security',
                        '--disable-blink-features',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-site-isolation-trials',
                        '--disable-webgl',
                        '--disable-threaded-animation',
                        '--disable-threaded-scrolling',
                        '--disable-in-process-stack-traces',
                        '--disable-logging',
                        '--log-level=3',
                        '--output=/dev/null',
                        '--disable-accelerated-2d-canvas',
                        '--disable-accelerated-jpeg-decoding',
                        '--disable-accelerated-mjpeg-decode',
                        '--disable-accelerated-video-decode',
                        '--disable-accelerated-video-encode',
                        '--disable-software-rasterizer',
                        '--disable-breakpad',
                        '--disable-client-side-phishing-detection',
                        '--disable-default-apps',
                        '--disable-hang-monitor',
                        '--disable-popup-blocking',
                        '--disable-prompt-on-repost',
                        '--disable-sync',
                        '--metrics-recording-only',
                        '--no-first-run',
                        '--safebrowsing-disable-auto-update',
                        '--password-store=basic',
                        '--use-mock-keychain',
                        '--disable-background-networking',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-backing-store-limit',
                        '--disable-component-update',
                        '--disable-datasaver-prompt',
                        '--disable-domain-reliability',
                        '--disable-ipc-flooding-protection',
                        '--disable-notifications',
                        '--disable-renderer-backgrounding',
                        '--disable-remote-fonts',
                        '--mute-audio',
                        '--no-default-browser-check',
                        '--no-pings',
                        '--autoplay-policy=user-gesture-required',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-ipc-flooding-protection',
                        '--disable-renderer-backgrounding',
                        '--disable-back-forward-cache',
                        '--disable-background-networking',
                        '--disable-component-update',
                        '--disable-default-apps',
                        '--disable-hang-monitor',
                        '--disable-sync',
                        '--metrics-recording-only',
                        '--no-first-run',
                        '--safebrowsing-disable-auto-update',
                        '--password-store=basic',
                        '--use-mock-keychain',
                        '--disable-bundled-ppapi-flash',
                        '--disable-extensions',
                        '--disable-features=TranslateUI,BlinkGenPropertyTrees',
                        '--disable-ipc-flooding-protection',
                        '--disable-renderer-backgrounding',
                        '--enable-features=NetworkService,NetworkServiceInProcess',
                        '--force-color-profile=srgb',
                        '--hide-scrollbars',
                        '--ignore-gpu-blacklist',
                        '--in-process-gpu',
                        '--mute-audio',
                        '--no-default-browser-check',
                        '--no-pings',
                        '--no-sandbox',
                        '--no-zygote',
                        '--prerender-from-omnibox=disabled',
                        '--use-gl=swiftshader',
                        '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
                    ]
                }
                
                # Add proxy if configured
                if self.proxy:
                    launch_options['proxy'] = {'server': self.proxy}
                
                # Add user data dir if specified
                if self.user_data_dir:
                    launch_options['user_data_dir'] = self.user_data_dir
                
                # Launch browser
                logger.info("Launching browser...")
                self.browser = await self.playwright.chromium.launch(**launch_options)
                
                # Create a new browser context with storage state
                # Set up browser context with storage state
                context_options = {
                    'viewport': {'width': 1920, 'height': 1080},
                    'locale': 'en-US',
                    'timezone_id': 'Asia/Jerusalem',
                    'ignore_https_errors': True,
                    'java_script_enabled': True,
                    'color_scheme': 'light',
                    'permissions': ['geolocation'],
                    'extra_http_headers': {
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Referer': 'https://www.google.com/',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    },
                    'storage_state': {
                        'cookies': [],
                        'origins': [
                            {
                                'origin': 'https://www.yad2.co.il',
                                'localStorage': [
                                    {'name': 'cookies_accepted', 'value': 'true'},
                                    {'name': 'gdpr_accepted', 'value': 'true'},
                                    {'name': 'consent', 'value': 'granted'}
                                ]
                            },
                            {
                                'origin': 'https://ynet.co.il',
                                'localStorage': [
                                    {'name': 'cookies_accepted', 'value': 'true'},
                                    {'name': 'consent', 'value': 'granted'}
                                ]
                            }
                        ]
                    }
                }
                
                self.context = await self.browser.new_context(**context_options)
                self.page = await self.context.new_page()
                
                # Set default timeouts
                self.page.set_default_timeout(90000)  # 90 seconds
                self.page.set_default_navigation_timeout(90000)  # 90 seconds
                
                try:
                    response = await self.page.goto(
                        'about:blank',
                        wait_until='domcontentloaded',
                        timeout=30000
                    )
                    logger.info(f"Initial navigation status: {response.status if response else 'No response'}")
                except Exception as nav_error:
                    logger.error(f"Initial navigation failed: {str(nav_error)}")
                    # Try a second time with a different approach
                    try:
                        await self.page.goto(
                            'data:text/html,<html></html>',
                            wait_until='domcontentloaded',
                            timeout=30000
                        )
                        logger.info("Successfully loaded data URL")
                    except Exception as fallback_error:
                        logger.error(f"Fallback navigation failed: {str(fallback_error)}")
                        # Try one last time with networkidle
                        try:
                            await self.page.goto(
                                'about:blank',
                                wait_until='networkidle',
                                timeout=45000
                            )
                            logger.info("Successfully loaded with networkidle")
                        except Exception as final_error:
                            logger.error(f"Final navigation attempt failed: {str(final_error)}")
                            raise Exception(f"All navigation attempts failed. Last error: {str(final_error)}")
                
                logger.info("Page navigation test successful")
                
                # Set up basic page configuration
                await self.page.set_viewport_size({"width": 1920, "height": 1080})
                
                # Set up request interception (using the correct Playwright async API)
                await self.page.route('**/*', self._route_handler)
                
                # Get a random user agent
                user_agent = self._get_random_user_agent()
                
                # Apply anti-detection measures
                await self._setup_anti_detection_measures(user_agent)
                
                # Set viewport to a common desktop size
                await self.page.set_viewport_size({"width": 1920, "height": 1080})
                
                logger.info("Browser setup completed successfully")
                return self.browser, self.context, self.page
                
            except Exception as e:
                last_error = e
                logger.error(f"Browser setup attempt {attempt + 1} failed: {str(e)}")
                
                # Clean up any partially created resources
                await self._cleanup_resources()
                
                if attempt < max_retries - 1:
                    retry_delay = (attempt + 1) * 3  # Exponential backoff
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                continue
        
        # If we get here, all retries failed
        logger.error("All browser setup attempts failed")
        if last_error:
            raise last_error
        raise Exception("Failed to set up browser after multiple attempts")
        
    async def scrape(self, search_params: Optional[Dict] = None) -> List[Dict]:
        """Main method to scrape Yad2 car listings with a pattern of 3 cars, then 5s wait.
        
        Args:
            search_params: Optional dictionary of search parameters
            
        Returns:
            List of dictionaries containing scraped listings
        """
        if not self.page:
            await self._setup_browser()
            
        try:
            # Build the search URL based on parameters
            search_url = await self._build_search_url(search_params or {})
            logger.info(f"Starting scrape with URL: {search_url}")
            
            # Navigate to the search URL with retry logic
            max_navigation_attempts = 3
            for attempt in range(max_navigation_attempts):
                if await self._navigate_to_page(self.page, search_url):
                    break
                    
                logger.warning(f"Navigation attempt {attempt + 1}/{max_navigation_attempts} failed")
                if attempt < max_navigation_attempts - 1:
                    # Wait before retrying with increasing delay
                    retry_delay = (attempt + 1) * 2
                    logger.info(f"Retrying navigation in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
            else:
                error_msg = f"Failed to navigate to search URL after {max_navigation_attempts} attempts"
                logger.error(error_msg)
                # Take a screenshot for debugging
                try:
                    await self._take_debug_screenshot(self.page, "navigation_failed")
                except Exception as e:
                    logger.error(f"Failed to take debug screenshot: {str(e)}")
                raise Exception(error_msg)
            
            all_listings = []
            processed_count = 0
            
            while True:
                # Extract a batch of listings (up to 3)
                logger.info(f"Extracting batch of up to 3 listings...")
                batch_listings = await self._extract_page_listings(self.page, limit=3)
                
                if not batch_listings:
                    logger.info("No more listings found")
                    break
                    
                all_listings.extend(batch_listings)
                processed_count += len(batch_listings)
                logger.info(f"Processed {processed_count} listings so far")
                
                # If we got fewer than 3 listings, we've reached the end
                if len(batch_listings) < 3:
                    break
                    
                # Wait for 5 seconds before continuing
                logger.info("Waiting for 5 seconds before next batch...")
                await asyncio.sleep(5)
                
                # Try to go to next page if available
                next_page_url = await self._get_next_page_url(self.page)
                if next_page_url:
                    logger.info(f"Navigating to next page: {next_page_url}")
                    if not await self._navigate_to_page(self.page, next_page_url):
                        logger.warning("Failed to navigate to next page")
                        break
                else:
                    logger.info("No more pages available")
                    break
            
            logger.info(f"Scraping complete. Found {len(all_listings)} listings in total")
            return all_listings
            
        except Exception as e:
            logger.error(f"Error during scraping: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def _build_search_url(self, search_params: Dict) -> str:
        """Build the Yad2 search URL from search parameters."""
        base_url = "https://www.yad2.co.il/vehicles/cars"
        params = []
        
        # Map search parameters to Yad2 URL parameters
        param_mapping = {
            'manufacturer': 'manufacturer',
            'model': 'model',
            'year_from': 'year',
            'price_from': 'price',
            'mileage_from': 'km',
            'location': 'area',
        }
        
        # Apply anti-detection measures
        anti_detection_js = """
        // WebDriver detection override
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            set: undefined,
            configurable: true
        });
        
        // User agent override
        const userAgent = '%s';
        Object.defineProperty(navigator, 'userAgent', {
            get: function() { return userAgent; },
            configurable: true
        });
        
        // Language settings
        Object.defineProperty(navigator, 'language', {
            get: () => 'en-US',
            configurable: true
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
            configurable: true
        """
        # Base URL for car search
        url = f"{self.base_url}/vehicles/cars"
        
        # Default parameters
        params = {
            'manufacturer': search_params.get('manufacturer', ''),
            'model': search_params.get('model', ''),
            'year': f"{search_params.get('year_from', '')}-{search_params.get('year_to', '')}",
            'price': f"{search_params.get('price_from', '')}-{search_params.get('price_to', '')}",
            'hand': search_params.get('hand', ''),
            'km': f"{search_params.get('mileage_from', '')}-{search_params.get('mileage_to', '')}",
            'page': search_params.get('page', 1),
            'forceLdLoad': 'true',
            'ref': 'srch_rslt_cars',
            'searchText': search_params.get('search_text', '')
        }
        
        # Remove empty parameters
        params = {k: v for k, v in params.items() if v and v != '-'}
        
        # Build query string
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        
        return f"{url}?{query}" if query else url
    
    async def _setup_anti_detection_measures(self, user_agent: str) -> None:
        """Apply various anti-detection measures to make the browser appear more human-like.
        
        Args:
            user_agent: The user agent string to use
        """
        try:
            # JavaScript code to override various browser properties
            anti_detection_js = """
            // WebDriver detection override
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                set: undefined,
                configurable: true
            });
            
            // Override the plugins property to prevent detection
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
                configurable: true
            });
            
            // Override the languages property
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true
            });
            
            // Override the platform property
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
                configurable: true
            });
            
            // Override the userAgent property
            Object.defineProperty(navigator, 'userAgent', {
                get: () => '%s',
                configurable: true
            });
            
            // Override the permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => {
                if (parameters.name === 'notifications' || parameters.name === 'geolocation') {
                    return Promise.resolve({ state: 'denied' });
                }
                return originalQuery(parameters);
            };
            
            // Mock common automation detection variables
            Object.defineProperty(window, 'callPhantom', { get: () => undefined });
            Object.defineProperty(window, '_phantom', { get: () => undefined });
            Object.defineProperty(window, 'phantom', { get: () => undefined });
            
            // Mock common test automation frameworks
            Object.defineProperty(window, '__nightmare', { get: () => undefined });
            Object.defineProperty(window, '_selenium', { get: () => undefined });
            Object.defineProperty(window, 'callSelenium', { get: () => undefined });
            
            // Mock common automation extensions
            Object.defineProperty(window, '_Selenium_IDE_Recorder', { get: () => undefined });
            Object.defineProperty(window, 'domAutomation', { get: () => undefined });
            Object.defineProperty(window, 'domAutomationController', { get: () => undefined });
            
            // Set timezone
            const timezone = 'Asia/Jerusalem';
            const timezoneOffset = -180;
            
            // Override timezone for Date object
            const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
            Date.prototype.getTimezoneOffset = function() {
                return timezoneOffset;
            };
            
            // Override timezone for toLocaleString
            const originalToLocaleString = Date.prototype.toLocaleString;
            Date.prototype.toLocaleString = function(locale, options) {
                if (options && options.timeZone) {
                    options.timeZone = timezone;
                }
                return originalToLocaleString.call(this, locale, options);
            };
            
            // Set initial time and timezone offset
            const originalDateNow = Date.now;
            const timeOffset = new Date().getTimezoneOffset() * 60000 + (timezoneOffset * 60000);
            Date.now = function() {
                return originalDateNow.call(Date) - timeOffset;
            };
            """
            
            # Format the JavaScript with the user agent
            anti_detection_js = anti_detection_js % user_agent
            
            # Add the initialization script
            await self.page.add_init_script(anti_detection_js)
            
            # Set geolocation (Tel Aviv coordinates)
            await self.page.context.set_geolocation({
                'latitude': 32.0853,
                'longitude': 34.7818,
                'accuracy': 100
            })
            
        except Exception as e:
            logger.warning(f"Failed to apply some anti-detection measures: {str(e)}")
    
    async def _route_handler(self, route):
        """Handle requests to block unnecessary resources.
        
        In headless mode, blocks images and other resources to improve performance.
        In non-headless mode, allows images to enable CAPTCHA solving.
        """
        request = route.request
        resource_type = request.resource_type.lower()
        
        # Always block these resources regardless of headless mode
        always_blocked = ['font', 'stylesheet', 'media', 'manifest']
        
        # In headless mode, block images for performance
        # In non-headless mode, allow images for CAPTCHA solving
        if self.headless and resource_type == 'image':
            await route.abort()
        elif resource_type in always_blocked:
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
    
    async def _check_for_captcha(self, page: Page) -> bool:
        """Check if a CAPTCHA is present on the page.
        
        Args:
            page: Playwright Page object
            
        Returns:
            bool: True if CAPTCHA is detected, False otherwise or if check fails
        """
        # First check if page is still valid
        if page.is_closed():
            logger.warning("Page is closed, cannot check for CAPTCHA")
            return False
            
        try:
            # Check for common CAPTCHA selectors
            captcha_selectors = [
                'iframe[src*="captcha"]',
                'div.recaptcha',
                'div#captcha',
                'div.captcha-container',
                'iframe[src*="recaptcha"]',
                'div[class*="captcha"]',
                'div[class*="Captcha"]',
                'div[class*="CAPTCHA"]',
                'div[class*="recaptcha"]'
            ]
            
            for selector in captcha_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        # Verify the element is actually visible
                        is_visible = await element.is_visible()
                        if is_visible:
                            logger.warning(f"CAPTCHA detected with selector: {selector}")
                            return True
                except Exception as e:
                    # If we can't check the selector, just continue
                    logger.debug(f"Error checking selector {selector}: {str(e)}")
                    continue
            
            # Check for CAPTCHA in page content if page is still valid
            try:
                content = await page.content()
                if content and ("captcha" in content.lower() or "recaptcha" in content.lower()):
                    logger.warning("CAPTCHA detected in page content")
                    return True
            except Exception as e:
                logger.debug(f"Error checking page content for CAPTCHA: {str(e)}")
                
            return False
            
        except Exception as e:
            # Don't log as error if it's just a navigation issue
            if "context was destroyed" in str(e).lower() or "navigation" in str(e).lower():
                logger.debug(f"Navigation occurred while checking for CAPTCHA: {str(e)}")
            else:
                logger.error(f"Error checking for CAPTCHA: {str(e)}")
            return False
            
    async def _take_debug_screenshot(self, page: Page, prefix: str = "debug") -> None:
        """Take a screenshot for debugging purposes.
        
        Args:
            page: Playwright Page object
            prefix: Prefix for the screenshot filename
        """
        try:
            # Create screenshots directory if it doesn't exist
            os.makedirs("screenshots", exist_ok=True)
            
            # Generate timestamp for unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshots/{prefix}_{timestamp}.png"
            
            # Take full page screenshot
            await page.screenshot(path=filename, full_page=True)
            logger.info(f"Screenshot saved to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to take screenshot: {str(e)}")
    async def _handle_captcha(self, page: Page) -> bool:
        """Handle CAPTCHA if detected.
        
        Args:
            page: Playwright Page object
            
        Returns:
            bool: True if CAPTCHA was handled successfully, False otherwise
        """
        try:
            # Take a screenshot for debugging
            await self._take_debug_screenshot(page, "captcha_detected")
            
            # Log the CAPTCHA detection
            logger.warning("\n" + "="*80)
            logger.warning("CAPTCHA DETECTED - MANUAL SOLVING REQUIRED")
            logger.warning("A browser window should open automatically.")
            logger.warning("If it doesn't open, please check your browser settings.")
            logger.warning("="*80 + "\n")
            
            # Store the current URL before any navigation
            current_url = page.url
            
            # Ensure the browser window is visible
            if self.headless:
                logger.warning("Restarting browser in non-headless mode for CAPTCHA solving...")
                await self._cleanup_resources()
                self.headless = False
                self.browser, self.context, self.page = await self._setup_browser()
                await self._navigate_to_page(self.page, current_url)
                page = self.page
            
            # Bring the page to front and set a reasonable window size
            await page.bring_to_front()
            await page.set_viewport_size({"width": 1366, "height": 768})
            await page.evaluate("window.focus()")
            
            # Take another screenshot after making the window visible
            await self._take_debug_screenshot(page, "captcha_visible")
            
            # First, try to wait for CAPTCHA to be solved automatically
            try:
                logger.info("Waiting for CAPTCHA to be solved automatically...")
                # Wait for CAPTCHA to be solved or for 30 seconds, whichever comes first
                await page.wait_for_function(
                    "() => !document.querySelector('iframe[src*=\"captcha\"], iframe[src*=\"recaptcha\"], .captcha, .g-recaptcha, .recaptcha')",
                    timeout=30000  # 30 seconds
                )
                logger.info("CAPTCHA appears to be solved, continuing...")
                return True
            except Exception as e:
                logger.warning(f"Auto CAPTCHA solve failed: {str(e)}")
            
            # If auto-solve fails, prompt the user
            logger.warning("\n" + "="*80)
            logger.warning("MANUAL CAPTCHA SOLVING REQUIRED")
            logger.warning("1. A browser window should be open with the CAPTCHA visible")
            logger.warning("2. Please solve the CAPTCHA in the browser window")
            logger.warning("3. Wait for the page to load completely")
            logger.warning("4. Press Enter in this terminal when done")
            logger.warning("="*80 + "\n")
            
            # Keep the window focused and visible
            await page.bring_to_front()
            await page.evaluate("window.focus()")
            
            # Wait for user input with a timeout
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    logger.warning("Press Enter to continue after solving the CAPTCHA...")
                    msvcrt.getch()
                else:
                    import select
                    import tty
                    import termios
                    
                    logger.warning("Press any key to continue after solving the CAPTCHA...")
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    try:
                        tty.setraw(sys.stdin.fileno())
                        select.select([sys.stdin], [], [], 300)  # 5 minute timeout
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                
                # Verify CAPTCHA is gone
                logger.info("Verifying CAPTCHA was solved...")
                try:
                    # Wait for navigation to complete after CAPTCHA solve
                    await page.wait_for_load_state('networkidle', timeout=30000)
                    
                    # Check if CAPTCHA is still present
                    captcha_present = await page.evaluate("""
                        () => !!document.querySelector('iframe[src*="captcha"], iframe[src*="recaptcha"], .captcha, .g-recaptcha, .recaptcha')
                    """)
                    
                    if captcha_present:
                        logger.warning("CAPTCHA still detected after manual solve attempt.")
                        return False
                        
                    logger.info("CAPTCHA successfully solved!")
                    self.captcha_solved = True
                    return True
                    
                except Exception as e:
                    logger.error(f"Error verifying CAPTCHA solve: {str(e)}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error waiting for user input: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error in CAPTCHA handling: {str(e)}", exc_info=True)
            return False
            
            # Verify CAPTCHA is really gone
            if await self._check_for_captcha(page):
                logger.warning("WARNING: CAPTCHA still detected after manual solve attempt")
                logger.warning("The scraper will continue but might not work properly.")
                logger.warning("If you see this message repeatedly, the CAPTCHA might not have been solved correctly.")
                return False
                
            logger.info("CAPTCHA solved successfully, continuing...")
            return True
            
        except Exception as e:
            logger.error(f"Error handling CAPTCHA: {str(e)}")
            return False
            
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
            self.state = BrowserState.ERROR
            return False
            
        try:
            self.state = BrowserState.NAVIGATING
            logger.info(f"Navigation sequence starting (attempt {retry_count + 1}/{self.max_retries})")
            
            # Set up request interception to block unnecessary resources
            await page.route('**/*', self._route_handler)
            
            # Randomize viewport size to appear more human-like
            viewport_width = random.randint(1200, 1920)
            viewport_height = random.randint(800, 1080)
            await page.set_viewport_size({"width": viewport_width, "height": viewport_height})
            
            # Set random user agent for each request
            user_agent = self._get_random_user_agent()
            await page.set_extra_http_headers({"User-Agent": user_agent})
            
            # First navigate to rotter.net and wait
            logger.info("Loading initial page (rotter.net) to establish context...")
            try:
                await page.goto(
                    'https://rotter.net',
                    wait_until='domcontentloaded',
                    timeout=30000
                )
                # Reduced wait time to 1 second
                wait_time = 1.0
                logger.info(f"Waiting for {wait_time:.1f} seconds on rotter.net...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.warning(f"Initial navigation to rotter.net failed: {str(e)}")
                if retry_count < self.max_retries - 1:
                    return await self._navigate_to_page(page, url, retry_count + 1)
                return False
            
            # Clear cookies but don't touch localStorage/sessionStorage
            try:
                await page.context.clear_cookies()
            except Exception as e:
                logger.warning(f"Failed to clear cookies: {str(e)}")
            
            # Navigate to the target URL with realistic parameters
            logger.info(f"Navigating to target URL: {url}")
            try:
                await page.goto(
                    url,
                    wait_until='domcontentloaded',
                    timeout=self.timeout,
                    referer='https://rotter.net/'
                )
            except Exception as e:
                logger.error(f"Failed to navigate to {url}: {str(e)}")
                if retry_count < self.max_retries - 1:
                    # Add a small delay before retry
                    await asyncio.sleep(2)
                    return await self._navigate_to_page(page, url, retry_count + 1)
                return False
            
            # Check for CAPTCHA or bot detection
            captcha_detected = await self._check_for_captcha(page)
            if captcha_detected:
                logger.warning("CAPTCHA detected after navigation")
                self.stats['captcha_encounters'] += 1
                if retry_count < self.max_retries - 1:  # Save last retry for different approach
                    await self._handle_captcha(page)
            
            # Wait for the main content to load with multiple fallback selectors
            # Specific to Yad2's structure
            yad2_specific_selectors = [
                'div[data-test-id="feed"]',           # Main feed container
                'div[class*="feed"]',                  # Generic feed container
                'div[class*="list"]',                  # List containers
                'div[class*="results"]',               # Results containers
                'div[class*="items"]',                 # Item containers
                'div[class*="grid"]',                  # Grid layouts
                'div[class*="vehicle"]',               # Vehicle listings
                'div[class*="listing"]',               # Listing containers
                'div[class*="product"]',               # Product containers
                'div[class*="card"]',                  # Card components
                'div[class*="yad2"]',                  # Yad2 specific components
                'div[class*="search-results"]',        # Search results
                'div[class*="searchResults"]',         # Alternative search results
                'div[class*="feed_list"]',             # Feed list
                'div[class*="feed-list"]',             # Feed list alternative
                'div[class*="feedList"]',              # Feed list camelCase
                'div[class*="listings"]',              # Listings container
                'div[class*="listings"]',              # Listings container
                'div[class*="items"]',                 # Items container
                'div[class*="item"]',                  # Item container
                'div[class*="vehicle"]',               # Vehicle container
                'div[class*="car"]',                   # Car container
                'div[class*="auto"]',                  # Auto container
                'div[class*="result"]',                # Result container
                'div[class*="product"]',               # Product container
                'div[class*="card"]',                  # Card container
                'div[class*="tile"]',                  # Tile container
                'div[class*="box"]',                   # Box container
                'div[class*="panel"]',                 # Panel container
                'div[class*="content"]',               # Content container
                'div[class*="main"]',                  # Main container
                'div[class*="container"]',             # Generic container
                'div[class*="wrapper"]',               # Wrapper container
                'div[class*="holder"]',                # Holder container
                'div[class*="section"]',               # Section container
                'div[class*="block"]',                 # Block container
                'div[class*="element"]',               # Element container
                'div[class*="component"]',             # Component container
                'div[class*="module"]',                # Module container
                'div[class*="widget"]',                # Widget container
                'div[class*="yad2"]',                  # Yad2 specific
                'div[class*="y2"]',                    # Yad2 short
                'div[class*="yad"]',                   # Yad2 prefix
                'div[class*="y2d"]'                    # Yad2 alternative
            ]
            
            # Also check for common structural elements
            common_selectors = [
                'main',
                '[role="main"]',
                '#__next',
                '.app-root',
                '.main-content',
                '#main',
                '#content',
                '#container',
                '#wrapper',
                '#page',
                '#app',
                '#root',
                'body',
                'html'
            ]
            
            # Combine all selectors with Yad2 specific ones first
            all_selectors = list(dict.fromkeys(yad2_specific_selectors + common_selectors))
            
            content_found = False
            last_error = None
            
            logger.info("Waiting for content to load...")
            
            # First try with a short timeout for common elements
            for selector in all_selectors:
                try:
                    element = await page.wait_for_selector(
                        selector,
                        timeout=5000,  # Shorter timeout for initial check
                        state="attached"
                    )
                    if element:
                        logger.info(f"Found content with selector: {selector}")
                        content_found = True
                        
                        # Additional check if the element is actually visible and has content
                        is_visible = await element.is_visible()
                        has_content = await element.evaluate('el => el.textContent.trim().length > 0')
                        
                        if is_visible and has_content:
                            logger.debug(f"Selector {selector} has visible content")
                            break
                        else:
                            logger.debug(f"Selector {selector} found but no visible content")
                            content_found = False
                            
                except Exception as e:
                    last_error = str(e)
                    continue
            
            # If no content found, try with a longer timeout
            if not content_found:
                logger.warning("Initial content check failed, trying with longer timeout...")
                for selector in all_selectors:
                    try:
                        element = await page.wait_for_selector(
                            selector,
                            timeout=15000,  # Longer timeout for second attempt
                            state="attached"
                        )
                        if element:
                            logger.info(f"Found content with selector (longer timeout): {selector}")
                            content_found = True
                            break
                    except Exception as e:
                        last_error = str(e)
                        continue
            
            if not content_found:
                logger.warning(f"Could not find main content with any selector. Last error: {last_error}")
                # Take a screenshot for debugging
                await self._take_debug_screenshot(page, "content_not_found")
                
                # Try to get some diagnostic information
                try:
                    page_title = await page.title()
                    logger.info(f"Page title: {page_title}")
                    
                    # Check for common error pages
                    if any(term in page_title.lower() for term in ['error', 'blocked', 'access denied', 'captcha']):
                        logger.error("Detected error/blocked page")
                        return False
                        
                    # Check for redirects
                    current_url = page.url
                    if 'login' in current_url or 'auth' in current_url or 'block' in current_url:
                        logger.error(f"Redirected to potential blocking page: {current_url}")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error getting page info: {str(e)}")
                
                return False
            
            # Check if we were redirected to a login or error page
            current_url = page.url
            if 'login' in current_url or 'error' in current_url:
                logger.warning(f"Redirected to {current_url}, possible bot detection")
                self.state = BrowserState.ERROR
                return False
            
            self.state = BrowserState.NAVIGATION_COMPLETE
            return True
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout while navigating to {url}: {str(e)}")
            self.state = BrowserState.ERROR
            if retry_count < self.max_retries - 1:
                logger.info(f"Retrying navigation (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(5)  # Wait before retry
                return await self._navigate_to_page(page, url, retry_count + 1)
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to {url}: {str(e)}")
            self.state = BrowserState.ERROR
            if retry_count < self.max_retries - 1:
                logger.info(f"Retrying navigation (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(5)  # Wait before retry
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
        
    async def _cleanup(self):
        """Clean up browser resources."""
        try:
            # Close page if it exists and is not already closed
            if hasattr(self, 'page') and self.page:
                try:
                    if not self.page.is_closed():
                        await self.page.close()
                    self.page = None
                except Exception as e:
                    logger.warning(f"Error closing page: {str(e)}")
            
            # Close context if it exists
            if hasattr(self, 'context') and self.context:
                try:
                    await self.context.close()
                    self.context = None
                except Exception as e:
                    logger.warning(f"Error closing context: {str(e)}")
            
            # Close browser if it exists
            if hasattr(self, 'browser') and self.browser:
                try:
                    await self.browser.close()
                    self.browser = None
                except Exception as e:
                    logger.warning(f"Error closing browser: {str(e)}")
            
            # Stop Playwright if it exists
            if hasattr(self, 'playwright') and self.playwright:
                try:
                    await self.playwright.stop()
                    self.playwright = None
                except Exception as e:
                    logger.warning(f"Error stopping Playwright: {str(e)}")
            
            # Reset state
            self.state = BrowserState.INITIALIZING
            
            # Add a small delay to ensure resources are properly released
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
            # Even if cleanup fails, we should reset the state
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            self.state = BrowserState.INITIALIZING
    
    async def _extract_listing_data(self, item: ElementHandle) -> Optional[Dict[str, Any]]:
        """Extract data from a single listing element.
        
{{ ... }}
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
    
    async def _extract_page_listings(self, page: Page, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Extract listings from the current page with an optional limit.
        
        Args:
            page: Playwright Page object
            limit: Maximum number of listings to return (None for all)
            
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
        logger.info(f"Detected search results page, extracting up to {limit if limit else 'all'} listings")
        
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
            
        # Extract data from each listing, respecting the limit
        extracted = 0
        max_items = min(limit, len(items)) if limit is not None else len(items)
        
        for i, item in enumerate(items):
            # Stop if we've reached the limit
            if limit is not None and extracted >= limit:
                logger.info(f"Reached the limit of {limit} listings")
                break
                
            try:
                # Scroll the item into view
                await item.scroll_into_view_if_needed()
                
                # Add a small random delay between processing listings
                delay = random.uniform(0.5, 1.5)
                logger.debug(f"Waiting {delay:.2f}s before processing next listing...")
                await asyncio.sleep(delay)
                
                # Try to extract the listing data
                listing_data = await self._extract_listing_data(item)
                if listing_data:
                    listings.append(listing_data)
                    extracted += 1
                    
                    # Log progress
                    logger.info(f"Extracted listing {extracted}/{max_items}")
                    
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
            
            # Extract brand and model from title if available
            brand = ''
            model = ''
            if title:
                parts = title.split()
                if parts:
                    brand = parts[0]
                    if len(parts) > 1:
                        model = ' '.join(parts[1:])
            
            # Construct and return the listing dictionary
            return {
                'id': listing_id,
                'title': title,
                'price': price,
                'url': url,
                'year': year,
                'mileage': mileage,
                'location': location,
                'description': description,
                'fuel_type': fuel_type,
                'transmission': transmission,
                'body_type': body_type,
                'color': color,
                'brand': brand,
                'model': model
            }
            
        except Exception as e:
            logger.error(f"Error parsing listing: {str(e)}")
            return None
            
    async def _extract_listings_from_api(self, page: Page) -> List[Dict]:
        """Extract listings from the Yad2 API if available.
        
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
                search_url = await self._build_search_url(search_params)
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

async def normalize_and_store(self, listings: List[Dict]) -> None:
    """Normalize and store the scraped listings in the database."""
    if not listings:
        return
        
    from app.db.session import SessionLocal
    from app.models.car_listing import CarListing as CarListingModel
    
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

    def _build_search_url(self, params: Dict) -> str:
        """Build the search URL with the given parameters.
        
        Args:
            params: Dictionary of search parameters
            
        Returns:
            str: The complete search URL with query parameters
        """
        base_url = f"{self.base_url}/vehicles/cars"
        query_parts = []
        
        # Add manufacturer if provided
        if 'manufacturer' in params and params['manufacturer']:
            query_parts.append(f'manufacturer={params["manufacturer"]}')
            
        # Add model if provided
        if 'model' in params and params['model']:
            query_parts.append(f'model={params["model"]}')
            
        # Add year range if provided
        if 'year_from' in params and params['year_from']:
            query_parts.append(f'year_from={params["year_from"]}')
        if 'year_to' in params and params['year_to']:
            query_parts.append(f'year_to={params["year_to"]}')
            
        # Add price range if provided
        if 'price_from' in params and params['price_from']:
            query_parts.append(f'price_from={params["price_from"]}')
        if 'price_to' in params and params['price_to']:
            query_parts.append(f'price_to={params["price_to"]}')
            
        # Add mileage range if provided
        if 'mileage_from' in params and params['mileage_from']:
            query_parts.append(f'mileage_from={params["mileage_from"]}')
        if 'mileage_to' in params and params['mileage_to']:
            query_parts.append(f'mileage_to={params["mileage_to"]}')
            
        # Add location if provided
        if 'location' in params and params['location']:
            query_parts.append(f'location={params["location"]}')
            
        # Page number
        if 'page' in params and int(params['page']) > 1:
            query_parts.append(f'page={params["page"]}')
        
        # Combine all query parameters
        if query_parts:
            return f"{base_url}?{'&'.join(query_parts)}"
            
        return base_url


# Example usage
async def main() -> None:
    """Example usage of the Yad2Scraper class."""
    import asyncio
    from datetime import datetime
    import logging
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'yad2_scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )
    
    # Define search parameters
    search_params = {
        'manufacturer': 'Toyota',
        'model': 'Corolla',
        'year_from': 2015,
        'year_to': 2020,
        'price_from': 40000,
        'price_to': 100000,
        'mileage_from': 0,
        'mileage_to': 100000,
        'location': 'תל אביב',
        'page': 1,
        'max_pages': 2
    }
    
    # Create and run the scraper
    scraper = Yad2Scraper(headless=False, slow_mo=100)
    
    try:
        async with scraper as scraper_ctx:
            results = await scraper_ctx.scrape(search_params=search_params)
            print(f"Scraped {len(results)} listings")
            
            # Print the first few results
            for i, result in enumerate(results[:5], 1):
                print(f"\nResult {i}:")
                for key, value in result.items():
                    print(f"  {key}: {value}")
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}", exc_info=True)
    finally:
        await scraper._cleanup()


if __name__ == "__main__":
    # Run the scraper
    asyncio.run(main())
