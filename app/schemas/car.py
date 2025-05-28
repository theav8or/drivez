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
    source: str
    source_id: str
    url: str
    title: str
    price: float
    mileage: Optional[int] = None
    year: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class CarListingCreate(CarListingBase):
    pass

class CarListing(CarListingBase):
    id: int

    class Config:
        from_attributes = True
