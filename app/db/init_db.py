from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Any
import logging

from app.core.config import settings
from app.db.models.car import Base, CarBrand, CarModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_session():
    """Create a new database session."""
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def init_db():
    """Initialize the database by creating all tables and populating initial data."""
    try:
        engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
        
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        # Create a new session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Add initial data if tables are empty
            _populate_initial_data(db)
            db.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            db.rollback()
            logger.error(f"Error populating initial data: {e}")
            raise
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def _populate_initial_data(db):
    """Populate initial data in the database."""
    # Common car brands and their models
    brands_and_models = {
        'Toyota': ['Corolla', 'Camry', 'RAV4', 'Prius', 'Hilux'],
        'Honda': ['Civic', 'Accord', 'CR-V', 'HR-V', 'Jazz'],
        'Mazda': ['3', '6', 'CX-5', 'CX-30', 'MX-5'],
        'Hyundai': ['i30', 'Tucson', 'Kona', 'i20', 'i10'],
        'Kia': ['Sportage', 'Picanto', 'Rio', 'Ceed', 'Niro']
    }
    
    # Add brands and models if they don't exist
    for brand_name, models in brands_and_models.items():
        # Check if brand exists
        stmt = select(CarBrand).where(CarBrand.name == brand_name)
        brand = db.execute(stmt).scalars().first()
        
        if not brand:
            brand = CarBrand(
                name=brand_name,
                normalized_name=brand_name.lower()
            )
            db.add(brand)
            db.flush()  # Flush to get the brand ID
            logger.info(f"Added brand: {brand_name}")
        
        # Add models for the brand
        for model_name in models:
            stmt = select(CarModel).where(
                CarModel.brand_id == brand.id,
                CarModel.name == model_name
            )
            model = db.execute(stmt).scalars().first()
            
            if not model:
                model = CarModel(
                    name=model_name,
                    normalized_name=model_name.lower(),
                    brand_id=brand.id
                )
                db.add(model)
                logger.info(f"  - Added model: {brand_name} {model_name}")

if __name__ == "__main__":
    init_db()
