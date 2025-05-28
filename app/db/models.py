from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class CarBrand(Base):
    __tablename__ = "car_brands"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    normalized_name = Column(String, index=True)
    
    models = relationship("CarModel", back_populates="brand")

class CarModel(Base):
    __tablename__ = "car_models"
    
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("car_brands.id"))
    name = Column(String, index=True)
    normalized_name = Column(String, index=True)
    
    brand = relationship("CarBrand", back_populates="models")
    listings = relationship("CarListing", back_populates="model")

class CarListing(Base):
    __tablename__ = "car_listings"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("car_models.id"))
    source = Column(String, index=True)  # yad2, facebook, etc.
    source_id = Column(String, index=True)  # Original ID from source
    title = Column(String)
    price = Column(Float)
    mileage = Column(Integer)
    year = Column(Integer)
    location = Column(String)
    description = Column(Text)
    url = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    model = relationship("CarModel", back_populates="listings")

class CarListingHistory(Base):
    __tablename__ = "car_listing_history"
    
    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("car_listings.id"))
    price = Column(Float)
    mileage = Column(Integer)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    listing = relationship("CarListing", back_populates="history")
