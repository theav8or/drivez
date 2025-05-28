from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
from enum import Enum as PyEnum
from typing import Optional

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
    __tablename__ = "car_listings"

    id = Column(Integer, primary_key=True, index=True)
    yad2_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    year = Column(Integer, nullable=False)
    mileage = Column(Integer, nullable=True)
    fuel_type = Column(String, nullable=True)
    transmission = Column(String, nullable=True)
    body_type = Column(String, nullable=True)
    color = Column(String, nullable=True)
    status = Column(Enum(CarStatus), default=CarStatus.ACTIVE)
    
    brand_id = Column(Integer, ForeignKey("car_brands.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("car_models.id"), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    
    brand = relationship("CarBrand", back_populates="listings")
    model = relationship("CarModel", back_populates="listings")
