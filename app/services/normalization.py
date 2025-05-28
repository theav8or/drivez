from typing import Dict, Optional
import rapidfuzz
from app.db.models import CarBrand, CarModel
from app.core.config import settings

async def normalize_car_data(raw_data: Dict) -> Optional[Dict]:
    """
    Normalize raw car listing data using fuzzy matching and predefined dictionaries.
    """
    try:
        # Extract basic information
        title = raw_data.get("title", "")
        price_str = raw_data.get("price", "")
        url = raw_data.get("url")
        
        # Normalize price
        price = _normalize_price(price_str)
        if price is None:
            return None
        
        # Extract brand and model from title
        brand, model = _extract_brand_model(title)
        if not brand or not model:
            return None
        
        # Normalize location (if available)
        location = raw_data.get("location", "")
        normalized_location = _normalize_location(location)
        
        # Extract year (if available)
        year = _extract_year(title)
        
        return {
            "title": title,
            "brand": brand,
            "model": model,
            "price": price,
            "location": normalized_location,
            "year": year,
            "url": url,
            "source": raw_data.get("source", "unknown")
        }
    except Exception as e:
        print(f"Error normalizing data: {str(e)}")
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
