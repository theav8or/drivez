#!/usr/bin/env python3
"""
Clean up old records from the database.
"""
import sys
import logging
import argparse
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

def cleanup_database(days_old: int = 30):
    """Clean up old records from the database.
    
    Args:
        days_old: Number of days after which a record is considered old
    """
    from app.db.session import SessionLocal
    from app.services.data_service import DataService
    
    logger.info(f"Starting database cleanup (removing records older than {days_old} days)...")
    
    try:
        db = SessionLocal()
        try:
            data_service = DataService(db)
            count = data_service.cleanup_old_listings(days_old)
            logger.info(f"Successfully removed {count} old records")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error during database cleanup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean up old database records.')
    parser.add_argument('--days', type=int, default=30,
                       help='Number of days after which a record is considered old (default: 30)')
    
    args = parser.parse_args()
    cleanup_database(args.days)
