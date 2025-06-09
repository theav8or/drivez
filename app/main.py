from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import engine
from app.db.models.car import Base

# Import the correct router
from app.api.api_v1.api_new import api_router

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

# Include API v1 router (prefix is already set in the router)
from app.api.api_v1 import api_router as api_v1_router
app.include_router(api_v1_router)

@app.on_event("startup")
async def startup_event():
    """Initialize services when the application starts."""
    # Ensure database tables are created
    Base.metadata.create_all(bind=engine)

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# Debug endpoint to list all routes
@app.get("/api/debug/routes")
async def list_routes():
    """List all registered routes."""
    routes = []
    for route in app.routes:
        if hasattr(route, "methods"):
            routes.append({
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods)
            })
    
    # Debug: Print all routes to console
    print("\n=== Registered Routes ===")
    for route in routes:
        print(f"{route['path']} - {route['methods']}")
    print("======================\n")
    
    return {"routes": routes}
