from fastapi import APIRouter
from .api_new import api_router

# This is the main router that will be imported by main.py
# All API routes from api_new.py are included via the api_router

# You can also include other routers here if needed
# from .endpoints import car, scraper
# router.include_router(car.router, prefix="/cars", tags=["cars"])
# router.include_router(scraper.router, prefix="/scraper", tags=["scraper"])

# Export the router for main.py to import
__all__ = ["api_router"]
