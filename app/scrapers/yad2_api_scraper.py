"""
Yad2 API-based car listings scraper.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
import aiohttp
import random
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

class Yad2ApiScraper:
    """Scraper for Yad2 car listings using their internal API."""
    
    def __init__(
        self,
        max_retries: int = 3,
        delay_range: tuple = (1, 3),
        max_pages: int = 3,
        limit: int = 25
    ) -> None:
        """Initialize the Yad2 API scraper.
        
        Args:
            max_retries: Maximum number of retry attempts for failed requests
            delay_range: Range of random delays between requests in seconds
            max_pages: Maximum number of pages to scrape
            limit: Maximum number of listings to return
        """
        self.max_retries = max_retries
        self.delay_range = delay_range
        self.max_pages = max_pages
        self.limit = limit
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,he;q=0.8',
            'Referer': 'https://www.yad2.co.il/vehicles/cars',
            'Origin': 'https://www.yad2.co.il',
            'DNT': '1',
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _make_request(
        self, 
        url: str, 
        params: Optional[Dict] = None,
        method: str = 'GET',
        json_data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make an HTTP request with retry logic.
        
        Args:
            url: URL to request
            params: Query parameters
            method: HTTP method (GET, POST, etc.)
            json_data: JSON data for POST requests
            
        Returns:
            JSON response as a dictionary, or None if all retries fail
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"Making {method} request to {url} (attempt {attempt}/{self.max_retries})")
                
                async with self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    return await response.json()
                    
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Request failed (attempt {attempt}/{self.max_retries}): {str(e)}")
                if attempt == self.max_retries:
                    logger.error(f"Max retries ({self.max_retries}) exceeded for URL: {url}")
                    return None
                
                # Exponential backoff
                delay = random.uniform(*self.delay_range) * (2 ** (attempt - 1))
                logger.debug(f"Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
    
    async def get_car_listings(self, search_params: Optional[Dict] = None) -> List[Dict]:
        """Get car listings from Yad2 API.
        
        Args:
            search_params: Additional search parameters
            
        Returns:
            List of car listing dictionaries
        """
        base_url = "https://gw.yad2.co.il/vehicles/vehicles/list"
        
        # Default parameters
        params = {
            'cat': 1,  # Vehicles category
            'subcat': 2,  # Cars subcategory
            'sort': 1,  # Sort by: Newest first
            'page': 1,
            'forceLdLoad': 'true'
        }
        
        # Map search parameters to Yad2 API parameters
        if search_params:
            if 'manufacturer' in search_params:
                params['manufacturer'] = search_params['manufacturer']
            if 'model' in search_params:
                params['model'] = search_params['model']
            if 'year' in search_params:
                year_parts = search_params['year'].split('-')
                if len(year_parts) == 2:
                    if year_parts[0]:
                        params['yearMin'] = year_parts[0]
                    if year_parts[1]:
                        params['yearMax'] = year_parts[1]
            if 'price' in search_params:
                price_parts = search_params['price'].split('-')
                if len(price_parts) == 2:
                    if price_parts[0]:
                        params['priceMin'] = price_parts[0]
                    if price_parts[1]:
                        params['priceMax'] = price_parts[1]
        
        all_listings = []
        
        try:
            for page in range(1, self.max_pages + 1):
                params['page'] = page
                logger.info(f"Fetching page {page} of results...")
                
                # Make the API request
                response = await self._make_request(base_url, params=params)
                if not response or 'data' not in response or 'feed' not in response['data']:
                    logger.warning(f"No data found in API response for page {page}")
                    break
                
                # Process the listings
                page_listings = self._process_listings(response['data']['feed']['feed_items'])
                all_listings.extend(page_listings)
                
                # Log some debug info
                logger.debug(f"Page {page} - Got {len(page_listings)} listings")
                
                logger.info(f"Found {len(page_listings)} listings on page {page}")
                
                # Stop if we've reached the limit
                if len(all_listings) >= self.limit:
                    all_listings = all_listings[:self.limit]
                    logger.info(f"Reached the limit of {self.limit} listings")
                    break
                
                # Add a small delay between requests
                if page < self.max_pages and len(page_listings) > 0:
                    delay = random.uniform(*self.delay_range)
                    logger.debug(f"Waiting {delay:.2f} seconds before next request...")
                    await asyncio.sleep(delay)
                
                # If we got fewer results than expected, we've probably reached the end
                if len(page_listings) < 20:  # Yad2 typically returns 20 items per page
                    logger.info("Reached the end of available listings")
                    break
            
            return all_listings
            
        except Exception as e:
            logger.error(f"Error getting car listings: {str(e)}", exc_info=True)
            return all_listings
    
    def _process_listings(self, raw_listings: List[Dict]) -> List[Dict]:
        """Process raw listing data into a standardized format.
        
        Args:
            raw_listings: List of raw listing dictionaries from the API
            
        Returns:
            List of processed listing dictionaries
        """
        processed = []
        
        for item in raw_listings:
            try:
                # Skip invalid or missing items
                if not item.get('id'):
                    continue
                
                # Extract basic information
                listing = {
                    'source': 'yad2',
                    'source_id': str(item.get('id', '')),
                    'title': f"{item.get('manufacturer', '')} {item.get('model', '')} {item.get('sub_title', '')}".strip(),
                    'price': float(item.get('price', 0)) if item.get('price') else 0,
                    'year': int(item.get('year', 0)) if item.get('year') else None,
                    'kilometers': float(item.get('kilometers', 0)) if item.get('kilometers') else None,
                    'engine_size': float(item.get('engine_volume', 0)) if item.get('engine_volume') else None,
                    'gear': item.get('gear', '').strip(),
                    'hand': int(item.get('owner_id', 0)) if item.get('owner_id') else None,  # Using owner_id as hand
                    'owner_id': item.get('owner_id', ''),
                    'date_updated': datetime.utcnow(),
                    'url': f"https://www.yad2.co.il{item.get('link', '')}",
                    'image_url': item.get('images', [{}])[0].get('src', '') if item.get('images') else '',
                    'location': item.get('area', '').strip(),
                    'fuel_type': item.get('fuel_type', '').strip(),
                    'color': item.get('color', '').strip(),
                    'tested': item.get('tested', False),
                    'next_test': item.get('next_test', '').strip(),
                    'description': item.get('description', '').strip(),
                }
                
                processed.append(listing)
                
            except Exception as e:
                logger.error(f"Error processing listing: {str(e)}")
                continue
        
        return processed

async def main():
    """Example usage of the Yad2ApiScraper."""
    # Example search parameters
    search_params = {
        'manufacturer': 'Toyota',
        'model': 'Corolla',
        'year': '2015-2023',
        'price': '50000-150000',
    }
    
    async with Yad2ApiScraper(max_pages=3, limit=25) as scraper:
        listings = await scraper.get_car_listings(search_params)
        print(f"Found {len(listings)} listings")
        
        # Print the first few listings as an example
        for i, listing in enumerate(listings[:3], 1):
            print(f"\nListing {i}:")
            print(f"  Title: {listing['title']}")
            print(f"  Price: {listing['price']} NIS")
            print(f"  Year: {listing['year']}")
            print(f"  Kilometers: {listing['kilometers']}")
            print(f"  Location: {listing['location']}")
            print(f"  URL: {listing['url']}")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('yad2_scraper.log')
        ]
    )
    
    asyncio.run(main())
