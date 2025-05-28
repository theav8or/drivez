import asyncio
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
from app.core.config import settings
from app.db.models import CarListing
from app.services.normalization import normalize_car_data
import rapidfuzz
import json
import logging

logger = logging.getLogger(__name__)

class Yad2Scraper:
    def __init__(self):
        self.base_url = "https://www.yad2.co.il"
        self.search_url = f"{self.base_url}/cars"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def scrape_listings(self) -> List[Dict]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                await page.goto(self.search_url, wait_until="networkidle")
                
                # Wait for listings to load
                await page.wait_for_selector(".item-line")
                
                # Extract listings
                listings = []
                items = await page.query_selector_all(".item-line")
                
                for item in items:
                    try:
                        listing = await self._extract_listing_data(item)
                        if listing:
                            listings.append(listing)
                    except Exception as e:
                        logger.error(f"Error extracting listing: {str(e)}")
                        continue
                
                return listings
            finally:
                await browser.close()

    async def _extract_listing_data(self, item) -> Optional[Dict]:
        try:
            title = await item.query_selector(".title-cell")
            if not title:
                return None
            
            title_text = await title.text_content()
            
            # Extract other fields
            price_elem = await item.query_selector(".price-cell")
            price = await price_elem.text_content() if price_elem else None
            
            link = await item.query_selector("a")
            url = f"{self.base_url}{await link.get_attribute('href')}" if link else None
            
            return {
                "title": title_text,
                "price": price,
                "url": url,
                "source": "yad2"
            }
        except Exception as e:
            logger.error(f"Error extracting data: {str(e)}")
            return None

    async def normalize_and_store(self, listings: List[Dict]):
        normalized_listings = []
        
        for listing in listings:
            try:
                normalized = normalize_car_data(listing)
                if normalized:
                    normalized_listings.append(normalized)
            except Exception as e:
                logger.error(f"Error normalizing listing: {str(e)}")
                continue
        
        # Store in database
        # TODO: Implement database storage
        return normalized_listings
