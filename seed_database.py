#!/usr/bin/env python3
"""
Script to seed the database with car listings from Yad2 by parsing embedded JSON data.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session, sessionmaker, relationship
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, func, text
from sqlalchemy.ext.declarative import declarative_base
import logging

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database models
Base = declarative_base()

class Brand(Base):
    __tablename__ = "car_brands"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    normalized_name = Column(String, index=True)
    models = relationship("Model", back_populates="brand")
    listings = relationship("Listing", back_populates="brand")

class Model(Base):
    __tablename__ = "car_models"
    
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("car_brands.id"))
    name = Column(String, index=True)
    normalized_name = Column(String, index=True)
    brand = relationship("Brand", back_populates="models")
    listings = relationship("Listing", back_populates="model")

class Listing(Base):
    __tablename__ = "car_listings"
    
    id = Column(Integer, primary_key=True, index=True)
    yad2_id = Column(String, unique=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    price = Column(Float)
    brand_id = Column(Integer, ForeignKey("car_brands.id"))
    model_id = Column(Integer, ForeignKey("car_models.id"))
    year = Column(Integer)
    km = Column(Integer)
    fuel_type = Column(String)
    body_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    brand = relationship("Brand", back_populates="listings")
    model = relationship("Model", back_populates="listings")

# Database setup
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

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

# Base URL for Yad2
BASE_URL = 'https://www.yad2.co.il/vehicles/cars'

# Headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,he;q=0.8',
    'Referer': 'https://www.yad2.co.il/',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def extract_price_from_html(html_content: str) -> List[Dict]:
    """Extract listing data including prices from HTML content."""
    # The actual listings are in the __NEXT_DATA__ script tag as JSON
    soup = BeautifulSoup(html_content, 'html.parser')
    listings = []
    
    # Find the script tag containing the JSON data
    script_tag = soup.find('script', id='__NEXT_DATA__')
    if not script_tag:
        logger.error("Could not find __NEXT_DATA__ script tag")
        return []
    
    try:
        # Parse the JSON data
        json_data = json.loads(script_tag.string)
        
        # Save the parsed JSON for debugging
        with open('yad2_parsed_data.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        logger.info("Saved parsed JSON data to 'yad2_parsed_data.json'")
        
        # Extract private and commercial listings from the JSON structure
        def find_listings(data: Any) -> List[Dict]:
            """Recursively search for listings in the JSON structure."""
            listings = []
            
            if isinstance(data, dict):
                # Check for listings in the current level
                if 'private' in data and isinstance(data['private'], list):
                    listings.extend(data['private'])
                if 'commercial' in data and isinstance(data['commercial'], list):
                    listings.extend(data['commercial'])
                
                # Recursively search through dictionary values
                for value in data.values():
                    listings.extend(find_listings(value))
                    
            elif isinstance(data, list):
                for item in data:
                    listings.extend(find_listings(item))
            
            return listings
        
        all_listings = find_listings(json_data)
        
        if not all_listings:
            logger.warning("No listings found in the JSON data")
            return []
            
        logger.info(f"Found {len(all_listings)} listings in the JSON data")
        
        # Process each listing
        for item in all_listings:
            try:
                listing_data = {}
                
                # Extract basic information
                listing_id = item.get('adNumber') or item.get('token') or item.get('id')
                if not listing_id:
                    continue
                
                listing_data['id'] = listing_id
                
                # Extract title from manufacturer and model
                manufacturer = ''
                model = ''
                
                if 'manufacturer' in item:
                    if isinstance(item['manufacturer'], dict) and 'text' in item['manufacturer']:
                        manufacturer = item['manufacturer']['text']
                    elif isinstance(item['manufacturer'], str):
                        manufacturer = item['manufacturer']
                
                if 'model' in item:
                    if isinstance(item['model'], dict) and 'text' in item['model']:
                        model = item['model']['text']
                    elif isinstance(item['model'], str):
                        model = item['model']
                
                title = f"{manufacturer} {model}".strip()
                listing_data['title'] = title if title else 'No title'
                listing_data['manufacturer'] = manufacturer
                listing_data['model'] = model
                
                # Extract price
                price = item.get('price')
                if price and (isinstance(price, (int, float)) or (isinstance(price, str) and price.isdigit())):
                    price = float(price)
                    listing_data['price'] = price if price > 0 else None
                else:
                    listing_data['price'] = None
                
                # Extract year
                if 'vehicleDates' in item and 'yearOfProduction' in item['vehicleDates']:
                    listing_data['year'] = int(item['vehicleDates']['yearOfProduction'])
                
                # Extract mileage
                if 'km' in item:
                    try:
                        km = str(item['km']).replace(',', '').replace(' ', '')
                        if km.isdigit():
                            listing_data['mileage'] = int(km)
                    except (ValueError, TypeError):
                        pass
                
                # Extract fuel type
                if 'fuelType' in item:
                    if isinstance(item['fuelType'], dict) and 'text' in item['fuelType']:
                        listing_data['fuel_type'] = item['fuelType']['text']
                    elif isinstance(item['fuelType'], str):
                        listing_data['fuel_type'] = item['fuelType']
                
                # Extract body type
                if 'bodyType' in item:
                    if isinstance(item['bodyType'], dict) and 'text' in item['bodyType']:
                        listing_data['body_type'] = item['bodyType']['text']
                    elif isinstance(item['bodyType'], str):
                        listing_data['body_type'] = item['bodyType']
                
                # Extract description
                if 'description' in item and item['description']:
                    listing_data['description'] = item['description']
                elif 'text' in item and item['text']:
                    listing_data['description'] = item['text']
                else:
                    listing_data['description'] = ''
                
                # Extract location
                location_parts = []
                if 'address' in item:
                    if 'city' in item['address'] and 'text' in item['address']['city']:
                        location_parts.append(item['address']['city']['text'])
                    if 'area' in item['address'] and 'text' in item['address']['area']:
                        location_parts.append(item['address']['area']['text'])
                listing_data['location'] = ', '.join(location_parts) if location_parts else ''
                
                # Extract image URL
                if 'images' in item and item['images'] and isinstance(item['images'], list):
                    listing_data['image_url'] = item['images'][0]
                elif 'image' in item and item['image']:
                    listing_data['image_url'] = item['image']
                elif 'media' in item and item['media'] and 'images' in item['media'] and item['media']['images']:
                    listing_data['image_url'] = item['media']['images'][0].get('url', '')
                else:
                    listing_data['image_url'] = ''
                
                # Add the raw item for debugging
                listing_data['raw_data'] = item
                
                listings.append(listing_data)
                
            except Exception as e:
                logger.warning(f"Error processing listing: {str(e)}", exc_info=True)
                continue
        
        return listings
        
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse JSON data: {str(je)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return []

def fetch_listings(page: int = 1, limit: int = 20) -> List[Dict]:
    """Fetch car listings from Yad2 search API."""
    try:
        # Set up session
        session = requests.Session()
        
        # Headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,he;q=0.8',
            'Referer': 'https://www.yad2.co.il/vehicles/cars',
            'Origin': 'https://www.yad2.co.il',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
        
        # First, get the main page to set cookies
        logger.info("Fetching initial page to set cookies...")
        session.get('https://www.yad2.co.il/vehicles/cars', headers=headers, timeout=10)
        
        # Now use the search API endpoint
        api_url = "https://www.yad2.co.il/api/v1/cars/search"
        
        # Request payload (similar to what the website sends)
        payload = {
            "cat": 5,  # Cars category
            "subcat": 101,  # Private cars
            "area": 1,  # All areas
            "hand": 1,  # Private sellers
            "price": "0-0",  # All prices
            "page": page,
            "forceLdLoad": True,
            "compact-req-1": 0,
            "topArea": 2,  # Center area
            "pageSize": limit,
        }
        
        logger.info(f"Fetching page {page} with up to {limit} listings...")
        
        # Make the POST request to the search API
        response = session.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()
        
        # Save the raw JSON response for debugging
        with open('yad2_api_response.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Saved API response to 'yad2_api_response.json'")
        
        # Extract listings from the response
        listings = []
        if 'data' in data and 'feed' in data['data'] and 'feed_items' in data['data']['feed']:
            for item in data['data']['feed']['feed_items']:
                if 'data' in item and isinstance(item['data'], dict):
                    listings.append(item['data'])
        
        # Alternative path if the structure is different
        if not listings and 'data' in data and 'feed' in data['data'] and 'items' in data['data']['feed']:
            listings = data['data']['feed']['items']
        
        logger.info(f"Extracted {len(listings)} listings from API response")
        
        # Debug: Log the first listing if available
        if listings:
            logger.debug(f"First listing sample: {json.dumps(listings[0], ensure_ascii=False, indent=2)[:500]}...")
        
        return listings[:limit]  # Return only the requested number of items
        
    except requests.exceptions.RequestException as re:
        logger.error(f"Request failed: {str(re)}")
        return []
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse JSON response: {str(je)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return []

def normalize_listing(listing: Dict) -> Optional[Dict]:
    """Normalize listing data to match our database schema."""
    try:
        # Debug: Log the raw listing data
        logger.debug(f"Processing listing: {json.dumps(listing, indent=2, ensure_ascii=False)[:500]}...")
        
        # Initialize variables with default values
        title = ''
        description = ''
        manufacturer = 'Unknown'
        model = 'Unknown'
        price = 0
        year = None
        km = 0
        fuel_type = ''
        body_type = ''
        
        # Extract ID - try multiple possible fields
        listing_id = (
            str(listing.get('id')) or 
            str(listing.get('adNumber', '')) or 
            str(listing.get('ad_number', '')) or 
            str(listing.get('adId', '')) or
            str(listing.get('ad_id', ''))
        ).strip()
        
        if not listing_id:
            logger.warning("No ID found in listing, skipping")
            return None
            
        # Extract title and description
        title = str(listing.get('title') or listing.get('name') or '').strip()
        description = str(listing.get('description') or '').strip()
        
        # Try to get description from nested fields if not found
        if not description and 'images' in listing and isinstance(listing['images'], dict):
            description = str(listing['images'].get('description', '')).strip()
        
        # Extract manufacturer and model
        if 'manufacturer' in listing and listing['manufacturer']:
            if isinstance(listing['manufacturer'], dict):
                manufacturer = str(listing['manufacturer'].get('text', '')).strip()
            else:
                manufacturer = str(listing['manufacturer']).strip()
        
        if 'model' in listing and listing['model']:
            if isinstance(listing['model'], dict):
                model = str(listing['model'].get('text', '')).strip()
            else:
                model = str(listing['model']).strip()
        
        # If we still don't have manufacturer or model, try to extract from title
        if not manufacturer or not model or manufacturer == 'Unknown' or model == 'Unknown':
            title_parts = title.split()
            if len(title_parts) >= 2:
                if not manufacturer or manufacturer == 'Unknown':
                    manufacturer = title_parts[0]
                if (not model or model == 'Unknown') and len(title_parts) > 1:
                    model = ' '.join(title_parts[1:])  # Take the rest as model name
        
        # Clean up manufacturer and model
        manufacturer = manufacturer.strip() or 'Unknown'
        model = model.strip() or 'Unknown'
        
        # Extract price
        price_value = 0
        if 'price' in listing and listing['price'] is not None:
            try:
                price_str = str(listing['price']).replace(',', '').replace(' ', '')
                price_value = int(float(price_str)) if price_str.replace('.', '').isdigit() else 0
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse price for listing {listing_id}: {e}")
                price_value = 0
        
        # Extract year
        year_value = None
        if 'year' in listing and listing['year']:
            try:
                year_value = int(str(listing['year']).strip())
            except (ValueError, TypeError):
                pass
        elif 'vehicleDates' in listing and listing['vehicleDates'] and 'yearOfProduction' in listing['vehicleDates']:
            try:
                year_value = int(str(listing['vehicleDates']['yearOfProduction']).strip())
            except (ValueError, TypeError):
                pass
        
        # Extract mileage (km)
        km_value = 0
        if 'km' in listing and listing['km'] is not None:
            try:
                km_str = str(listing['km']).replace(',', '').replace(' ', '').replace('km', '')
                km_value = int(float(km_str)) if km_str.replace('.', '').isdigit() else 0
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse mileage for listing {listing_id}: {e}")
                km_value = 0
        
        # Extract fuel type
        fuel_type_value = ''
        if 'fuelType' in listing and listing['fuelType']:
            if isinstance(listing['fuelType'], dict) and 'text' in listing['fuelType']:
                fuel_type_value = str(listing['fuelType']['text']).strip()
            else:
                fuel_type_value = str(listing['fuelType']).strip()
        
        # Extract body type
        body_type_value = ''
        if 'bodyType' in listing and listing['bodyType']:
            if isinstance(listing['bodyType'], dict) and 'text' in listing['bodyType']:
                body_type_value = str(listing['bodyType']['text']).strip()
            else:
                body_type_value = str(listing['bodyType']).strip()
        
        # Create normalized listing
        normalized = {
            'id': listing_id,
            'title': title[:255],
            'description': description[:4000],
            'manufacturer': manufacturer,
            'model': model,
            'price': price_value,
            'year': year_value,
            'km': km_value,
            'fuel_type': fuel_type_value,
            'body_type': body_type_value,
            'raw_data': listing  # Keep original data for debugging
        }
        
        logger.debug(f"Normalized listing {listing_id}: {json.dumps(normalized, indent=2, ensure_ascii=False)[:500]}...")
        return normalized
        
    except Exception as e:
        logger.error(f"Error normalizing listing: {e}", exc_info=True)
        return None
        
        if price is None:
            logger.warning(f"Could not determine price for listing {listing_id}")
        elif price == 0:
            logger.debug(f"Listing {listing_id} has price 0, which might indicate a price-on-request or error")
            
        # Extract year if available
        year = None
        if 'vehicleDates' in listing and 'yearOfProduction' in listing['vehicleDates']:
            year = listing['vehicleDates']['yearOfProduction']
        elif 'year' in listing:
            year = listing['year']
            
        # Extract mileage if available
        mileage = None
        if 'km' in listing:
            try:
                mileage = int(listing['km'])
            except (ValueError, TypeError):
                pass
                
        # Extract engine volume if available
        engine_volume = None
        if 'engineVolume' in listing:
            try:
                engine_volume = float(listing['engineVolume'])
            except (ValueError, TypeError):
                pass
                
        # Extract transmission type if available
        transmission = None
        if 'gearBox' in listing and isinstance(listing['gearBox'], dict) and 'text' in listing['gearBox']:
            transmission = listing['gearBox']['text']
            
        # Extract fuel type if available
        fuel_type = None
        if 'engineType' in listing and isinstance(listing['engineType'], dict) and 'text' in listing['engineType']:
            fuel_type = listing['engineType']['text']
            
        # Extract color if available
        color = None
        if 'color' in listing and isinstance(listing['color'], dict) and 'text' in listing['color']:
            color = listing['color']['text']
            
        # Extract location if available
        location = None
        if 'address' in listing and isinstance(listing['address'], dict):
            address_parts = []
            if 'city' in listing['address'] and 'text' in listing['address']['city']:
                address_parts.append(listing['address']['city']['text'])
            if 'area' in listing['address'] and 'text' in listing['address']['area']:
                address_parts.append(listing['address']['area']['text'])
            if address_parts:
                location = ', '.join(address_parts)
                
        # Extract image URL if available
        image_url = None
        if 'metaData' in listing and 'coverImage' in listing['metaData']:
            image_url = listing['metaData']['coverImage']
            if image_url and not image_url.startswith(('http://', 'https://')):
                image_url = f'https:{image_url}' if image_url.startswith('//') else image_url
        
        # Get the year
        year = None
        if 'vehicleDates' in listing and 'yearOfProduction' in listing['vehicleDates']:
            try:
                year = int(listing['vehicleDates']['yearOfProduction'])
            except (ValueError, TypeError):
                year = None
        
        # Get the mileage
        km = None
        if 'km' in listing and listing['km'] is not None:
            try:
                km = float(str(listing['km']).replace(',', '').replace(' ', '').replace('ק"מ', '').strip())
            except (ValueError, TypeError):
                km = None
        
        # Get the location
        location_parts = []
        if 'address' in listing:
            if 'city' in listing['address'] and 'text' in listing['address']['city']:
                location_parts.append(listing['address']['city']['text'])
            if 'area' in listing['address'] and 'text' in listing['address']['area']:
                location_parts.append(listing['address']['area']['text'])
        location = ', '.join(location_parts) if location_parts else ''
        
        # Get the link
        link = f"https://www.yad2.co.il/item/{listing_id}" if listing_id else ''
        
        # Get the image URL
        image_url = ''
        if 'metaData' in listing and 'coverImage' in listing['metaData'] and listing['metaData']['coverImage']:
            image_url = listing['metaData']['coverImage']
        elif 'images' in listing and listing['images'] and isinstance(listing['images'], list) and listing['images']:
            image_url = listing['images'][0]
        
        # Get additional details
        color = listing.get('color', {}).get('text', '') if isinstance(listing.get('color'), dict) else ''
        hand = listing.get('hand', {}).get('text', '') if isinstance(listing.get('hand'), dict) else ''
        gear_box = listing.get('gearBox', {}).get('text', '') if isinstance(listing.get('gearBox'), dict) else ''
        
        # Check if the car is automatic
        is_automatic = 'אוטומט' in gear_box or 'automatic' in gear_box.lower()
        
        # Get engine details
        engine_volume = listing.get('engineVolume')
        horse_power = listing.get('horsePower')
        if price is not None:
            if isinstance(price, str):
                # Remove non-numeric characters except decimal point
                price_str = re.sub(r'[^\d.]', '', price)
                try:
                    price = float(price_str) if price_str else None
                except (ValueError, TypeError):
                    price = None
            elif not isinstance(price, (int, float)):
                price = None
        
        # Extract year
        year = listing.get('year')
        if year and isinstance(year, str):
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None
        
        # Extract mileage
        mileage = listing.get('mileage')
        if mileage and isinstance(mileage, str):
            # Remove non-numeric characters
            mileage = re.sub(r'\D', '', mileage)
            try:
                mileage = int(mileage) if mileage else None
            except (ValueError, TypeError):
                mileage = None
        
        # Extract fuel type
        fuel_type = None
        if 'fuel_type' in listing:
            fuel_type = listing['fuel_type']
            if isinstance(fuel_type, dict):
                fuel_type = fuel_type.get('text', '')
            fuel_type = str(fuel_type).strip() if fuel_type else None
        
        # Extract body type
        body_type = None
        if 'body_type' in listing:
            body_type = listing['body_type']
            if isinstance(body_type, dict):
                body_type = body_type.get('text', '')
            body_type = str(body_type).strip() if body_type else None
        
        # Extract engine volume if available
        engine_volume_cc = None
        if 'engine_volume' in listing:
            engine_volume = listing['engine_volume']
            if isinstance(engine_volume, dict):
                engine_volume = engine_volume.get('text', '')
            if engine_volume and isinstance(engine_volume, str):
                try:
                    # Extract numbers from string (e.g., "2.0L" -> 2000)
                    numbers = re.findall(r'\d+\.?\d*', engine_volume)
                    if numbers:
                        # Convert to cc (assuming the number is in liters)
                        engine_volume_cc = int(float(numbers[0]) * 1000)
                except (ValueError, TypeError):
                    pass
        
        # Extract image URL
        image_url = listing.get('image_url', '')
        if image_url and not image_url.startswith(('http://', 'https://')):
            image_url = ''
        
        # Extract location
        location = listing.get('location', '')
        
        # Create normalized listing
        normalized = {
            'source_id': str(listing_id),
            'source': 'yad2',
            'title': title,
            'description': description,
            'price': price,
            'year': year,
            'mileage': mileage,
            'fuel_type': fuel_type,
            'body_type': body_type,
            'engine_volume_cc': engine_volume_cc,
            'image_url': image_url,
            'location': location,
            'raw_data': listing  # Keep original data for reference
        }
        
        return normalized
        
    except Exception as e:
        logger.error(f"Error normalizing listing: {str(e)}", exc_info=True)
        return None

def get_or_create_brand(db_session: Session, brand_name: str) -> Optional[Brand]:
    """Get an existing brand or create a new one if it doesn't exist."""
    if not brand_name:
        return None
        
    try:
        # Normalize the brand name (convert to lowercase and remove extra spaces)
        normalized_name = ' '.join(brand_name.strip().lower().split())
        
        # Try to find existing brand by normalized name
        brand = db_session.query(Brand).filter(
            func.lower(Brand.normalized_name) == normalized_name
        ).first()
        
        if not brand:
            # Create new brand
            brand = Brand(
                name=brand_name.strip(),
                normalized_name=normalized_name,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db_session.add(brand)
            db_session.commit()
            db_session.refresh(brand)
            logger.info(f"Created new brand: {brand_name}")
        
        return brand
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error getting/creating brand {brand_name}: {e}")
        return None

def get_or_create_model(db_session: Session, model_name: str, brand_id: int) -> Optional[Model]:
    """Get or create a model for a brand."""
    if not model_name or not isinstance(model_name, str) or not brand_id:
        logger.warning(f"Invalid model name or brand_id: {model_name}, {brand_id}")
        return None
        
    try:
        normalized_name = model_name.lower().strip()
        model = db_session.query(Model).filter(
            Model.brand_id == brand_id,
            func.lower(Model.name) == normalized_name
        ).first()
        
        if not model and model_name != 'Unknown':
            model = Model(
                name=model_name,
                normalized_name=normalized_name,
                brand_id=brand_id
            )
            db_session.add(model)
            db_session.commit()
            db_session.refresh(model)
            logger.info(f"Created new model: {model_name} for brand_id {brand_id}")
            
        return model
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error getting/creating model {model_name} for brand_id {brand_id}: {e}")
        return None

def extract_brand_and_model(title: str) -> tuple[str, str]:
    """Extract brand and model from the title."""
    if not title:
        return None, None
    
    # Split the title into words
    words = title.split()
    
    # Simple heuristic: first word is usually the brand, second is the model
    if len(words) >= 2:
        return words[0], words[1]
    elif len(words) == 1:
        return words[0], None
    return None, None

def save_listing_to_db(db_session: Session, listing_data: Dict) -> bool:
    """Save a single listing to the database."""
    if not listing_data or 'id' not in listing_data:
        logger.warning("Invalid listing data: missing 'id' field")
        return False
        
    listing_id = listing_data.get('id')
    
    try:
        # Check if listing already exists
        existing_listing = db_session.query(Listing).filter(Listing.yad2_id == str(listing_id)).first()
        if existing_listing:
            logger.debug(f"Listing {listing_id} already exists, skipping...")
            return True  # Return True since the listing exists, no need to process again
        
        # Get or create brand
        manufacturer = listing_data.get('manufacturer', 'Unknown')
        if not manufacturer or not isinstance(manufacturer, str):
            manufacturer = 'Unknown'
            
        brand = get_or_create_brand(db_session, manufacturer)
        if not brand:
            logger.warning(f"Could not process brand for listing {listing_id}")
            return False
        
        # Get or create model
        model_name = listing_data.get('model', 'Unknown')
        if not model_name or not isinstance(model_name, str):
            model_name = 'Unknown'
            
        model = get_or_create_model(db_session, model_name, brand.id)
        if not model:
            logger.warning(f"Could not process model {model_name} for brand {brand.name}")
            return False
        
        # Extract and validate fields
        title = listing_data.get('title', f"{brand.name} {model.name}")
        description = listing_data.get('description', '')
        
        try:
            price = float(listing_data.get('price', 0)) if listing_data.get('price') else 0
        except (ValueError, TypeError):
            price = 0
            
        try:
            year = int(listing_data.get('year', 0)) if listing_data.get('year') else None
        except (ValueError, TypeError):
            year = None
            
        try:
            km = int(str(listing_data.get('km', '0')).replace(',', '').replace('.', '')) if listing_data.get('km') else 0
        except (ValueError, TypeError):
            km = 0
            
        fuel_type = str(listing_data.get('fuel_type', ''))[:50]  # Limit length
        body_type = str(listing_data.get('body_type', ''))[:50]  # Limit length
        
        # Create new listing
        new_listing = Listing(
            yad2_id=str(listing_id),
            title=title[:255],  # Ensure title is not too long
            description=description[:4000],  # Limit description length
            price=price,
            brand_id=brand.id,
            model_id=model.id,
            year=year,
            km=km,
            fuel_type=fuel_type,
            body_type=body_type
        )
        
        db_session.add(new_listing)
        db_session.commit()
        logger.info(f"Saved listing {listing_id} to database")
        return True
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error saving listing {listing_id} to database: {e}", exc_info=True)
        return False

def save_car_listing_to_db(db_session: Session, listing_data: Dict) -> bool:
    """Save a single car listing to the database."""
    try:
        # Check if listing already exists by yad2_id
        existing = db_session.query(CarListing).filter_by(
            yad2_id=str(listing_data['source_id'])
        ).first()

        if existing:
            # Update existing record
            car_data = {
                'title': listing_data.get('title', ''),
                'description': listing_data.get('description', ''),
                'price': listing_data.get('price'),
                'year': listing_data.get('year'),
                'mileage': listing_data.get('mileage'),
                'engine_volume_cc': listing_data.get('engine_volume_cc'),
                'fuel_type': listing_data.get('fuel_type', ''),
                'body_type': listing_data.get('body_type', ''),
                'image_url': listing_data.get('image_url', ''),
                'location': listing_data.get('location', ''),
                'brand_id': listing_data.get('brand_id'),
                'model_id': listing_data.get('model_id'),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            for key, value in car_data.items():
                if hasattr(existing, key) and key != 'id':
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            logger.debug(f"Updated existing listing: {listing_data['source_id']}")
        else:
            # Create new record
            car_data = {
                'yad2_id': listing_data.get('source_id'),
                'title': listing_data.get('title', ''),
                'description': listing_data.get('description', ''),
                'price': listing_data.get('price'),
                'year': listing_data.get('year'),
                'mileage': listing_data.get('mileage'),
                'engine_volume_cc': listing_data.get('engine_volume_cc'),
                'fuel_type': listing_data.get('fuel_type', ''),
                'body_type': listing_data.get('body_type', ''),
                'image_url': listing_data.get('image_url', ''),
                'location': listing_data.get('location', ''),
                'brand_id': listing_data.get('brand_id'),
                'model_id': listing_data.get('model_id'),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            car = CarListing(**car_data)
            db_session.add(car)
            logger.debug(f"Added new listing: {listing_data['source_id']}")
            
        db_session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error saving listing to database: {str(e)}", exc_info=True)
        db_session.rollback()
        return False

def main():
    """Main function to fetch and save car listings."""
    db_session = None
    try:
        logger.info("Starting database seeding process...")
        
        # Initialize database session
        db_session = SessionLocal()
        
        # Track statistics
        total_processed = 0
        total_saved = 0
        page = 1
        max_pages = 10  # Safety limit to prevent infinite loops
        
        logger.info("Starting to fetch car listings...")
        
        while page <= max_pages:
            try:
                logger.info(f"Fetching page {page}...")
                listings = fetch_listings(page=page)
                
                if not listings:
                    logger.info("No more listings found.")
                    break
                    
                logger.info(f"Processing {len(listings)} listings from page {page}")
                
                for listing in listings:
                    try:
                        total_processed += 1
                        normalized = normalize_listing(listing)
                        if normalized:
                            if save_listing_to_db(db_session, normalized):
                                total_saved += 1
                                
                            # Commit after each successful save
                            db_session.commit()
                        
                        # Log progress every 10 listings
                        if total_processed % 10 == 0:
                            logger.info(f"Processed {total_processed} listings, saved {total_saved}")
                            
                    except Exception as e:
                        db_session.rollback()
                        logger.error(f"Error processing listing: {e}", exc_info=True)
                        continue
                        
            except Exception as e:
                logger.error(f"Error fetching/processing page {page}: {e}", exc_info=True)
                break
                
            page += 1
            
        logger.info(f"Database seeding completed. Processed {total_processed} listings, saved {total_saved} new entries.")
        
    except Exception as e:
        logger.error(f"Fatal error in main process: {e}", exc_info=True)
        if db_session:
            db_session.rollback()
        raise
        
    finally:
        if db_session:
            try:
                db_session.close()
                logger.info("Database connection closed.")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
        
        logger.info("Seeding process finished.")

if __name__ == "__main__":
    main()