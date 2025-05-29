from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CarBrandBase(BaseModel):
    name: str
    normalized_name: str

class CarBrandCreate(CarBrandBase):
    pass

class CarBrand(CarBrandBase):
    id: int

    class Config:
        from_attributes = True

class CarModelBase(BaseModel):
    name: str
    normalized_name: str
    brand_id: int

class CarModelCreate(CarModelBase):
    pass

class CarModel(CarModelBase):
    id: int

    class Config:
        from_attributes = True

class CarListingBase(BaseModel):
    yad2_id: str
    title: str
    description: Optional[str] = None
    price: float
    year: int
    mileage: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    body_type: Optional[str] = None
    color: Optional[str] = None
    image_url: Optional[str] = None  # URL to the main car image
    status: str = "active"
    brand_id: int
    model_id: int
    last_scraped_at: Optional[datetime] = None

class CarListingCreate(CarListingBase):
    pass

class CarListing(CarListingBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    brand: CarBrand
    model: CarModel

    class Config:
        from_attributes = True
        
        @classmethod
        def model_validate(cls, obj, *, strict=None, from_attributes=None, context=None):
            # Ensure updated_at is set to created_at if not provided
            if hasattr(obj, 'created_at') and (not hasattr(obj, 'updated_at') or obj.updated_at is None):
                obj.updated_at = obj.created_at
            return super().model_validate(obj, strict=strict, from_attributes=from_attributes, context=context)
