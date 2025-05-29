#!/usr/bin/env python3
"""
Script to add test car listings to the database.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models.car import CarStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import database models after logging is configured
from app.db.session import SessionLocal
from app.db.models.car import CarBrand, CarModel, CarListing

def create_test_data(db: Session):
    """Create test data in the database."""
    try:
        # Create test brands with Hebrew names
        brand1 = CarBrand(name="טויוטה", normalized_name="toyota")
        brand2 = CarBrand(name="הונדה", normalized_name="honda")
        brand3 = CarBrand(name="ב.מ.וו", normalized_name="bmw")
        
        db.add_all([brand1, brand2, brand3])
        db.flush()  # Flush to get the brand IDs
        
        # Create test models with Hebrew names
        models = [
            CarModel(name="קורולה", normalized_name="corolla", brand_id=brand1.id),
            CarModel(name="קאמרי", normalized_name="camry", brand_id=brand1.id),
            CarModel(name="סיוויק", normalized_name="civic", brand_id=brand2.id),
            CarModel(name="אקורד", normalized_name="accord", brand_id=brand2.id),
            CarModel(name="סדרה 3", normalized_name="3_series", brand_id=brand3.id),
            CarModel(name="סדרה 5", normalized_name="5_series", brand_id=brand3.id)
        ]
        
        db.add_all(models)
        db.flush()
        
        # Create test listings with Hebrew text
        listings = [
            CarListing(
                yad2_id="test_1",
                title="טויוטה קורולה 2019",
                description="מצב מצוין, בעלים אחד, היסטוריית תחזוקה מלאה. ניתן לתאם נסיעת מבחן.",
                price=18000.0,
                year=2019,
                mileage=45000,
                fuel_type="בנזין",
                transmission="אוטומטית",
                body_type="סדאן",
                color="לבן",
                brand_id=brand1.id,
                model_id=models[0].id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                last_scraped_at=datetime.utcnow(),
                status=CarStatus.ACTIVE
            ),
            CarListing(
                yad2_id="test_2",
                title="הונדה סיוויק 2020",
                description="קילומטראז' נמוך, מצב מצוין, כולל כל האפשרויות. רכב ללא עישון.",
                price=20000.0,
                year=2020,
                mileage=30000,
                fuel_type="היברידי",
                transmission="אוטומטית",
                body_type="האצ'בק",
                color="אדום",
                brand_id=brand2.id,
                model_id=models[2].id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                last_scraped_at=datetime.utcnow(),
                status=CarStatus.ACTIVE
            ),
            CarListing(
                yad2_id="test_3",
                title="ב.מ.וו סדרה 3 2018",
                description="חבילת יוקרה, קו ספורט, מתוחזק היטב. היסטוריית שירות מלאה זמינה.",
                price=25000.0,
                year=2018,
                mileage=35000,
                fuel_type="דיזל",
                transmission="אוטומטית",
                body_type="סדאן",
                color="שחור",
                brand_id=brand3.id,
                model_id=models[4].id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                last_scraped_at=datetime.utcnow(),
                status=CarStatus.ACTIVE
            )
        ]
        
        db.add_all(listings)
        db.commit()
        logger.info("Successfully added test data to the database")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating test data: {str(e)}")
        raise

def main():
    """Main function to add test data to the database."""
    logger.info("Starting to add test data to the database...")
    
    db = SessionLocal()
    try:
        create_test_data(db)
    except Exception as e:
        logger.error(f"Failed to add test data: {str(e)}")
    finally:
        db.close()
        logger.info("Test data addition completed")

if __name__ == "__main__":
    main()
