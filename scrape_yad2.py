#!/usr/bin/env python3
"""
Script to scrape car listings from Yad2 using the Yad2Scraper class.
"""
import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Any

from app.scrapers.yad2_updated import Yad2Scraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('yad2_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

async def scrape_yad2_listings(limit: int = 25) -> List[Dict[str, Any]]:
    """
    Scrape car listings from Yad2.
    
    Args:
        limit: Maximum number of listings to fetch
        
    Returns:
        List of scraped car listings
    """
    logger.info(f"Starting Yad2 scraper to fetch {limit} car listings")
    
    # Initialize the scraper with headless=True for browser mode
    scraper = Yad2Scraper(
        headless=False,  # Set to True for headless mode
        max_retries=3
    )
    
    try:
        # Set up the browser
        await scraper._setup_browser()
        
        # Define search parameters (you can modify these as needed)
        search_params = {
            'limit': limit,
            'page': 1
        }
        
        # Scrape the listings
        logger.info(f"Scraping Yad2 for car listings with params: {search_params}")
        listings = await scraper.scrape(search_params)
        
        # Limit the number of listings
        if len(listings) > limit:
            listings = listings[:limit]
            
        logger.info(f"Successfully scraped {len(listings)} car listings")
        return listings
        
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}", exc_info=True)
        raise
        
    finally:
        # Clean up resources
        await scraper._cleanup()

def save_to_json(listings: List[Dict[str, Any]], filename: str = None) -> str:
    """
    Save listings to a JSON file.
    
    Args:
        listings: List of car listings
        filename: Output filename (optional)
        
    Returns:
        str: Path to the saved file
    """
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"yad2_listings_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved {len(listings)} listings to {filename}")
    return filename

async def main():
    """Main function to run the scraper."""
    try:
        # Scrape 25 car listings
        listings = await scrape_yad2_listings(limit=25)
        
        # Save results to JSON file
        output_file = save_to_json(listings)
        print(f"\nScraping completed successfully!")
        print(f"Found {len(listings)} car listings.")
        print(f"Results saved to: {output_file}")
        
        # Print a sample listing
        if listings:
            print("\nSample listing:")
            print(json.dumps(listings[0], indent=2, ensure_ascii=False))
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    asyncio.run(main())
