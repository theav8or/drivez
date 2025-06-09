"""
Scraper API endpoints for the v2 API.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.scrapers.yad2_updated import Yad2Scraper
from app.core.config import settings

# Create a router with a prefix that will be used when including it in the main router
router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory store for active scraping tasks
active_tasks: Dict[str, asyncio.Task] = {}

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def run_scraper_task(task_id: str, max_pages: int, db: Session, headless: bool = False):
    """Run the Yad2 scraper and save results to database.
    
    Args:
        task_id: Unique ID for the task
        max_pages: Maximum number of pages to scrape
        db: Database session
        headless: Whether to run the browser in headless mode (default: False)
    """
    scraper = None
    try:
        # Create scraper instance with database session
        scraper = Yad2Scraper(
            headless=headless,  # Use the headless parameter
            slow_mo=100,
            max_retries=3,
            db=db
        )
        
        # Use async context manager
        async with scraper as scraper_ctx:
            logger.info(f"Starting Yad2 scraping task {task_id}")
            # Call the scrape method with search_params including max_pages
            search_params = {'max_pages': max_pages}
            result = await scraper_ctx.scrape(search_params=search_params)
            logger.info(f"Completed Yad2 scraping task {task_id}")
            return result
    except Exception as e:
        logger.error(f"Error in scraping task {task_id}: {str(e)}", exc_info=True)
        raise
    finally:
        # Ensure cleanup happens even if there's an error
        if scraper:
            await scraper._cleanup()
        # Clean up task from active tasks
        if task_id in active_tasks:
            del active_tasks[task_id]

@router.post("/scrape/yad2", status_code=status.HTTP_202_ACCEPTED)
async def scrape_yad2(
    max_pages: int = 5,
    headless: bool = False,  # Add headless parameter defaulting to False
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Trigger a Yad2 scraping job.
    
    Args:
        max_pages: Maximum number of pages to scrape (default: 5)
        
    Returns:
        Task ID and status URL
    """
    # Check if a task is already running
    if active_tasks:
        task_id = next(iter(active_tasks))
        return {
            "status": "already_running",
            "task_id": task_id,
            "details": {
                "message": "A scraping task is already running",
                "status_url": f"/api/v1/scrape/status/{task_id}"
            }
        }
    
    task_id = str(uuid.uuid4())
    
    # Create and store the task
    task = asyncio.create_task(run_scraper_task(task_id, max_pages, db, headless))
    active_tasks[task_id] = task
    
    # Add callback to clean up when task is done
    task.add_done_callback(lambda _: active_tasks.pop(task_id, None))
    
    return {
        "task_id": task_id,
        "status": "started",
        "details": {
            "started_at": datetime.utcnow().isoformat(),
            "scraper": "yad2",
            "max_pages": max_pages,
            "status_url": f"/api/v1/scrape/status/{task_id}"
        }
    }

@router.get("/scrape/status/{task_id}")
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
        return {
            "task_id": task_id,
            "status": "not_found",
            "message": "Task not found or already completed"
        }
    
    if task.done():
        try:
            result = task.result()
            return {
                "task_id": task_id,
                "status": "completed",
                "result": result
            }
        except Exception as e:
            return {
                "task_id": task_id,
                "status": "error",
                "error": str(e)
            }
    
    return {
        "task_id": task_id,
        "status": "running"
    }

@router.get("/scrape/tasks")
async def list_active_tasks():
    """
    List all active scraping tasks.
    
    Returns:
        List of active task IDs and their statuses
    """
    tasks = []
    for task_id, task in active_tasks.items():
        status = "running"
        if task.done():
            status = "completed" if not task.exception() else "error"
        tasks.append({
            "task_id": task_id,
            "status": status,
            "done": task.done(),
            "cancelled": task.cancelled()
        })
    
    return {
        "count": len(tasks),
        "tasks": tasks
    }
