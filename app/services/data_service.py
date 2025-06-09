"""
Data service for handling database operations including initialization, data population,
and cleanup of car listings.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.db import get_db_session
from app.db.models.car import (
    CarBrand, CarModel, CarListing, CarListingHistory, CarStatus
)
from app.core.config import settings
from app.core.logging import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

class DataService:
    """Service for handling database operations related to car listings."""
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the data service with an optional database session.
        
        Args:
            db: Optional SQLAlchemy session. If not provided, a new session will be created.
        """
        self._db = db
        self._session_owner = db is None
    
    @property
    def db(self) -> Session:
        """Lazy-load the database session."""
        if not hasattr(self, '_db') or self._db is None:
            self._db = next(get_db_session())
            self._session_owner = True
        return self._db
    
    def __enter__(self):
        """Enable usage as a context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up the session when used as a context manager."""
        if self._session_owner and self._db is not None:
            try:
                if exc_type is not None:
                    self._db.rollback()
                else:
                    self._db.commit()
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
                self._db.rollback()
            finally:
                self._db.close()
                self._db = None
    
    def ensure_initial_data(self) -> bool:
        """Ensure that initial data is populated in the database.
        
        Returns:
            bool: True if data was populated or already exists, False on error.
        """
        logger.info("Ensuring initial data is populated in the database")
        try:
            # Create a list of common car brands and their models
            brands_models = {
                'Toyota': ['Corolla', 'Camry', 'RAV4', 'Prius', 'Hilux', 'Land Cruiser', 'Yaris', 'C-HR', 'Corolla Cross', 'Highlander'],
                'Mazda': ['3', '6', 'CX-5', 'CX-30', 'CX-9', 'MX-5', 'CX-3', 'CX-60', 'CX-90'],
                'Hyundai': ['Tucson', 'Kona', 'i30', 'i20', 'i10', 'i40', 'Santa Fe', 'Palisade', 'IONIQ', 'IONIQ 5', 'IONIQ 6'],
                'Kia': ['Sportage', 'Sorento', 'Picanto', 'Rio', 'Ceed', 'Niro', 'EV6', 'EV9', 'Seltos', 'Stonic'],
                'Mitsubishi': ['Outlander', 'ASX', 'Eclipse Cross', 'Pajero', 'L200'],
                'Subaru': ['Forester', 'Outback', 'XV', 'Impreza', 'Legacy', 'WRX', 'BRZ'],
                'Honda': ['Civic', 'CR-V', 'Accord', 'HR-V', 'Jazz', 'e', 'City'],
                'Nissan': ['Qashqai', 'X-Trail', 'Juke', 'Leaf', 'Micra', 'Note', 'Navara', 'Ariya'],
                'Suzuki': ['Swift', 'Vitara', 'S-Cross', 'Ignis', 'Jimny', 'Baleno'],
                'Volkswagen': ['Golf', 'Tiguan', 'Passat', 'Polo', 'T-Roc', 'T-Cross', 'ID.3', 'ID.4', 'ID.5', 'ID. Buzz'],
                'BMW': ['3 Series', '5 Series', 'X1', 'X3', 'X5', 'i4', 'iX', 'i7', '2 Series', '4 Series'],
                'Mercedes': ['A-Class', 'C-Class', 'E-Class', 'GLA', 'GLC', 'GLE', 'EQS', 'EQE', 'S-Class'],
                'Audi': ['A3', 'A4', 'A6', 'Q3', 'Q5', 'Q7', 'e-tron', 'Q4 e-tron', 'e-tron GT'],
                'Volvo': ['XC40', 'XC60', 'XC90', 'S60', 'S90', 'V60', 'V90', 'C40', 'EX30', 'EX90'],
                'Skoda': ['Octavia', 'Superb', 'Kodiaq', 'Karoq', 'Kamiq', 'Enyaq', 'Scala', 'Fabia'],
                'SEAT': ['Leon', 'Arona', 'Ateca', 'Tarraco', 'Ibiza', 'Cupra Formentor', 'Cupra Born'],
                'Renault': ['Clio', 'Megane', 'Captur', 'Kadjar', 'Austral', 'Arkana', 'Zoe', 'Twingo'],
                'Peugeot': ['208', '2008', '308', '3008', '5008', 'e-208', 'e-2008', 'e-308', 'e-3008'],
                'Citroen': ['C3', 'C3 Aircross', 'C4', 'C5 Aircross', 'e-C4', 'e-C4 X', 'e-C4 Aircross'],
                'Ford': ['Fiesta', 'Focus', 'Puma', 'Kuga', 'Mustang Mach-E', 'Explorer', 'Tourneo Connect'],
                'Opel': ['Corsa', 'Astra', 'Mokka', 'Grandland', 'Crossland', 'Combo', 'Vivaro']
            }
            
            # Track if we added any new data
            added_data = False
            
            # Add brands and models if they don't exist
            for brand_name, models in brands_models.items():
                # Check if brand exists
                brand = self.db.query(CarBrand).filter(
                    func.lower(CarBrand.name) == brand_name.lower()
                ).first()
                
                if not brand:
                    # Brand doesn't exist, create it
                    brand = CarBrand(
                        name=brand_name,
                        normalized_name=brand_name.lower().replace(' ', '_')
                    )
                    self.db.add(brand)
                    self.db.flush()  # Get the brand ID
                    logger.info(f"Added new brand: {brand_name}")
                    added_data = True
                
                # Add models for this brand
                for model_name in models:
                    # Check if model exists for this brand
                    model = self.db.query(CarModel).filter(
                        CarModel.brand_id == brand.id,
                        func.lower(CarModel.name) == model_name.lower()
                    ).first()
                    
                    if not model:
                        # Model doesn't exist, create it
                        model = CarModel(
                            name=model_name,
                            normalized_name=model_name.lower().replace(' ', '_'),
                            brand_id=brand.id
                        )
                        self.db.add(model)
                        logger.info(f"  - Added model: {brand_name} {model_name}")
                        added_data = True
            
            if added_data:
                self.db.commit()
                logger.info("Initial data population completed successfully")
            else:
                logger.info("Initial data already exists, no changes made")
                
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring initial data: {e}", exc_info=True)
            self.db.rollback()
            return False
            # Check if we have any brands in the database
            brand_count = self.db.query(CarBrand).count()
            
            if brand_count == 0:
                logger.info("No brands found in database, populating initial data...")
                self._populate_initial_brands_and_models()
                logger.info("Successfully populated initial data")
            else:
                logger.debug("Database already contains data, skipping initial population")
                
        except Exception as e:
            logger.error(f"Error ensuring initial data: {e}")
            raise
    
    def _populate_initial_brands_and_models(self) -> None:
        """Populate initial brands and models in the database."""
        # Common car brands and their models
        brands_and_models = {
            'Toyota': ['Corolla', 'Camry', 'RAV4', 'Prius', 'Hilux', 'Yaris', 'C-HR', 'Land Cruiser'],
            'Honda': ['Civic', 'Accord', 'CR-V', 'HR-V', 'Jazz', 'Fit', 'Pilot', 'Odyssey'],
            'Mazda': ['3', '6', 'CX-5', 'CX-30', 'MX-5', 'CX-9', 'CX-3', 'BT-50'],
            'Hyundai': ['i30', 'Tucson', 'Kona', 'i20', 'i10', 'Elantra', 'Santa Fe', 'Tucson'],
            'Kia': ['Sportage', 'Picanto', 'Rio', 'Ceed', 'Niro', 'Sorento', 'Soul', 'Stonic'],
            'Ford': ['Fiesta', 'Focus', 'Kuga', 'Puma', 'Ranger', 'Mustang', 'Explorer', 'Edge'],
            'Volkswagen': ['Golf', 'Polo', 'Tiguan', 'Passat', 'T-Roc', 'T-Cross', 'Arteon', 'ID.4'],
            'BMW': ['3 Series', '5 Series', 'X1', 'X3', 'X5', '1 Series', '2 Series', '4 Series'],
            'Mercedes': ['A-Class', 'C-Class', 'E-Class', 'GLA', 'GLC', 'GLE', 'S-Class', 'CLA'],
            'Audi': ['A3', 'A4', 'A6', 'Q3', 'Q5', 'Q7', 'Q8', 'e-tron']
        }
        
        try:
            # Add brands and models if they don't exist
            for brand_name, models in brands_and_models.items():
                # Check if brand exists
                brand = self.db.query(CarBrand).filter(CarBrand.name == brand_name).first()
                
                if not brand:
                    brand = CarBrand(
                        name=brand_name,
                        normalized_name=brand_name.lower()
                    )
                    self.db.add(brand)
                    self.db.flush()  # Flush to get the brand ID
                    logger.info(f"Added brand: {brand_name}")
                
                # Add models for the brand
                for model_name in models:
                    model = self.db.query(CarModel).filter(
                        CarModel.brand_id == brand.id,
                        CarModel.name == model_name
                    ).first()
                    
                    if not model:
                        model = CarModel(
                            name=model_name,
                            normalized_name=model_name.lower(),
                            brand_id=brand.id
                        )
                        self.db.add(model)
                        logger.debug(f"  - Added model: {brand_name} {model_name}")
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error populating initial brands and models: {e}")
            raise
    
    def cleanup_old_listings(self, days_old: int = 30) -> Tuple[int, int]:
        """Mark old listings as inactive and create history records.
        
        Args:
            days_old: Number of days after which a listing is considered old
            
        Returns:
            tuple: (number of listings marked as inactive, number of history records created)
        """
        logger.info(f"Cleaning up listings older than {days_old} days")
        
        try:
            # Calculate the cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Find active listings older than cutoff date
            listings_to_deactivate = self.db.query(CarListing).filter(
                CarListing.status == CarStatus.ACTIVE,
                CarListing.updated_at < cutoff_date
            ).all()
            
            deactivated_count = 0
            history_created = 0
            
            for listing in listings_to_deactivate:
                # Create history record
                history = CarListingHistory(
                    listing_id=listing.id,
                    price=listing.price,
                    mileage=listing.mileage,
                    status=CarStatus.INACTIVE,
                    price_change=None,
                    days_on_market=(datetime.utcnow() - listing.scraped_at).days if listing.scraped_at else None
                )
                self.db.add(history)
                
                # Update listing status
                listing.status = CarStatus.INACTIVE
                listing.updated_at = datetime.utcnow()
                
                deactivated_count += 1
                history_created += 1
            
            if deactivated_count > 0:
                self.db.commit()
                logger.info(f"Marked {deactivated_count} listings as inactive")
            
            return deactivated_count, history_created
            
        except Exception as e:
            logger.error(f"Error cleaning up old listings: {e}", exc_info=True)
            self.db.rollback()
            return 0, 0
    
    def upsert_listing(self, listing_data: Dict[str, Any]) -> Tuple[bool, Optional[CarListing]]:
        """Insert or update a car listing.
        
        Args:
            listing_data: Dictionary containing listing data
            
        Returns:
            tuple: (success: bool, listing: Optional[CarListing])
        """
        if not listing_data or 'yad2_id' not in listing_data:
            logger.error("Invalid listing data: missing yad2_id")
            return False, None
            
        try:
            yad2_id = str(listing_data['yad2_id'])
            
            # Check if listing already exists
            listing = self.db.query(CarListing).filter(
                CarListing.yad2_id == yad2_id
            ).first()
            
            is_new = False
            
            if not listing:
                # Create new listing
                is_new = True
                listing = CarListing(
                    yad2_id=yad2_id,
                    status=CarStatus.ACTIVE,
                    scraped_at=datetime.utcnow()
                )
                self.db.add(listing)
            
            # Update listing fields
            for field, value in listing_data.items():
                if hasattr(listing, field) and field != 'id' and field != 'yad2_id':
                    setattr(listing, field, value)
            
            # Handle brand and model
            if 'brand' in listing_data and listing_data['brand']:
                brand = self._get_or_create_brand(listing_data['brand'])
                if brand:
                    listing.brand_id = brand.id
            
            if 'model' in listing_data and listing_data['model'] and listing.brand_id:
                model = self._get_or_create_model(listing_data['model'], listing.brand_id)
                if model:
                    listing.model_id = model.id
            
            # Update timestamps
            listing.updated_at = datetime.utcnow()
            
            # Create history record if price or status changed
            if not is_new and ('price' in listing_data or 'status' in listing_data):
                history = CarListingHistory(
                    listing_id=listing.id,
                    price=listing.price,
                    mileage=listing.mileage,
                    status=listing.status,
                    price_change=None,  # Can be calculated if needed
                    days_on_market=(datetime.utcnow() - listing.scraped_at).days if listing.scraped_at else None
                )
                self.db.add(history)
            
            self.db.commit()
            logger.info(f"{'Created' if is_new else 'Updated'} listing: {listing.title} (ID: {listing.id})")
            return True, listing
            
        except Exception as e:
            logger.error(f"Error upserting listing: {e}", exc_info=True)
            self.db.rollback()
            return False, None
    
    def _get_or_create_brand(self, brand_name: str) -> Optional[CarBrand]:
        """Get or create a car brand by name."""
        if not brand_name:
            return None
            
        try:
            # Try to find existing brand (case-insensitive)
            brand = self.db.query(CarBrand).filter(
                func.lower(CarBrand.name) == brand_name.lower()
            ).first()
            
            if not brand:
                # Create new brand
                brand = CarBrand(
                    name=brand_name,
                    normalized_name=brand_name.lower().replace(' ', '_')
                )
                self.db.add(brand)
                self.db.flush()
                logger.info(f"Created new brand: {brand_name}")
                
            return brand
            
        except Exception as e:
            logger.error(f"Error getting/creating brand {brand_name}: {e}")
            self.db.rollback()
            return None
    
    def _get_or_create_model(self, model_name: str, brand_id: int) -> Optional[CarModel]:
        """Get or create a car model by name and brand ID."""
        if not model_name or not brand_id:
            return None
            
        try:
            # Try to find existing model (case-insensitive)
            model = self.db.query(CarModel).filter(
                CarModel.brand_id == brand_id,
                func.lower(CarModel.name) == model_name.lower()
            ).first()
            
            if not model:
                # Create new model
                model = CarModel(
                    name=model_name,
                    normalized_name=model_name.lower().replace(' ', '_'),
                    brand_id=brand_id
                )
                self.db.add(model)
                self.db.flush()
                logger.info(f"Created new model: {model_name} (Brand ID: {brand_id})")
                
            return model
            
        except Exception as e:
            logger.error(f"Error getting/creating model {model_name}: {e}")
            self.db.rollback()
            return None

# Singleton instance
data_service = DataService()

def get_data_service() -> DataService:
    """Get a DataService instance with a new database session.
    
    Returns:
        DataService: A new DataService instance
    """
    return DataService()
