from app.scrapers.yad2 import Yad2Scraper
from app.db.session import SessionLocal
from app.db.models import CarListing
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Type
import asyncio
import time
import logging
from datetime import datetime
from app.config.scraping import ScrapingSettings
from app.services.normalization import normalize_car_data
from app.core.caching import cache
from app.exceptions.scraping import ScrapingError, FatalError
from app.utils.error_handling import ErrorHandler

logger = logging.getLogger(__name__)
settings = ScrapingSettings()

class ScrapingService:
    def __init__(self):
        self.yad2_scraper = Yad2Scraper()
        self._last_request_time = 0
        self._retry_count = 0

    @staticmethod
    def _get_random_delay() -> float:
        """Get a random delay between min and max delay settings"""
        import random
        return random.uniform(
            settings.MIN_DELAY_BETWEEN_REQUESTS,
            settings.MAX_DELAY_BETWEEN_REQUESTS
        )

    async def _rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        delay = self._get_random_delay()
        
        if current_time - self._last_request_time < delay:
            await asyncio.sleep(delay - (current_time - self._last_request_time))
        
        self._last_request_time = time.time()

    async def _retry_with_backoff(self, func: Type[callable], *args, **kwargs) -> Optional[any]:
        """Retry a function with sophisticated error handling"""
        for attempt in range(settings.MAX_RETRIES):
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                scraping_error = ErrorHandler.handle_scraping_error(e, retryable=True)
                
                if not ErrorHandler.should_retry(scraping_error):
                    raise scraping_error
                    
                delay = ErrorHandler.get_retry_delay(scraping_error, attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {str(scraping_error)}. Retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                
                # Adjust rate limits if we're hitting them frequently
                if isinstance(scraping_error, RateLimitError):
                    self._adjust_rate_limits()

    async def _process_listing(self, db: Session, listing_data: Dict) -> Optional[CarListing]:
        """Process a single listing with sophisticated error handling"""
        try:
            # Normalize the data
            normalized_data = normalize_car_data(listing_data)
            
            # Check if listing already exists
            existing_listing = db.query(CarListing).filter_by(yad2_id=normalized_data['yad2_id']).first()
            
            if existing_listing:
                # Update existing listing
                for key, value in normalized_data.items():
                    setattr(existing_listing, key, value)
                existing_listing.last_scraped_at = datetime.utcnow()
                return existing_listing
            
            # Create new listing
            new_listing = CarListing(**normalized_data)
            new_listing.last_scraped_at = datetime.utcnow()
            return new_listing
            
        except Exception as e:
            scraping_error = ErrorHandler.handle_scraping_error(e, retryable=False)
            if isinstance(scraping_error, FatalError):
                raise scraping_error
            logger.error(f"Error processing listing: {str(scraping_error)}")
            return None

    async def _adjust_rate_limits(self):
        """Adjust rate limits if we're hitting them too frequently"""
        current_delay = settings.MAX_DELAY_BETWEEN_REQUESTS
        settings.MAX_DELAY_BETWEEN_REQUESTS = min(current_delay * 1.5, 10.0)  # Cap at 10 seconds
        settings.MIN_DELAY_BETWEEN_REQUESTS = min(current_delay * 1.2, 5.0)  # Cap at 5 seconds
        logger.warning(f"Adjusted rate limits: min={settings.MIN_DELAY_BETWEEN_REQUESTS}s, max={settings.MAX_DELAY_BETWEEN_REQUESTS}s")

    async def trigger_scrape_yad2(self, db: Session):
        """
        Trigger a scraping job for Yad2.co.il with sophisticated error handling.
        Implements rate limiting, retries, and caching.
        """
        try:
            # Get listings with retries
            listings = await self._retry_with_backoff(
                self.yad2_scraper.scrape_listings
            )
            
            if not listings:
                logger.warning("No listings found")
                return
                
            processed_listings = []
            
            for listing_data in listings:
                await self._rate_limit()  # Rate limit between requests
                
                try:
                    listing = await self._process_listing(db, listing_data)
                    if listing:
                        processed_listings.append(listing)
                except Exception as e:
                    scraping_error = ErrorHandler.handle_scraping_error(e)
                    if isinstance(scraping_error, RateLimitError):
                        # If we hit rate limits during processing, adjust and retry
                        await self._adjust_rate_limits()
                        await asyncio.sleep(settings.MAX_DELAY_BETWEEN_REQUESTS)
                        continue
                    logger.error(f"Failed to process listing: {str(scraping_error)}")
                    
            # Bulk save listings
            if processed_listings:
                try:
                    db.add_all(processed_listings)
                    db.commit()
                    logger.info(f"Successfully processed {len(processed_listings)} listings")
                except Exception as e:
                    scraping_error = ErrorHandler.handle_scraping_error(e)
                    logger.error(f"Database error: {str(scraping_error)}")
                    db.rollback()
                    raise scraping_error
            
        except Exception as e:
            scraping_error = ErrorHandler.handle_scraping_error(e)
            logger.error(f"Scraping failed: {str(scraping_error)}")
            db.rollback()
            raise scraping_error
