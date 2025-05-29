#!/usr/bin/env python3
"""
Script to run the Yad2 car listings scraper and save results to the database.
"""
import asyncio
import logging
import argparse
from typing import List, Dict, Any
from datetime import datetime

from app.scrapers.yad2_api_scraper import Yad2ApiScraper
from app.db.session import SessionLocal
from app.db.models.car import CarListing

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

async def save_listings_to_db(listings: List[Dict[str, Any]]) -> None:
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
        logger.error(f"Error saving listing to database: {str(e)}")
        db.rollback()
        
    finally:
        db.close()

async def main():
    """Main function to run the scraper."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scrape car listings from Yad2')
    parser.add_argument('--max-pages', type=int, default=3, help='Maximum number of pages to scrape')
    parser.add_argument('--limit', type=int, default=25, help='Maximum number of listings to fetch')
    parser.add_argument('--manufacturer', type=str, help='Filter by car manufacturer')
    parser.add_argument('--model', type=str, help='Filter by car model')
    parser.add_argument('--year-min', type=int, help='Minimum year filter')
    parser.add_argument('--year-max', type=int, help='Maximum year filter')
    parser.add_argument('--price-min', type=int, help='Minimum price filter')
    parser.add_argument('--price-max', type=int, help='Maximum price filter')
    
    args = parser.parse_args()
    
    # Build search parameters
    search_params = {}
    if args.manufacturer:
        search_params['manufacturer'] = args.manufacturer
    if args.model:
        search_params['model'] = args.model
    if args.year_min or args.year_max:
        year_range = []
        if args.year_min:
            year_range.append(str(args.year_min))
        else:
            year_range.append('')
        year_range.append('-')
        if args.year_max:
            year_range.append(str(args.year_max))
        search_params['year'] = ''.join(year_range)
    if args.price_min or args.price_max:
        price_range = []
        if args.price_min:
            price_range.append(str(args.price_min))
        else:
            price_range.append('')
        price_range.append('-')
        if args.price_max:
            price_range.append(str(args.price_max))
        search_params['price'] = ''.join(price_range)
    
    logger.info("Starting Yad2 car listings scraper...")
    logger.info(f"Search parameters: {search_params}")
    
    try:
        async with Yad2ApiScraper(
            max_pages=args.max_pages,
            limit=args.limit,
            max_retries=3,
            delay_range=(1, 3)
        ) as scraper:
            # Start scraping
            logger.info("Starting to fetch car listings...")
            listings = await scraper.get_car_listings(search_params)
            
            # Save listings to database
            if listings:
                logger.info(f"Found {len(listings)} listings. Saving to database...")
                await save_listings_to_db(listings)
                logger.info("Successfully saved all listings to database")
            else:
                logger.warning("No listings found!")
                
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
