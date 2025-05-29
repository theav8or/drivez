from typing import List, Dict, Optional
from fastapi import Depends, APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.car import CarListing as CarListingModel, CarBrand, CarModel
from app.schemas.car import CarListing, CarBrand as CarBrandSchema, CarModel as CarModelSchema

# Create router
router = APIRouter()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

__all__ = ['router']

# API router instance for main app to include
api_router = router

@router.get("/listings", response_model=List[CarListing])
async def get_listings(
    db: Session = Depends(get_db),
    brand: Optional[str] = None,
    model: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    location: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    """
    Get paginated list of car listings with optional filters.
    """
    query = db.query(CarListingModel)
    
    # Apply filters
    if brand:
        query = query.join(CarBrand).filter(CarBrand.name.ilike(f"%{brand}%"))
    if model:
        query = query.join(CarModel).filter(CarModel.name.ilike(f"%{model}%"))
    if min_price is not None:
        query = query.filter(CarListingModel.price >= min_price)
    if max_price is not None:
        query = query.filter(CarListingModel.price <= max_price)
    if min_year is not None:
        query = query.filter(CarListingModel.year >= min_year)
    if max_year is not None:
        query = query.filter(CarListingModel.year <= max_year)
    if location:
        query = query.filter(CarListingModel.location.ilike(f"%{location}%"))
    
    # Pagination
    skip = (page - 1) * limit
    listings = query.offset(skip).limit(limit).all()
    
    # Convert SQLAlchemy models to Pydantic models
    return [
        CarListing(
            id=listing.id,
            yad2_id=listing.yad2_id,
            title=listing.title,
            description=listing.description,
            price=listing.price,
            year=listing.year,
            mileage=listing.mileage,
            fuel_type=listing.fuel_type,
            transmission=listing.transmission,
            body_type=listing.body_type,
            color=listing.color,
            status=listing.status,
            brand_id=listing.brand_id,
            model_id=listing.model_id,
            created_at=listing.created_at,
            updated_at=listing.updated_at,
            last_scraped_at=listing.last_scraped_at,
            brand=CarBrandSchema(
                id=listing.brand.id,
                name=listing.brand.name,
                normalized_name=listing.brand.normalized_name
            ) if listing.brand else None,
            model=CarModelSchema(
                id=listing.model.id,
                name=listing.model.name,
                normalized_name=listing.model.normalized_name,
                brand_id=listing.model.brand_id
            ) if listing.model else None
        )
        for listing in listings
    ]

@router.get("/brands", response_model=List[Dict[str, str]])
async def get_brands(db: Session = Depends(get_db)):
    """Get list of available car brands"""
    brands = db.query(CarBrand).distinct().all()
    return [{"name": brand.name} for brand in brands if brand.name]

@router.get("/models/{brand}", response_model=List[Dict[str, str]])
async def get_models(brand: str, db: Session = Depends(get_db)):
    """Get list of models for a specific brand"""
    models = db.query(CarModel).join(CarBrand).filter(
        CarBrand.name.ilike(f"%{brand}%")
    ).distinct().all()
    return [{"name": model.name} for model in models if model.name]
