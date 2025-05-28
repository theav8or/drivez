import asyncio
import random
import logging
import re
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from app.core.config import settings
from app.db.models import CarListing, CarBrand, CarModel
from app.services.normalization import normalize_car_data

logger = logging.getLogger(__name__)

class Yad2Scraper:
    def __init__(self):
        self.base_url = "https://www.yad2.co.il"
        self.search_url = f"{self.base_url}/vehicles/cars"
        self.timeout = 60000  # 60 seconds timeout
        self.max_retries = 3
        self.delay_range = (2, 5)  # Random delay between requests in seconds
        self.processed_urls = set()  # Track processed URLs to avoid duplicates
        
        # Browser context settings
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
            '--disable-site-isolation-trials'
        ]
        
        # Realistic headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
    
    async def _get_random_delay(self) -> float:
        """Return a random delay between requests to avoid being blocked."""
        return random.uniform(*self.delay_range)

    async def _navigate_to_page(self, page, url: str, retry_count: int = 0) -> bool:
        """Navigate to a URL with retry logic."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            # Wait for the page to be fully loaded
            await page.wait_for_load_state("networkidle")
            
            # Check for bot detection
            if await page.query_selector("text=Please verify you are a human"):
                logger.warning("Bot detection triggered, solving challenge...")
                await asyncio.sleep(5)  # Wait for challenge to load
                # Try to bypass the challenge by clicking the verify button if it exists
                verify_btn = await page.query_selector("button:has-text('Verify') or button:has-text('I am not a robot')")
                if verify_btn:
                    await verify_btn.click()
                    await asyncio.sleep(5)  # Wait for verification
            
            return True
            
        except PlaywrightTimeoutError:
            if retry_count < self.max_retries:
                logger.warning(f"Timeout loading {url}, retrying... (Attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(await self._get_random_delay() * 2)  # Longer delay on retry
                return await self._navigate_to_page(page, url, retry_count + 1)
            logger.error(f"Failed to load {url} after {self.max_retries} attempts")
            return False
        except Exception as e:
            logger.error(f"Error navigating to {url}: {str(e)}")
            return False


                
                # Extract listings from current page
                page_listings = await self._extract_page_listings(page)
                all_listings.extend(page_listings)
                
                # Handle pagination
                next_page_url = await self._get_next_page_url(page, 1)
                page_num = 2
                
                while next_page_url and page_num <= 3:  # Limit to 3 pages for testing
                    logger.info(f"Navigating to page {page_num}...")
                    await asyncio.sleep(await self._get_random_delay())
                    
                    if not await self._navigate_to_page(page, next_page_url):
                        logger.warning(f"Failed to load page {page_num}")
                        break
                    
                    # Extract listings from current page
                    page_listings = await self._extract_page_listings(page)
                    if not page_listings:
                        logger.warning(f"No listings found on page {page_num}")
                        break
                        
                    all_listings.extend(page_listings)
                    next_page_url = await self._get_next_page_url(page, page_num)
                    page_num += 1
                
                logger.info(f"Scraped {len(all_listings)} listings in total")
                
            except Exception as e:
                logger.error(f"Error during scraping: {str(e)}", exc_info=True)
            
            finally:
                await context.close()
                await browser.close()
        
        return all_listings

    async def _get_next_page_url(self, page, current_page: int) -> Optional[str]:
        """Find the URL for the next page of results."""
        try:
            # Look for pagination links
            next_btn = await page.query_selector('a[data-role="next_page"]')
            if next_btn:
                href = await next_btn.get_attribute('href')
                if href and '/vehicles/cars' in href:
                    return urljoin(self.base_url, href)
            
            # Alternative pagination method
            pages = await page.query_selector_all('.pagination a')
            for page_el in pages:
                page_num = await page_el.text_content()
                if page_num and page_num.strip().isdigit() and int(page_num.strip()) == current_page + 1:
                    href = await page_el.get_attribute('href')
                    if href and '/vehicles/cars' in href:
                        return urljoin(self.base_url, href)
            
            return None
            
        except Exception as e:
            logger.warning(f"Error finding next page URL: {str(e)}")
            return None

    async def _extract_page_listings(self, page) -> List[Dict]:
        """Extract all listings from the current page."""
        listings = []
        try:
            # Wait for listings to be visible
            await page.wait_for_selector('[data-test-id="feed_item"]', timeout=10000)
            
            # Get all listing elements
            items = await page.query_selector_all('[data-test-id="feed_item"]')
            
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
        """Extract data from a single listing element."""
        try:
            # Extract basic info
            title_elem = await item.query_selector('[data-test-id="title"]')
            title = await title_elem.text_content() if title_elem else ""
            
            price_elem = await item.query_selector('[data-test-id="price"]')
            price_text = await price_elem.text_content() if price_elem else ""
            price = int(re.sub(r'[^0-9]', '', price_text)) if price_text else 0
            
            # Extract details
            details = {}
            detail_elems = await item.query_selector_all('.feed_item_info')
            for elem in detail_elems:
                try:
                    label_elem = await elem.query_selector('.field_title')
                    value_elem = await elem.query_selector('.value')
                    
                    if label_elem and value_elem:
                        label = (await label_elem.text_content() or "").strip().lower()
                        value = (await value_elem.text_content() or "").strip()
                        if label and value:
                            details[label] = value
                except:
                    continue
            
            # Extract URL
            link_elem = await item.query_selector('a')
            url = await link_elem.get_attribute('href') if link_elem else ""
            if url and not url.startswith('http'):
                url = urljoin(self.base_url, url)
            
            # Create listing dict
            listing = {
                'source': 'yad2',
                'source_id': url.split('/')[-1] if url else "",
                'url': url,
                'title': title.strip(),
                'price': price,
                'year': int(details.get('year', '0')) if details.get('year', '0').isdigit() else 0,
                'mileage': int(re.sub(r'[^0-9]', '', details.get('mileage', '0'))) if details.get('mileage') else 0,
                'location': details.get('location', ''),
                'description': '',  # Will be filled in detailed view
                'fuel_type': details.get('fuel', ''),
                'transmission': details.get('transmission', ''),
                'body_type': details.get('body', ''),
                'color': details.get('color', ''),
                'brand': '',  # Will be extracted from title
                'model': '',   # Will be extracted from title
                'raw_data': json.dumps(details, ensure_ascii=False)
            }
            
            # Extract brand and model from title if possible
            if title:
                title_parts = title.split()
                if len(title_parts) >= 2:
                    listing['brand'] = title_parts[0]
                    listing['model'] = ' '.join(title_parts[1:])
            
            return listing
            
        except Exception as e:
            logger.warning(f"Error extracting listing data: {str(e)}")
            return None

    async def normalize_and_store(self, listings: List[Dict]) -> None:
        """Normalize and store the scraped listings in the database."""
        if not listings:
            return
            
        db = SessionLocal()
        try:
            for listing in listings:
                try:
                    # Check if listing already exists
                    existing = db.query(CarListing).filter(
                        CarListing.source == 'yad2',
                        CarListing.source_id == listing.get('source_id')
                    ).first()
                    
                    if not existing:
                        # Create new listing
                        db_listing = CarListing(**listing)
                        db.add(db_listing)
                    else:
                        # Update existing listing
                        for key, value in listing.items():
                            if hasattr(existing, key) and key != 'id':
                                setattr(existing, key, value)
                except Exception as e:
                    logger.error(f"Error saving listing: {str(e)}")
                    continue
            
            db.commit()
            logger.info(f"Successfully saved {len(listings)} listings to database")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in database operation: {str(e)}")
        finally:
            db.close()
