from typing import List, Dict, Optional
from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.car_listing import CarListing
from app.models.car_listing_model import CarListing as CarListingModel

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
        query = query.filter(CarListingModel.brand.ilike(f"%{brand}%"))
    if model:
        query = query.filter(CarListingModel.model.ilike(f"%{model}%"))
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
    
    return listings

@router.get("/brands", response_model=List[Dict[str, str]])
async def get_brands(db: Session = Depends(get_db)):
    """Get list of available car brands"""
    brands = db.query(CarListingModel.brand).distinct().all()
    return [{"name": brand[0]} for brand in brands if brand[0]]

@router.get("/models/{brand}", response_model=List[Dict[str, str]])
async def get_models(brand: str, db: Session = Depends(get_db)):
    """Get list of models for a specific brand"""
    models = db.query(CarListingModel.model).filter(
        CarListingModel.brand.ilike(f"%{brand}%")
    ).distinct().all()
    return [{"name": model[0]} for model in models if model[0]]
