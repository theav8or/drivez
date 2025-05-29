#!/usr/bin/env python3
"""
Script to run the Yad2 scraper and fetch car listings.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.scrapers.yad2_updated import Yad2Scraper
from app.db.session import SessionLocal
from app.db.models.car import CarListing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Run the Yad2 scraper and fetch car listings."""
    # Initialize the scraper with headless mode and debugging
    scraper = Yad2Scraper(
        headless=True,  # Run in headless mode
        max_retries=3,
        slow_mo=100,  # Slow down Playwright operations
        user_data_dir="/tmp/playwright_data"  # Use a persistent user data directory
    )
    
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        # Run the scraper with search parameters
        search_params = {
            'page': 1,
            'max_pages': 2,  # Fetch 2 pages (20-40 listings)
            'price_from': 50000,  # Filter by price range
            'price_to': 200000,
            'year_from': 2015,  # Filter by year
            'mileage_to': 100000,  # Filter by max mileage
        }
        
        logger.info("Starting Yad2 scraper...")
        listings = await scraper.scrape(search_params)
        
        if not listings:
            logger.warning("No listings found or an error occurred while scraping.")
            return
            
        logger.info(f"Successfully scraped {len(listings)} listings.")
        
        # Print some statistics
        unique_listings = {listing['yad2_id']: listing for listing in listings}.values()
        logger.info(f"Unique listings: {len(unique_listings)}")
        
        # Print sample data
        for i, listing in enumerate(list(unique_listings)[:3]):
            logger.info(f"Listing {i+1}:")
            logger.info(f"  Title: {listing.get('title')}")
            logger.info(f"  Price: {listing.get('price')}₪")
            logger.info(f"  Year: {listing.get('year')}")
            logger.info(f"  Mileage: {listing.get('mileage')}km")
            logger.info(f"  Image URL: {listing.get('image_url', 'N/A')}")
            logger.info(f"  URL: {listing.get('url')}")
        
        # Save to database
        db = SessionLocal()
        try:
            new_count = 0
            updated_count = 0
            
            for listing in unique_listings:
                # Check if listing already exists
                db_listing = db.query(CarListing).filter(
                    CarListing.yad2_id == listing['yad2_id']
                ).first()
                
                if db_listing:
                    # Update existing listing
                    for key, value in listing.items():
                        if hasattr(db_listing, key) and key != 'id':
                            setattr(db_listing, key, value)
                    updated_count += 1
                else:
                    # Create new listing
                    db_listing = CarListing(**listing)
                    db.add(db_listing)
                    new_count += 1
            
            db.commit()
            logger.info(f"Database updated: {new_count} new listings, {updated_count} updated listings")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating database: {str(e)}")
            raise
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise
    
    finally:
        # Clean up resources
        await scraper._cleanup()

if __name__ == "__main__":
    asyncio.run(main())
