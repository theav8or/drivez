#!/usr/bin/env python3
"""
Script to seed the database with car listings from the Yad2 API.
"""
import os
import logging
import random
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy.orm import Session
from urllib.parse import urlparse, urljoin
import shutil

# Yad2 Scraper
from yad2_scraper import Yad2Scraper, Yad2Category

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

# Import database models and session after logging is configured
from app.db.session import SessionLocal
from app.db.models.car import CarListing, CarBrand, CarModel, CarStatus

# Yad2 configuration
BASE_URL = "https://www.yad2.co.il"
SEARCH_URL = f"{BASE_URL}/vehicles/private-cars"

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

async def fetch_listings(limit: int = 25) -> List[dict]:
    """Fetch car listings from Yad2 using direct HTTP requests and parse HTML."""
    logger.info(f"Fetching up to {limit} listings...")
    
    from bs4 import BeautifulSoup
    import re
    import aiohttp
    
    # We'll use aiohttp directly instead of Yad2Scraper
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://www.yad2.co.il/'
    }
    
    # Define query parameters
    query_params = {
        'price': '0-1000000',  # Price range
        'hand': '1-',          # First hand only
        'year': '2015-',       # Newer cars
        'km': '-100000',       # Up to 100,000 km
        'priceOnly': '1',      # Only show listings with price
    }
    
    # Build the URL with query parameters
    base_url = "https://www.yad2.co.il/vehicles/private-cars"
    query_string = '&'.join([f"{k}={v}" for k, v in query_params.items()])
    url = f"{base_url}?{query_string}"
    
    try:
        # Create a new aiohttp session
        async with aiohttp.ClientSession(headers=headers) as session:
            # Make the request
            logger.info(f"Fetching URL: {url}")
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch URL: {url}. Status: {response.status}")
                    return []
                
                # Read the response text
                html_content = await response.text()
                
                # Parse the HTML response
                soup = BeautifulSoup(html_content, 'html.parser')
        
                # Parse the HTML response
                soup = BeautifulSoup(html_content, 'html.parser')
        
        # Save the HTML content to a file for debugging
        with open('yad2_response.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        logger.info("Saved HTML response to yad2_response.html for debugging")
        
        # Try different selectors to find listing elements
        listing_elements = []
        
        # Common Yad2 listing selectors
        possible_selectors = [
            'div.feeditem',
            'div[class*="feeditem"]',
            'div[data-test-id="feed-item"]',
            'div.feed-item',
            'div[class*="feed-item"]',
            'div.listing-item',
            'div[class*="listing-item"]',
            'div[data-test="feed-item"]',
            'div[data-testid="feed-item"]',
        ]
        
        # Try each selector until we find some elements
        for selector in possible_selectors:
            listing_elements = soup.select(selector)
            if listing_elements:
                logger.info(f"Found {len(listing_elements)} listing elements with selector: {selector}")
                break
        else:
            # If no elements found with any selector, try a more general approach
            logger.warning("No listing elements found with standard selectors. Trying more general approach...")
            listing_elements = soup.find_all(attrs={"data-test": True})
            if not listing_elements:
                listing_elements = soup.find_all(class_=True)
        
        logger.info(f"Total listing elements found: {len(listing_elements)}")
        
        # If we still don't have elements, log the first 500 chars of the HTML for debugging
        if not listing_elements:
            logger.warning(f"No listing elements found in the page. First 500 chars: {html_content[:500]}...")
        
        listings = []
        for idx, element in enumerate(listing_elements[:limit], 1):
            try:
                # Extract listing data - these selectors will need to be adjusted
                # based on the actual HTML structure of Yad2's listings
                title_elem = element.select_one('div.feeditem-title')
                price_elem = element.select_one('div.price')
                year_km_elem = element.select_one('div.row_3xJNX')
                location_elem = element.select_one('div.row_3xJNX + div')
                image_elem = element.select_one('img')
                link_elem = element.select_one('a')
                
                # Clean and format the data
                title = title_elem.get_text(strip=True) if title_elem else ""
                price_text = price_elem.get_text(strip=True) if price_elem else ""
                price = float(re.sub(r'[^\d.]', '', price_text)) if price_text else 0
                
                # Extract year and mileage if available
                year = None
                mileage = None
                if year_km_elem:
                    text = year_km_elem.get_text()
                    year_match = re.search(r'(\d{4})', text)
                    km_match = re.search(r'(\d+,\d+)\s*ק"מ', text)
                    if year_match:
                        year = int(year_match.group(1))
                    if km_match:
                        mileage = int(km_match.group(1).replace(',', ''))
                
                # Get location
                location = location_elem.get_text(strip=True) if location_elem else ""
                
                # Get image URL
                image_url = image_elem.get('src', '') if image_elem else ""
                if image_url and not image_url.startswith(('http://', 'https://')):
                    image_url = urljoin(base_url, image_url)
                
                # Get listing URL
                listing_url = ""
                if link_elem and link_elem.get('href'):
                    listing_url = link_elem['href']
                    if not listing_url.startswith(('http://', 'https://')):
                        listing_url = urljoin(base_url, listing_url)
                
                # Create listing dictionary
                listing_data = {
                    'id': str(idx),
                    'title': title,
                    'price': price,
                    'year': year,
                    'mileage': mileage,
                    'location': location,
                    'image_url': image_url,
                    'url': listing_url,
                    'description': ""  # Will be populated when fetching full details
                }
                
                listings.append(listing_data)
                logger.info(f"Extracted listing: {title[:50]}...")
                
                # Be nice to the server
                if idx < len(listing_elements[:limit]):
                    await asyncio.sleep(random.uniform(1.0, 3.0))
                    
            except Exception as e:
                logger.error(f"Error processing listing {idx}: {str(e)}", exc_info=True)
                continue
        
        return listings
        
    except Exception as e:
        logger.error(f"Error in fetch_listings: {str(e)}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error in fetch_listings: {str(e)}", exc_info=True)
        return []

def normalize_listing(listing: Dict) -> Dict:
    """Normalize listing data to match our database schema."""
    try:
        listing_id = str(listing.get('id', ''))
        
        # Set default values for required fields
        title = listing.get('title', '').strip()
        description = listing.get('description', '').strip()
        price = max(0, float(listing.get('price', 0)))  # Ensure non-negative price
        
        # Try to extract year from title if not provided
        year = None
        if listing.get('year'):
            try:
                year = int(listing['year'])
            except (ValueError, TypeError):
                pass
        
        # If year is still None, try to extract it from the title
        if year is None and title:
            import re
            year_match = re.search(r'(20\d{2})', title)
            if year_match:
                try:
                    year = int(year_match.group(1))
                except (ValueError, TypeError):
                    pass
        
        # Set a default year if still None (required field)
        if year is None:
            year = 2020  # Default to current year - 5
        
        # Extract mileage
        mileage = None
        if listing.get('mileage'):
            try:
                mileage = int(str(listing['mileage']).replace(',', '').replace('.', ''))
            except (ValueError, TypeError):
                pass
        
        # Extract basic information with proper defaults
        listing_data = {
            "yad2_id": listing_id or f"generated_{int(time.time())}",
            "title": title or "No Title",
            "description": description or "No description available",
            "price": price,
            "year": year,
            "mileage": mileage,
            "fuel_type": listing.get('fuel_type', 'Unknown'),
            "transmission": listing.get('transmission', 'Unknown'),
            "body_type": listing.get('body_type', 'Sedan'),
            "color": listing.get('color', 'Not specified'),
            "image_url": listing.get('image_url', ''),
            "status": CarStatus.ACTIVE,
            "last_scraped_at": datetime.utcnow(),
            "extra_data": {k: v for k, v in listing.items() if k not in [
                'id', 'title', 'description', 'price', 'year', 'mileage', 
                'fuel_type', 'transmission', 'body_type', 'color', 
                'image_url', 'url', 'status'
            ]}  # Store the remaining data for reference
        }
        
        # Extract manufacturer and model from title if available
        if title:
            parts = title.split()
            if parts:
                listing_data["manufacturer"] = parts[0]
                if len(parts) > 1:
                    listing_data["model"] = " ".join(parts[1:3]) if len(parts) > 2 else parts[1]
        
        # Ensure we have at least a default manufacturer and model
        if 'manufacturer' not in listing_data or not listing_data['manufacturer']:
            listing_data['manufacturer'] = 'Unknown'
        if 'model' not in listing_data or not listing_data['model']:
            listing_data['model'] = 'Unknown'
        
        return listing_data
        
    except Exception as e:
        logger.error(f"Error normalizing listing: {str(e)}", exc_info=True)
        logger.debug(f"Problematic listing data: {listing}")
        return None  # Return None instead of empty dict to indicate failure

def get_or_create_brand(db: Session, brand_name: str) -> CarBrand:
    """Get or create a car brand."""
    if not brand_name:
        return None
        
    normalized_name = brand_name.lower().strip()
    brand = db.query(CarBrand).filter(
        CarBrand.normalized_name == normalized_name
    ).first()
    
    if not brand:
        brand = CarBrand(
            name=brand_name,
            normalized_name=normalized_name,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(brand)
        db.commit()
        db.refresh(brand)
        logger.info(f"Created new brand: {brand_name}")
    
    return brand

def get_or_create_model(db: Session, model_name: str, brand_id: int) -> CarModel:
    """Get or create a car model."""
    if not model_name or not brand_id:
        return None
        
    normalized_name = model_name.lower().strip()
    model = db.query(CarModel).filter(
        CarModel.normalized_name == normalized_name,
        CarModel.brand_id == brand_id
    ).first()
    
    if not model:
        model = CarModel(
            name=model_name,
            normalized_name=normalized_name,
            brand_id=brand_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        logger.info(f"Created new model: {model_name} for brand ID {brand_id}")
    
    return model

def save_listings_to_db(listings: List[Dict], db: Session) -> Tuple[int, int]:
    """
    Save listings to the database.
    
    Args:
        listings: List of normalized listing dictionaries
        db: Database session
        
    Returns:
        Tuple of (saved_count, error_count)
    """
    if not listings:
        logger.warning("No listings to save to database.")
        return 0, 0
    
    saved_count = 0
    error_count = 0
    
    try:
        for listing_data in listings:
            try:
                if not listing_data or 'yad2_id' not in listing_data:
                    logger.warning("Skipping invalid listing data")
                    error_count += 1
                    continue
                
                # Extract brand and model information
                manufacturer = listing_data.pop('manufacturer', 'Unknown')
                model_name = listing_data.pop('model', 'Unknown')
                
                # Get or create brand and model
                brand = get_or_create_brand(db, manufacturer)
                if not brand:
                    logger.warning(f"Failed to get or create brand: {manufacturer}")
                    error_count += 1
                    continue
                    
                model = get_or_create_model(db, model_name, brand.id)
                if not model:
                    logger.warning(f"Failed to get or create model: {model_name} for brand: {brand.name}")
                    error_count += 1
                    continue
                
                # Add brand_id and model_id to the listing data
                listing_data['brand_id'] = brand.id
                listing_data['model_id'] = model.id
                
                # Remove any keys that aren't valid CarListing attributes
                valid_attrs = {c.name for c in CarListing.__table__.columns}
                listing_data = {k: v for k, v in listing_data.items() 
                              if k in valid_attrs and v is not None}
                
                # Extract yad2_id for the query
                yad2_id = listing_data.get('yad2_id')
                
                # Check if listing already exists
                existing = db.query(CarListing).filter(
                    CarListing.yad2_id == yad2_id
                ).first()
                
                if existing:
                    # Update existing listing
                    for key, value in listing_data.items():
                        if hasattr(existing, key) and key not in ['id', 'created_at']:
                            setattr(existing, key, value)
                    existing.last_scraped_at = datetime.utcnow()
                    existing.updated_at = datetime.utcnow()
                    logger.debug(f"Updated listing: {listing_data.get('title', 'No title')}")
                else:
                    # Create new listing
                    listing = CarListing(**listing_data)
                    db.add(listing)
                    logger.info(f"Added new listing: {listing_data.get('title', 'No title')}")
                
                # Commit after each listing to ensure data is saved
                db.commit()
                saved_count += 1
                
                # Add a small delay between database operations
                time.sleep(0.1)
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error saving listing to database: {str(e)}", exc_info=True)
                logger.debug(f"Problematic listing data: {listing_data}")
                error_count += 1
                continue
                
        logger.info(f"Successfully saved {saved_count} listings to database")
        if error_count > 0:
            logger.warning(f"Failed to save {error_count} listings due to errors")
            
    except Exception as e:
        logger.error(f"Database error: {str(e)}", exc_info=True)
        db.rollback()
        raise
        
    return saved_count, error_count

async def main_async():
    """Async main function to seed the database with car listings."""
    logger.info("Starting database seeding process...")
    start_time = datetime.now()
    
    db = SessionLocal()
    try:
        # Fetch and save listings
        limit = 25  # Fetch 25 listings
        total_saved = 0
        total_errors = 0
        
        # Fetch listings using yad2-scraper
        logger.info(f"Fetching up to {limit} listings...")
        listings = await fetch_listings(limit=limit)
        
        if not listings:
            logger.warning("No listings found. The website might be blocking the request.")
            return
            
        # Normalize listings
        normalized_listings = []
        for listing in listings:
            try:
                normalized = normalize_listing(listing)
                if normalized:  # Only append if normalization was successful
                    normalized_listings.append(normalized)
                else:
                    logger.warning("Skipping listing due to normalization failure")
            except Exception as e:
                logger.error(f"Error normalizing listing: {str(e)}", exc_info=True)
                continue
        
        # Save to database
        saved, errors = save_listings_to_db(normalized_listings, db)
        total_saved += saved
        total_errors += errors
        
        logger.info(f"Processed {len(normalized_listings)} listings. Saved: {saved}, Errors: {errors}")
        
        # Summary
        duration = (datetime.now() - start_time).total_seconds()
        logger.info("=" * 50)
        logger.info("SEEDING SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total saved: {total_saved}")
        logger.info(f"Total errors: {total_errors}")
        logger.info(f"Time taken: {duration:.2f} seconds")
        logger.info("=" * 50)
            
    except Exception as e:
        logger.error(f"Error during database seeding: {str(e)}", exc_info=True)
    finally:
        db.close()
        logger.info("Database seeding completed.")

if __name__ == "__main__":
    import asyncio
    import sys
    
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
        sys.exit(1)
