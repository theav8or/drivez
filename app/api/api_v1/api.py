from fastapi import APIRouter, Depends
from typing import List
from app.db.models import CarListing
from app.services.normalization import normalize_car_data
from app.core.config import settings

router = APIRouter()

@router.get("/listings", response_model=List[CarListing])
async def get_listings(
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
    # TODO: Implement database query with filters
    return []

@router.get("/brands")
async def get_brands():
    """Get list of available car brands"""
    # TODO: Implement database query
    return []

@router.get("/models/{brand}")
async def get_models(brand: str):
    """Get list of models for a specific brand"""
    # TODO: Implement database query
    return []
