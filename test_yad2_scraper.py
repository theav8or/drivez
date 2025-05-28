#!/usr/bin/env python3
"""
Test script for the Yad2 scraper.

This script tests the Yad2Scraper class by:
1. Scraping a few pages of car listings
2. Printing the results
3. Saving the results to a JSON file
"""
import asyncio
import json
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.scrapers.yad2_updated import Yad2Scraper
from app.db.session import SessionLocal

def save_results(listings: list, filename: str = None):
    """Save the scraped listings to a JSON file."""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"yad2_listings_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(listings, f, ensure_ascii=False, indent=2, default=str)
    
    logger.info(f"Saved {len(listings)} listings to {filename}")

async def test_scraper():
    """Test the Yad2 scraper."""
    logger.info("Starting Yad2 scraper test...")
    
    # Initialize the scraper
    scraper = Yad2Scraper()
    
    try:
        # Scrape listings
        logger.info("Scraping Yad2 car listings...")
        listings = await scraper.scrape_listings()
        
        if not listings:
            logger.warning("No listings were scraped")
            return
        
        # Print a summary
        logger.info(f"Scraped {len(listings)} listings")
        
        # Print the first few listings
        for i, listing in enumerate(listings[:3], 1):
            logger.info(f"Listing {i}:")
            logger.info(f"  Title: {listing.get('title')}")
            logger.info(f"  Price: {listing.get('price')}")
            logger.info(f"  Year: {listing.get('year')}")
            logger.info(f"  Mileage: {listing.get('mileage')}")
            logger.info(f"  Location: {listing.get('location')}")
            logger.info(f"  URL: {listing.get('url')}")
            logger.info("-" * 50)
        
        # Save all listings to a JSON file
        save_results(listings)
        
        # Test saving to database
        logger.info("Saving listings to database...")
        await scraper.normalize_and_store(listings)
        logger.info("Listings saved to database")
        
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}", exc_info=True)
    finally:
        logger.info("Test completed")

if __name__ == "__main__":
    asyncio.run(test_scraper())
