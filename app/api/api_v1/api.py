from fastapi import APIRouter
from .api_new import router as api_router

# Create main router
router = APIRouter()

# Include the existing API router with /car prefix
router.include_router(api_router, prefix="/car", tags=["car"])

# Export the router for main.py to import
__all__ = ["router"]
