#!/usr/bin/env python3
"""
Test script for the Yad2 scraper.
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
        logging.FileHandler('yad2_scraper_test.log')
    ]
)
logger = logging.getLogger(__name__)

async def test_scraper():
    """Test the Yad2 scraper."""
    from app.scrapers.yad2_updated import Yad2Scraper
    
    search_params = {
        'manufacturer': 'Toyota',
        'model': 'Corolla',
        'year_from': 2015,
        'year_to': 2020,
        'price_from': 40000,
        'price_to': 100000,
        'mileage_from': 0,
        'mileage_to': 100000,
        'location': 'תל אביב',
        'page': 1,
        'max_pages': 1  # Just test one page for now
    }
    
    try:
        logger.info("Starting Yad2 scraper test...")
        
        # Initialize scraper with headless=False to see the browser
        async with Yad2Scraper(headless=False, slow_mo=100) as scraper:
            logger.info("Scraper initialized successfully")
            
            # Test browser setup
            logger.info("Testing browser setup...")
            browser, context, page = await scraper._setup_browser()
            logger.info("Browser setup successful")
            
            # Test navigation
            test_url = "https://www.yad2.co.il/vehicles/cars"
            logger.info(f"Testing navigation to {test_url}")
            
            try:
                response = await page.goto(test_url, timeout=60000)  # 60 seconds timeout
                logger.info(f"Navigation successful. Status: {response.status if response else 'No response'}")
                
                # Wait for the page to load
                await page.wait_for_load_state('networkidle', timeout=30000)
                
                # Check for bot detection
                bot_detected = await page.evaluate('''() => {
                    return document.body.innerText.includes('bot') || 
                           document.body.innerText.includes('Bot') ||
                           document.body.innerText.includes('BOT') ||
                           document.body.innerText.includes('Access Denied') ||
                           document.title.includes('Access Denied');
                }''')
                
                if bot_detected:
                    logger.warning("Bot detection triggered! Check the browser for CAPTCHA or other challenges.")
                    # Take a screenshot for debugging
                    await page.screenshot(path='bot_detected.png')
                    logger.info("Screenshot saved as 'bot_detected.png'")
                else:
                    logger.info("No bot detection triggered")
                    
                # Extract some basic info to verify the page loaded correctly
                title = await page.title()
                logger.info(f"Page title: {title}")
                
                # Try to extract some listings
                listings = await scraper._extract_page_listings(page)
                logger.info(f"Found {len(listings)} listings on the page")
                
                if listings:
                    logger.info("Sample listing:")
                    for key, value in listings[0].items():
                        logger.info(f"  {key}: {value}")
                
                return True
                
            except Exception as e:
                logger.error(f"Error during navigation: {str(e)}", exc_info=True)
                # Take a screenshot on error
                await page.screenshot(path='navigation_error.png')
                logger.info("Screenshot saved as 'navigation_error.png'")
                return False
                
    except Exception as e:
        logger.error(f"Error in test_scraper: {str(e)}", exc_info=True)
        return False
    finally:
        logger.info("Test completed")

if __name__ == "__main__":
    success = asyncio.run(test_scraper())
    if success:
        logger.info("Test completed successfully")
    else:
        logger.error("Test failed")
        sys.exit(1)
