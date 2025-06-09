from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON, Text,
    Boolean, BigInteger, Numeric, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func, expression
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from app.db.base_class import Base
from app.core.config import settings

class CarStatus(PyEnum):
    ACTIVE = "active"
    SOLD = "sold"
    ARCHIVED = "archived"

class CarBrand(Base):
    __tablename__ = "car_brands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    normalized_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    models = relationship("CarModel", back_populates="brand")
    listings = relationship("CarListing", back_populates="brand")

class CarModel(Base):
    __tablename__ = "car_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=False)
    brand_id = Column(Integer, ForeignKey("car_brands.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    brand = relationship("CarBrand", back_populates="models")
    listings = relationship("CarListing", back_populates="model")

class CarListing(Base):
    """Represents a car listing in the database."""
    __tablename__ = "car_listings"
    __table_args__ = (
        Index('idx_listing_yad2_id', 'yad2_id', unique=True),
        Index('idx_listing_brand_model', 'brand_id', 'model_id'),
        Index('idx_listing_price', 'price'),
        Index('idx_listing_year', 'year'),
        Index('idx_listing_mileage', 'mileage'),
        Index('idx_listing_created_at', 'created_at'),
        Index('idx_listing_updated_at', 'updated_at'),
        Index('idx_listing_status', 'status'),
        Index('idx_listing_location', 'city', 'neighborhood'),
        {
            'postgresql_partition_by': 'RANGE (created_at)',
            'postgresql_using': 'brin',
            'postgresql_with': {'autosummarize': 'on'}
        } if settings.ENVIRONMENT == 'production' else {}
    )

    id = Column(Integer, primary_key=True, index=True)
    yad2_id = Column(String(100), unique=True, index=True, nullable=False, comment="Unique identifier from Yad2")
    
    # Basic Information
    title = Column(String(200), nullable=False, comment="Listing title")
    description = Column(Text, nullable=True, comment="Detailed description")
    
    # Pricing
    price = Column(Numeric(12, 2), nullable=False, comment="Current price in ILS")
    original_price = Column(Numeric(12, 2), nullable=True, comment="Original price if discounted")
    is_price_negotiable = Column(Boolean, default=False, nullable=False, comment="If price is negotiable")
    
    # Vehicle Details
    year = Column(Integer, nullable=True, comment="Manufacturing year")
    mileage = Column(Integer, nullable=True, comment="Mileage in kilometers")
    engine_volume = Column(Integer, nullable=True, comment="Engine volume in CC")
    fuel_type = Column(String(50), nullable=True, comment="Fuel type (e.g., Gasoline, Diesel, Hybrid)")
    transmission = Column(String(50), nullable=True, comment="Transmission type (Automatic, Manual)")
    body_type = Column(String(100), nullable=True, comment="Body type (Sedan, SUV, Hatchback, etc.)")
    color = Column(String(50), nullable=True, comment="Exterior color")
    hand = Column(Integer, nullable=True, comment="Number of previous owners")
    test_until = Column(DateTime, nullable=True, comment="Next test date (MOT)")
    
    # Location
    city = Column(String(100), nullable=True, comment="City where the car is located")
    neighborhood = Column(String(100), nullable=True, comment="Neighborhood or district")
    
    # Technical Details
    horsepower = Column(Integer, nullable=True, comment="Engine power in HP")
    doors = Column(Integer, nullable=True, comment="Number of doors")
    seats = Column(Integer, nullable=True, comment="Number of seats")
    
    # Status
    status = Column(Enum(CarStatus), default=CarStatus.ACTIVE, nullable=False, comment="Current status of the listing")
    is_imported = Column(Boolean, default=False, nullable=False, comment="If the car is imported")
    is_accident_free = Column(Boolean, default=True, nullable=False, comment="If the car has no accident history")
    
    # Media
    images = Column(ARRAY(String), default=[], nullable=True, comment="Array of image URLs")
    thumbnail_url = Column(String(500), nullable=True, comment="URL of the main thumbnail image")
    
    # Metadata
    source_url = Column(String(500), nullable=True, comment="Original listing URL")
    source_created_at = Column(DateTime, nullable=True, comment="When the listing was created at the source")
    source_updated_at = Column(DateTime, nullable=True, comment="When the listing was last updated at the source")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    brand_id = Column(Integer, ForeignKey("car_brands.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("car_models.id"), nullable=False)
    
    brand = relationship("CarBrand", back_populates="listings")
    model = relationship("CarModel", back_populates="listings")
    history = relationship("CarListingHistory", back_populates="listing", cascade="all, delete-orphan")
    
    # JSON data for flexible schema
    metadata_ = Column('metadata', JSON, default=dict, nullable=True, comment="Additional metadata in JSON format")
    engine_cc = Column(String(20), nullable=True)
    engine_type = Column(String(50), nullable=True)
    condition = Column(String(50), nullable=True)
    ownership = Column(String(50), nullable=True)
    origin = Column(String(50), nullable=True)
    test_date = Column(String(20), nullable=True)
    hand = Column(String(10), nullable=True)
    location = Column(String(200), nullable=True)
    url = Column(String(500), nullable=True)
    source = Column(String(50), default='yad2')
    images = Column(JSON, default=list)  # Store image URLs as JSON array
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    status = Column(Enum(CarStatus), default=CarStatus.ACTIVE)
    
    # Foreign keys
    brand_id = Column(Integer, ForeignKey("car_brands.id"), nullable=True)
    model_id = Column(Integer, ForeignKey("car_models.id"), nullable=True)

    # Relationships
    brand = relationship("CarBrand", back_populates="listings")
    model = relationship("CarModel", back_populates="listings")
    history = relationship("CarListingHistory", back_populates="listing", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CarListing(id={self.id}, title='{self.title}', price={self.price})>"
    
    def to_dict(self):
        """Convert the model instance to a dictionary."""
        return {
            'id': self.id,
            'yad2_id': self.yad2_id,
            'title': self.title,
            'price': self.price,
            'year': self.year,
            'mileage': self.mileage,
            'fuel_type': self.fuel_type,
            'transmission': self.transmission,
            'body_type': self.body_type,
            'color': self.color,
            'location': self.location,
            'url': self.url,
            'source': self.source,
            'images': self.images,
            'status': self.status.value if self.status else None,
            'brand': self.brand.name if self.brand else None,
            'model': self.model.name if self.model else None,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class CarListingHistory(Base):
    """Tracks changes to car listings over time."""
    __tablename__ = "car_listing_history"
    __table_args__ = (
        Index('idx_history_listing_created', 'listing_id', 'created_at'),
        Index('idx_history_created_at', 'created_at'),
        {
            'postgresql_partition_by': 'RANGE (created_at)',
            'postgresql_using': 'brin',
            'postgresql_with': {'autosummarize': 'on'}
        } if settings.ENVIRONMENT == 'production' else {}
    )

    id = Column(BigInteger, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("car_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Tracked Fields
    price = Column(Numeric(12, 2), nullable=True, comment="Price at this point in time")
    mileage = Column(Integer, nullable=True, comment="Mileage at this point in time")
    status = Column(Enum(CarStatus), nullable=True, comment="Status at this point in time")
    
    # Calculated Fields
    price_change = Column(Numeric(12, 2), nullable=True, comment="Price change from previous record")
    price_change_percent = Column(Float, nullable=True, comment="Percentage price change from previous record")
    days_on_market = Column(Integer, nullable=True, comment="Days on market at this point")
    
    # Metadata
    source = Column(String(50), nullable=True, comment="Source of this update (scraper, manual, etc.)")
    notes = Column(Text, nullable=True, comment="Additional notes about this change")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    listing = relationship("CarListing", back_populates="history")
    
    # JSON data for flexible schema
    metadata_ = Column('metadata', JSON, default=dict, nullable=True, comment="Additional metadata in JSON format")
    
    def __repr__(self) -> str:
        return f"<CarListingHistory {self.id} - Listing {self.listing_id}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the history record to a dictionary."""
        return {
            'id': self.id,
            'listing_id': self.listing_id,
            'price': self.price,
            'mileage': self.mileage,
            'status': self.status.value if self.status else None,
            'price_change': self.price_change,
            'days_on_market': self.days_on_market,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
