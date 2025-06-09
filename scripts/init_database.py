#!/usr/bin/env python3
"""
Initialize the database with required tables and initial data.
"""
import sys
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize the database with required tables and data."""
    from app.db.base_class import Base
    from app.db.session import engine, SessionLocal
    from app.services.data_service import DataService
    
    logger.info("Starting database initialization...")
    
    try:
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        # Initialize data service
        db = SessionLocal()
        try:
            data_service = DataService(db)
            data_service.ensure_initial_data()
            logger.info("Database initialization completed successfully")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()
