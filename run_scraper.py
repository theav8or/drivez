#!/usr/bin/env python3
"""
Script to run the Yad2 car listings scraper and save results to the database.
"""
import asyncio
import logging
from app.scrapers.yad2_updated import Yad2Scraper
from app.db.session import SessionLocal
from app.db.models.car import CarListing
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraper.log')
    ]
)
logger = logging.getLogger(__name__)

async def save_listings_to_db(listings: list[dict]) -> None:
    """Save scraped listings to the database."""
    db = SessionLocal()
    try:
        for listing_data in listings:
            try:
                # Check if listing already exists
                existing = db.query(CarListing).filter_by(
                    source=listing_data['source'],
                    source_id=listing_data['source_id']
                ).first()
                
                if existing:
                    # Update existing listing
                    for key, value in listing_data.items():
                        if hasattr(existing, key) and key != 'id':
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                    logger.info(f"Updated listing: {listing_data['title']}")
                else:
                    # Create new listing
                    listing = CarListing(**listing_data)
                    db.add(listing)
                    logger.info(f"Added new listing: {listing_data['title']}")
                
                # Commit after each listing to ensure data is saved
                db.commit()
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error saving listing {listing_data.get('title', 'unknown')}: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        db.rollback()
    finally:
        db.close()

async def main():
    """Main function to run the scraper."""
    logger.info("Starting Yad2 car listings scraper...")
    
    try:
        # Initialize scraper
        scraper = Yad2Scraper()
        
        # Scrape all available listings
        logger.info("Starting to scrape all available car listings...")
        listings = await scraper.scrape()
        
        if not listings:
            logger.warning("No listings found!")
            return
            
        logger.info(f"Scraped {len(listings)} listings. Saving to database...")
        
        # Save to database
        await save_listings_to_db(listings)
        
        logger.info("Scraping completed successfully!")
        
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
