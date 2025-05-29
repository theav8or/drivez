from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_v1.api import router as api_router
from app.db.session import engine
from app.db.models.car import Base

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Car Listing Aggregator API",
    description="API for aggregating and normalizing car listings",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize services when the application starts."""
    # Ensure database tables are created
    Base.metadata.create_all(bind=engine)

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
