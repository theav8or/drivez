from fastapi import APIRouter, BackgroundTasks, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import asyncio
import logging
import uuid
from datetime import datetime

from app.scrapers.yad2_updated import Yad2Scraper
from app.db.session import SessionLocal
from app.db.models.car import CarListing as CarListingModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory store for active scraping tasks
active_tasks: Dict[str, asyncio.Task] = {}

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ScraperTask:
    """Class to manage scraper task state."""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.status = "pending"
        self.start_time = datetime.utcnow()
        self.end_time: Optional[datetime] = None
        self.total_listings = 0
        self.new_listings = 0
        self.updated_listings = 0
        self.errors: List[str] = []
        self.is_complete = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for API response."""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_listings": self.total_listings,
            "new_listings": self.new_listings,
            "updated_listings": self.updated_listings,
            "error_count": len(self.errors),
            "is_complete": self.is_complete
        }

async def run_scraper_and_save(task_id: str, db: Session, task_state: ScraperTask):
    """Run the Yad2 scraper and save results to database."""
    try:
        task_state.status = "running"
        scraper = Yad2Scraper()
        logger.info(f"Starting Yad2 scraping task {task_id}")
        
        # Run the scraper
        listings = await scraper.scrape_listings()
        task_state.total_listings = len(listings)
        logger.info(f"Found {len(listings)} listings")
        
        # Save to database
        task_state.status = "saving"
        await scraper.normalize_and_store(listings)
        
        # Get counts from the database
        stats = db.query(
            db.func.count(CarListingModel.id).label('total'),
            db.func.sum(db.case((CarListingModel.created_at >= task_state.start_time, 1), else_=0)).label('new'),
            db.func.sum(db.case((CarListingModel.updated_at >= task_state.start_time, 1), else_=0)).label('updated')
        ).filter(
            CarListingModel.source == 'yad2',
            or_(
                CarListingModel.created_at >= task_state.start_time,
                CarListingModel.updated_at >= task_state.start_time
            )
        ).first()
        
        if stats:
            task_state.new_listings = stats.new or 0
            task_state.updated_listings = (stats.updated or 0) - (stats.new or 0)
        
        task_state.status = "completed"
        logger.info(f"Successfully processed {len(listings)} listings")
        
    except Exception as e:
        error_msg = f"Error in scraping task {task_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        task_state.errors.append(error_msg)
        task_state.status = "failed"
    finally:
        task_state.end_time = datetime.utcnow()
        task_state.is_complete = True
        # Clean up task after a delay to allow status checks
        await asyncio.sleep(300)  # Keep task info for 5 minutes after completion
        if task_id in active_tasks:
            del active_tasks[task_id]

@router.post("/yad2", status_code=status.HTTP_202_ACCEPTED)
async def scrape_yad2(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Trigger a Yad2 scraping job.
    
    Returns:
        Task ID and status URL
    """
    task_id = str(uuid.uuid4())
    task_state = ScraperTask(task_id)
    
    # Create and store the task
    task = asyncio.create_task(run_scraper_and_save(task_id, db, task_state))
    active_tasks[task_id] = task
    
    # Return task information
    return {
        "task_id": task_id,
        "status": "started",
        "message": "Scraping job started",
        "links": {
            "status": f"/api/v1/scrape/status/{task_id}",
            "tasks": "/api/v1/scrape/tasks"
        }
    }

@router.get("/status/{task_id}")
async def get_scrape_status(task_id: str):
    """
    Get the status of a scraping task.
    
    Args:
        task_id: The ID of the task to check
        
    Returns:
        Current status of the task
    """
    task = active_tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found or already completed"
        )
    
    # Check if the task has a task_state attribute (our ScraperTask instance)
    task_state = None
    for attr_name in ['_task_state', 'task_state']:
        if hasattr(task, attr_name):
            task_state = getattr(task, attr_name)
            if isinstance(task_state, ScraperTask):
                break
    
    if not task_state:
        return {
            "task_id": task_id,
            "status": "unknown",
            "message": "Task state not available"
        }
    
    return task_state.to_dict()

@router.get("/tasks")
async def list_active_tasks():
    """
    List all active scraping tasks.
    
    Returns:
        List of active tasks with their status
    """
    tasks = []
    for task_id, task in active_tasks.items():
        task_state = None
        for attr_name in ['_task_state', 'task_state']:
            if hasattr(task, attr_name):
                task_state = getattr(task, attr_name)
                if isinstance(task_state, ScraperTask):
                    break
        
        if task_state:
            tasks.append(task_state.to_dict())
        else:
            tasks.append({
                "task_id": task_id,
                "status": "running",
                "message": "No detailed status available"
            })
    
    return {
        "count": len(tasks),
        "tasks": tasks
    }
