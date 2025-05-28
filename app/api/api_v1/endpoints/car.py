from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict
from app.db.session import get_db
from app.schemas.car import CarListing
from app.services.car import CarService
from app.services.scraping import ScrapingService

router = APIRouter()

car_service = CarService()
scraping_service = ScrapingService()

@router.get("/listings", response_model=List[CarListing])
async def get_listings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve car listings with pagination.
    """
    listings = await car_service.get_listings(db, skip=skip, limit=limit)
    return listings

@router.post("/scrape")
async def trigger_scrape(
    db: Session = Depends(get_db)
):
    """
    Trigger a new scraping job for car listings.
    """
    try:
        await scraping_service.trigger_scrape_yad2(db)
        return {"message": "Scraping job started successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filters", response_model=Dict)
async def get_filters(
    db: Session = Depends(get_db)
):
    """
    Get available filters for car listings.
    """
    filters = await car_service.get_filters(db)
    return filters
