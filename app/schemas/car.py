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
    status: str = "active"
    brand_id: int
    model_id: int
    last_scraped_at: Optional[datetime] = None

class CarListingCreate(CarListingBase):
    pass

class CarListing(CarListingBase):
    id: int
    created_at: datetime
    updated_at: datetime
    brand: CarBrand
    model: CarModel

    class Config:
        from_attributes = True
