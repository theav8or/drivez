from sqlalchemy import create_engine
from app.core.config import settings
from app.db.models.car import Base

def init_db():
    """Initialize the database by creating all tables."""
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")

if __name__ == "__main__":
    init_db()
