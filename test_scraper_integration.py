import asyncio
import logging
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.scrapers.yad2_new import Yad2Scraper
from app.db.session import SessionLocal
from app.db.models.car import CarListing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_scraper():
    """Test the Yad2 scraper integration."""
    db = SessionLocal()
    try:
        logger.info("Starting Yad2 scraper test...")
        
        # Initialize the scraper
        scraper = Yad2Scraper()
        
        # Run the scraper
        listings = await scraper.scrape_listings()
        logger.info(f"Found {len(listings)} listings")
        
        if listings:
            logger.info(f"First listing: {listings[0]}")
            
            # Test saving to database
            logger.info("Saving listings to database...")
            await scraper.normalize_and_store(listings)
            
            # Verify the data was saved
            count = db.query(CarListing).count()
            logger.info(f"Total listings in database: {count}")
            
            if count > 0:
                latest = db.query(CarListing).order_by(CarListing.created_at.desc()).first()
                logger.info(f"Latest listing: {latest.title} - {latest.price}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in test_scraper: {str(e)}", exc_info=True)
        return False
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_scraper())
