from typing import List, Dict, Optional
from pydantic import BaseModel
from fastapi import Depends, APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.car import CarListing as CarListingModel, CarBrand, CarModel
from .endpoints import scraper_v2

# Response model for the listings endpoint
class CarListingResponse(BaseModel):
    id: int
    title: str
    price: Optional[float] = None
    year: Optional[int] = None
    mileage: Optional[int] = None
    engine_volume: Optional[int] = None
    color: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    test_until: Optional[str] = None
    description: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    body_type: Optional[str] = None
    hand: Optional[int] = None
    horsepower: Optional[int] = None
    doors: Optional[int] = None
    seats: Optional[int] = None
    status: Optional[str] = None
    is_imported: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None

    class Config:
        from_attributes = True

# Create the main router for API v1 with prefix /api/v1
api_router = APIRouter(prefix="/api/v1", tags=["listings"])

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Define the listings endpoints directly in the router
@api_router.get("/listings", response_model=List[CarListingResponse], tags=["listings"])
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
    
    # Join with brand and model tables to get the names
    query = query.outerjoin(CarBrand, CarListingModel.brand_id == CarBrand.id)\
                 .outerjoin(CarModel, CarListingModel.model_id == CarModel.id)
    
    # Apply filters
    if brand:
        query = query.filter(CarBrand.name == brand)
    if model:
        query = query.filter(CarModel.name == model)
    if min_price is not None:
        query = query.filter(CarListingModel.price >= min_price)
    if max_price is not None:
        query = query.filter(CarListingModel.price <= max_price)
    if min_year is not None:
        query = query.filter(CarListingModel.year >= min_year)
    if max_year is not None:
        query = query.filter(CarListingModel.year <= max_year)
    if location:
        query = query.filter(
            (CarListingModel.city.ilike(f"%{location}%")) | 
            (CarListingModel.neighborhood.ilike(f"%{location}%"))
        )
    
    # Apply pagination
    offset = (page - 1) * limit
    listings = query.offset(offset).limit(limit).all()
    
    return [
        CarListingResponse(
            id=listing.id,
            title=listing.title,
            price=float(listing.price) if listing.price else None,
            year=listing.year,
            mileage=listing.mileage,
            engine_volume=listing.engine_volume,
            color=listing.color,
            city=listing.city,
            neighborhood=listing.neighborhood,
            test_until=listing.test_until.isoformat() if listing.test_until else None,
            description=listing.description,
            fuel_type=listing.fuel_type,
            transmission=listing.transmission,
            body_type=listing.body_type,
            hand=listing.hand,
            horsepower=listing.horsepower,
            doors=listing.doors,
            seats=listing.seats,
            status=listing.status.value if listing.status else None,
            is_imported=listing.is_imported,
            created_at=listing.created_at.isoformat() if listing.created_at else None,
            updated_at=listing.updated_at.isoformat() if listing.updated_at else None,
            brand=listing.brand.name if listing.brand else None,
            model=listing.model.name if listing.model else None
        )
        for listing in listings
    ]

# Include the scraper router
api_router.include_router(scraper_v2.router, prefix="", tags=["scraper"])

__all__ = ['api_router']

@api_router.get("/listings/{listing_id}", response_model=CarListingResponse, tags=["listings"])
async def get_listing(
    listing_id: int,
    db: Session = Depends(get_db)
):
    """Get a single car listing by ID"""
    listing = db.query(CarListingModel)\
                .outerjoin(CarBrand, CarListingModel.brand_id == CarBrand.id)\
                .outerjoin(CarModel, CarListingModel.model_id == CarModel.id)\
                .filter(CarListingModel.id == listing_id)\
                .first()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing with ID {listing_id} not found"
        )
    
    # Convert SQLAlchemy model to Pydantic model
    return CarListingResponse(
        id=listing.id,
        title=listing.title,
        price=float(listing.price) if listing.price else None,
        year=listing.year,
        mileage=listing.mileage,
        engine_volume=listing.engine_volume,
        color=listing.color,
        city=listing.city,
        neighborhood=listing.neighborhood,
        test_until=listing.test_until.isoformat() if listing.test_until else None,
        description=listing.description,
        fuel_type=listing.fuel_type,
        transmission=listing.transmission,
        body_type=listing.body_type,
        hand=listing.hand,
        horsepower=listing.horsepower,
        doors=listing.doors,
        seats=listing.seats,
        status=listing.status.value if listing.status else None,
        is_imported=listing.is_imported,
        created_at=listing.created_at.isoformat() if listing.created_at else None,
        updated_at=listing.updated_at.isoformat() if listing.updated_at else None,
        brand=listing.brand.name if listing.brand else None,
        model=listing.model.name if listing.model else None
    )

@api_router.get("/brands", response_model=List[Dict[str, str]], tags=["listings"])
async def get_brands(db: Session = Depends(get_db)):
    """Get list of available car brands"""
    brands = db.query(CarBrand).distinct().all()
    return [{"id": str(brand.id), "name": brand.name} for brand in brands]

@api_router.get("/models/{brand}", response_model=List[Dict[str, str]], tags=["listings"])
async def get_models(brand: str, db: Session = Depends(get_db)):
    """Get list of models for a specific brand"""
    models = db.query(CarModel).join(CarBrand).filter(
        CarBrand.name == brand
    ).all()
    return [{"id": str(model.id), "name": model.name} for model in models]

__all__ = ['api_router']
