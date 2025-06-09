#!/usr/bin/env python3
"""Test database connection and basic operations."""
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('db_test.log')
    ]
)
logger = logging.getLogger(__name__)

def test_database_connection():
    """Test database connection and basic operations."""
    from app.db import SessionLocal, engine
    from app.db.models.car import CarBrand, CarModel
    from sqlalchemy import text
    
    logger.info("Testing database connection...")
    
    # Test raw connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"Database version: {version}")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return False
    
    # Test ORM
    db = SessionLocal()
    try:
        # Test brand count
        brand_count = db.query(CarBrand).count()
        logger.info(f"Found {brand_count} car brands in the database")
        
        # Test model count
        model_count = db.query(CarModel).count()
        logger.info(f"Found {model_count} car models in the database")
        
        # List first 5 brands
        brands = db.query(CarBrand).limit(5).all()
        logger.info("Sample brands:")
        for brand in brands:
            logger.info(f"- {brand.name} (ID: {brand.id})")
        
        return True
        
    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Starting database connection test...")
    success = test_database_connection()
    if success:
        logger.info("Database connection test completed successfully")
    else:
        logger.error("Database connection test failed")
        sys.exit(1)
