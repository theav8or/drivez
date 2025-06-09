from typing import List, Dict, Optional
from sqlalchemy.orm import Session, joinedload
from app.db.models.car import CarListing as CarListingModel, CarBrand, CarModel
from app.schemas.car import CarListing
from app.db.session import get_db

class CarService:
    """Service class for car-related operations."""

    async def get_listings(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        **filters
    ) -> List[CarListing]:
        """
        Retrieve a list of car listings with optional filtering.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Optional filters (brand, model, year, etc.)
            
        Returns:
            List of car listings
        """
        # Start with base query and join with brand and model
        query = db.query(CarListingModel).options(
            joinedload(CarListingModel.brand),
            joinedload(CarListingModel.model)
        )
        
        # Apply filters if provided
        if 'brand' in filters and filters['brand']:
            query = query.join(CarBrand).filter(CarBrand.name == filters['brand'])
        if 'model' in filters and filters['model']:
            query = query.join(CarModel).filter(CarModel.name == filters['model'])
        if 'min_year' in filters and filters['min_year']:
            query = query.filter(CarListingModel.year >= filters['min_year'])
        if 'max_year' in filters and filters['max_year']:
            query = query.filter(CarListingModel.year <= filters['max_year'])
        if 'min_price' in filters and filters['min_price'] is not None:
            query = query.filter(CarListingModel.price >= filters['min_price'])
        if 'max_price' in filters and filters['max_price'] is not None:
            query = query.filter(CarListingModel.price <= filters['max_price'])
            
        # Apply pagination and execute query
        listings = query.offset(skip).limit(limit).all()
        return listings
    
    async def get_listing_by_id(self, db: Session, listing_id: int) -> Optional[CarListing]:
        """
        Retrieve a single car listing by ID.
        
        Args:
            db: Database session
            listing_id: ID of the listing to retrieve
            
        Returns:
            The car listing if found, None otherwise
        """
        listing = db.query(CarListingModel).options(
            joinedload(CarListingModel.brand),
            joinedload(CarListingModel.model)
        ).filter(CarListingModel.id == listing_id).first()
        
        return listing
    
    async def get_filters(self, db: Session) -> Dict:
        """
        Get available filters for car listings.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary of available filters with their values
        """
        # Get unique brands
        brands = [b.name for b in db.query(CarBrand).distinct().all() if b.name]
        
        # Get unique models (for each brand)
        models = {}
        for brand_name in brands:
            brand = db.query(CarBrand).filter(CarBrand.name == brand_name).first()
            if brand:
                brand_models = [m.name for m in db.query(CarModel)
                                .filter(CarModel.brand_id == brand.id)
                                .distinct().all() if m.name]
                if brand_models:
                    models[brand_name] = brand_models
        
        # Get min/max year and price
        min_year = db.query(db.func.min(CarListingModel.year)).scalar() or 0
        max_year = db.query(db.func.max(CarListingModel.year)).scalar() or 0
        min_price = db.query(db.func.min(CarListingModel.price)).scalar() or 0
        max_price = db.query(db.func.max(CarListingModel.price)).scalar() or 0
        
        return {
            'brands': sorted(brands),
            'models': models,
            'years': {'min': min_year, 'max': max_year},
            'prices': {'min': min_price, 'max': max_price}
        }