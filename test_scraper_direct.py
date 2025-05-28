import asyncio
import logging
from app.scrapers.yad2 import Yad2Scraper
from app.db.session import SessionLocal

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_scraper():
    db = SessionLocal()
    try:
        logger.info("Starting Yad2 scraper test...")
        scraper = Yad2Scraper()
        
        # Scrape a few pages
        logger.info("Scraping listings...")
        listings = await scraper.scrape_listings()
        
        logger.info(f"Found {len(listings)} listings")
        if listings:
            logger.info(f"First listing: {listings[0]}")
        
        return True
    except Exception as e:
        logger.error(f"Error in test_scraper: {str(e)}", exc_info=True)
        return False
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_scraper())
