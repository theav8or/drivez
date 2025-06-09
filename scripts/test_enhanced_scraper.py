#!/usr/bin/env python3
"""
Test script for the enhanced Yad2 scraper with database integration.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraper_test.log')
    ]
)
logger = logging.getLogger(__name__)

async def test_scraper():
    """Test the enhanced Yad2 scraper."""
    from app.scrapers.yad2_enhanced import Yad2ScraperEnhanced
    from app.db.session import SessionLocal
    from sqlalchemy import select
    from app.db.models.car import CarListing
    
    db = SessionLocal()
    
    try:
        # Count existing listings
        count_before = db.scalar(select([func.count()]).select_from(CarListing))
        logger.info(f"Found {count_before} existing listings in the database")
        
        # Run the scraper
        max_listings = 5  # Keep it small for testing
        logger.info(f"Starting scraper to fetch up to {max_listings} listings...")
        
        async with Yad2ScraperEnhanced(headless=False, max_listings=max_listings) as scraper:
            listings = await scraper.scrape_listings()
            logger.info(f"Successfully scraped {len(listings)} listings")
            
            # Verify data was saved to the database
            count_after = db.scalar(select([func.count()]).select_from(CarListing))
            new_listings = count_after - count_before
            logger.info(f"Added {new_listings} new listings to the database")
            
            # Print a sample of the scraped data
            if new_listings > 0:
                latest = db.execute(
                    select(CarListing)
                    .order_by(CarListing.scraped_at.desc())
                    .limit(1)
                ).scalars().first()
                
                if latest:
                    logger.info("\nLatest listing added:")
                    logger.info(f"  Title: {latest.title}")
                    logger.info(f"  Price: {latest.price}")
                    logger.info(f"  Year: {latest.year}")
                    logger.info(f"  Mileage: {latest.mileage}")
                    logger.info(f"  Location: {latest.location}")
                    logger.info(f"  URL: {latest.url}")
            
            return True
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        return False
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Starting Yad2 scraper test...")
    success = asyncio.run(test_scraper())
    if success:
        logger.info("Test completed successfully")
    else:
        logger.error("Test failed")
        sys.exit(1)
