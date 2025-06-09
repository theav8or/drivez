#!/usr/bin/env python3
"""
Run the Yad2 scraper from the command line.
"""
import argparse
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_scraper(max_listings: int, headless: bool = True):
    """Run the Yad2 scraper.
    
    Args:
        max_listings: Maximum number of listings to scrape
        headless: Whether to run the browser in headless mode
    """
    from app.scrapers.yad2_enhanced import Yad2ScraperEnhanced
    
    logger.info(f"Starting Yad2 scraper (max_listings={max_listings}, headless={headless})")
    
    try:
        async with Yad2ScraperEnhanced(headless=headless, max_listings=max_listings) as scraper:
            listings = await scraper.scrape_listings()
            logger.info(f"Successfully scraped {len(listings)} listings")
            return listings
    except Exception as e:
        logger.error(f"Error running scraper: {e}")
        raise

def main():
    """Parse command line arguments and run the scraper."""
    parser = argparse.ArgumentParser(description='Scrape car listings from Yad2')
    parser.add_argument('--max-listings', type=int, default=50,
                       help='Maximum number of listings to scrape (default: 50)')
    parser.add_argument('--headless', action='store_true', default=True,
                       help='Run browser in headless mode (default: True)')
    parser.add_argument('--no-headless', dest='headless', action='store_false',
                       help='Run browser in non-headless mode')
    
    args = parser.parse_args()
    
    # Run the scraper
    asyncio.run(run_scraper(
        max_listings=args.max_listings,
        headless=args.headless
    ))

if __name__ == "__main__":
    main()
