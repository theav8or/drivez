#!/usr/bin/env python3
"""
Script to seed the database with car listings from the Yad2 API.
"""
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('seed_database.log')
    ]
)
logger = logging.getLogger(__name__)

# Import database models and session after logging is configured
from app.db.session import SessionLocal
from app.db.models.car import CarListing, CarBrand, CarModel

# Yad2 API endpoints
YAD2_API_BASE = "https://www.yad2.co.il/api"
LISTINGS_ENDPOINT = f"{YAD2_API_BASE}/vehicles/vehicles/0.0"

# Common headers for API requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
    "Referer": "https://www.yad2.co.il/vehicles/cars",
    "Origin": "https://www.yad2.co.il",
    "x-y2-client": "web",
    "x-y2-client-version": "4.0.0"
}

def fetch_listings(page: int = 1, limit: int = 50) -> List[Dict]:
    """Fetch car listings from Yad2 API."""
    try:
        params = {
            "page": page,
            "limit": limit,
            "sort": "relevance",
            "order": "desc",
            "forceLdLoad": "true"
        }
        
        logger.info(f"Fetching page {page} with {limit} listings...")
        response = requests.get(LISTINGS_ENDPOINT, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return data.get("data", {}).get("items", [])
        
    except Exception as e:
        logger.error(f"Error fetching listings: {str(e)}")
        return []

def normalize_listing(listing: Dict) -> Dict:
    """Normalize listing data to match our database schema."""
    try:
        # Extract basic information
        listing_data = {
            "source": "yad2",
            "source_id": str(listing.get("id", "")),
            "title": listing.get("title", ""),
            "price": float(listing.get("price", 0)) if listing.get("price") else 0,
            "year": int(listing.get("year", 0)) if listing.get("year") else None,
            "mileage": int(listing.get("km", 0)) if listing.get("km") else None,
            "engine_volume": int(listing.get("engine_volume", 0)) if listing.get("engine_volume") else None,
            "gear": listing.get("gear", ""),
            "hand": int(listing.get("hand", 1)) if listing.get("hand") else 1,
            "tested": bool(listing.get("tested", False)),
            "image_url": listing.get("images", [{}])[0].get("src", "") if listing.get("images") else "",
            "link": f"https://www.yad2.co.il/item/{listing.get('id', '')}",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "extra_data": listing  # Store the full listing data for reference
        }
        
        # Extract location
        if "city" in listing and listing["city"]:
            listing_data["location"] = listing["city"].get("text", "")
        
        # Extract brand and model
        if "manufacturer" in listing and listing["manufacturer"]:
            listing_data["brand_name"] = listing["manufacturer"].get("text", "")
        
        if "model" in listing and listing["model"]:
            listing_data["model_name"] = listing["model"].get("text", "")
        
        return listing_data
        
    except Exception as e:
        logger.error(f"Error normalizing listing: {str(e)}")
        logger.debug(f"Problematic listing data: {listing}")
        return {}

def save_listings_to_db(listings: List[Dict], db: Session) -> None:
    """Save listings to the database."""
    if not listings:
        logger.warning("No listings to save to database.")
        return
    
    saved_count = 0
    error_count = 0
    
    try:
        for listing_data in listings:
            try:
                if not all(k in listing_data for k in ['source', 'source_id']):
                    logger.warning("Skipping listing missing required fields")
                    error_count += 1
                    continue
                
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
                    logger.debug(f"Updated listing: {listing_data.get('title', 'No title')}")
                else:
                    # Create new listing
                    listing = CarListing(**listing_data)
                    db.add(listing)
                    logger.info(f"Added new listing: {listing_data.get('title', 'No title')}")
                
                # Commit after each listing to ensure data is saved
                db.commit()
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Error saving listing to database: {str(e)}")
                logger.debug(f"Problematic listing data: {listing_data}")
                db.rollback()
                error_count += 1
                continue
                
        logger.info(f"Successfully saved {saved_count} listings to database")
        if error_count > 0:
            logger.warning(f"Failed to save {error_count} listings due to errors")
            
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        db.rollback()
        raise

def main():
    """Main function to seed the database with car listings."""
    logger.info("Starting database seeding process...")
    
    db = SessionLocal()
    try:
        # Fetch and save listings
        page = 1
        limit = 50
        total_saved = 0
        
        while True:
            # Fetch a page of listings
            listings = fetch_listings(page=page, limit=limit)
            if not listings:
                logger.info("No more listings found.")
                break
                
            # Normalize listings
            normalized_listings = [normalize_listing(listing) for listing in listings]
            normalized_listings = [l for l in normalized_listings if l]  # Remove empty listings
            
            # Save to database
            save_listings_to_db(normalized_listings, db)
            total_saved += len(normalized_listings)
            
            logger.info(f"Processed page {page}. Total saved so far: {total_saved}")
            
            # Check if we should continue to the next page
            if len(listings) < limit:
                break
                
            page += 1
            
            # Be nice to the API
            import time
            time.sleep(2)
            
    except Exception as e:
        logger.error(f"Error during database seeding: {str(e)}", exc_info=True)
    finally:
        db.close()
        logger.info("Database seeding completed.")

if __name__ == "__main__":
    main()
