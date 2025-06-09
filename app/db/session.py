"""Database session management."""
import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session

from app.core.config import settings
from app.db.models.car import Base

logger = logging.getLogger(__name__)

def get_database_url() -> str:
    """Construct the database URL from settings."""
    return (
        f"postgresql://{settings.POSTGRES_USER}:"
        f"{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_SERVER}/"
        f"{settings.POSTGRES_DB}"
    )

# Create engine with connection pool settings
try:
    database_url = get_database_url()
    logger.info(f"Connecting to database: {database_url}")
    
    engine = create_engine(
        database_url,
        pool_pre_ping=True,  # Check connection health before using
        pool_size=5,         # Number of connections to keep open
        max_overflow=10,     # Max number of connections beyond pool_size
        pool_timeout=30,     # Seconds to wait for a connection from the pool
        pool_recycle=3600,   # Recycle connections after 1 hour
        echo=settings.DEBUG  # Echo SQL queries in debug mode
    )
    
    logger.info("Database engine created successfully")
    
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Prevent attribute access after commit
)

# Scoped session factory for web applications
SessionScoped = scoped_session(SessionLocal)

# Create tables if they don't exist (only for development)
# In production, use migrations instead
if settings.ENVIRONMENT == "development":
    try:
        logger.info("Creating database tables (development mode)")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Get a database session with automatic cleanup.
    
    Yields:
        Session: A SQLAlchemy database session
        
    Example:
        with get_db_session() as db:
            result = db.query(MyModel).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# Async generator for FastAPI dependency
async def get_db():
    """Dependency for FastAPI to get a database session.
    
    Yields:
        Session: A SQLAlchemy database session
        
    Example:
        @app.get("/items/")
        async def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# For backward compatibility
get_db_session = get_db
