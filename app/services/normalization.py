from typing import Dict, Optional, Tuple
import rapidfuzz
from app.db.models import CarBrand, CarModel, CarListing
from app.core.config import settings
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

async def normalize_car_data(raw_data: Dict, db: Session = None) -> Optional[Dict]:
    """
    Normalize raw car listing data and ensure it matches the CarListing model.
    """
    try:
        # Get or create database session
        local_session = None
        if db is None:
            local_session = SessionLocal()
            db = local_session
            
        try:
            # Extract basic information
            yad2_id = raw_data.get("yad2_id")
            if not yad2_id:
                return None
                
            # Get or create brand
            brand_name = raw_data.get("brand", "").strip()
            if not brand_name:
                return None
                
            brand = db.query(CarBrand).filter(CarBrand.name == brand_name).first()
            if not brand:
                brand = CarBrand(name=brand_name, normalized_name=brand_name.lower())
                db.add(brand)
                db.commit()
                db.refresh(brand)
            
            # Get or create model
            model_name = raw_data.get("model", "").strip()
            if not model_name:
                return None
                
            model = db.query(CarModel).filter(
                CarModel.name == model_name,
                CarModel.brand_id == brand.id
            ).first()
            
            if not model:
                model = CarModel(
                    name=model_name,
                    normalized_name=model_name.lower(),
                    brand_id=brand.id
                )
                db.add(model)
                db.commit()
                db.refresh(model)
            
            # Normalize price
            price = float(raw_data.get("price", 0))
            if price <= 0:
                return None
            
            # Extract year
            year = int(raw_data.get("year", 0))
            if year < 1900 or year > 2100:  # Basic validation
                year = None
                
            # Extract mileage (convert to km if needed)
            mileage = int(raw_data.get("mileage", 0))
            
            # Prepare the result
            result = {
                "yad2_id": yad2_id,
                "title": raw_data.get("title", "").strip(),
                "price": price,
                "year": year,
                "mileage": mileage,
                "fuel_type": raw_data.get("fuel_type", "").strip(),
                "transmission": raw_data.get("transmission", "").strip(),
                "body_type": raw_data.get("body_type", "").strip(),
                "color": raw_data.get("color", "").strip(),
                "url": raw_data.get("url", "").strip(),
                "image_url": raw_data.get("image_url", "").strip(),
                "location": raw_data.get("location", "").strip(),
                "brand_id": brand.id,
                "model_id": model.id
            }
            
            # Ensure required fields are present
            if not all([result["yad2_id"], result["title"], result["price"] > 0]):
                return None
                
            return result
            
        finally:
            if local_session:
                local_session.close()
                
    except Exception as e:
        print(f"Error normalizing car data: {str(e)}")
        return None

def _normalize_price(price_str: str) -> Optional[float]:
    """Extract and normalize price from string"""
    try:
        price_str = price_str.replace("₪", "").replace(",", "").strip()
        price = float(price_str)
        return price
    except:
        return None

def _extract_brand_model(title: str) -> tuple:
    """Extract brand and model from title using fuzzy matching"""
    # TODO: Load brand and model dictionaries
    brands = ["toyota", "honda", "bmw", "mercedes"]
    models = {"toyota": ["corolla", "camry"], "honda": ["civic", "accord"]}
    
    # Find best matching brand
    brand_scores = {
        brand: rapidfuzz.fuzz.ratio(title.lower(), brand)
        for brand in brands
    }
    best_brand = max(brand_scores, key=brand_scores.get)
    
    # Find best matching model for the brand
    model_scores = {
        model: rapidfuzz.fuzz.ratio(title.lower(), model)
        for model in models.get(best_brand, [])
    }
    best_model = max(model_scores, key=model_scores.get)
    
    return best_brand, best_model

def _normalize_location(location: str) -> str:
    """Normalize location using predefined mappings"""
    location_mapping = {
        "tel aviv": "Tel Aviv",
        "jerusalem": "Jerusalem",
        "haifa": "Haifa"
    }
    
    for key in location_mapping:
        if key.lower() in location.lower():
            return location_mapping[key]
    
    return location

def _extract_year(title: str) -> Optional[int]:
    """Extract year from title"""
    try:
        # Look for 4-digit number that looks like a year
        for word in title.split():
            if word.isdigit() and 1900 <= int(word) <= 2025:
                return int(word)
        return None
    except:
        return None
