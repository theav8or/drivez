

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory store for active scraping tasks
active_tasks: Dict[str, asyncio.Task] = {}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def run_scraper_and_save(task_id: str, db: Session):
    """Run the Yad2 scraper and save results to database."""
    try:
        scraper = Yad2Scraper()
        logger.info(f"Starting Yad2 scraping task {task_id}")
        
        # Run the scraper
        listings = await scraper.scrape_listings()
        logger.info(f"Found {len(listings)} listings")
        
        # Save to database
        count = 0
        for listing in listings:
            try:
                # Check if listing already exists
                existing = db.query(CarListingModel).filter(
                    CarListingModel.source == 'yad2',
                    CarListingModel.source_id == listing.get('source_id')
                ).first()
                
                if not existing:
                    # Create new listing
                    db_listing = CarListingModel(
                        source='yad2',
                        source_id=listing.get('source_id'),
                        url=listing.get('url'),
                        title=listing.get('title'),
                        price=listing.get('price'),
                        mileage=listing.get('mileage'),
                        year=listing.get('year'),
                        location=listing.get('location'),
                        description=listing.get('description'),
                        fuel_type=listing.get('fuel_type'),
                        transmission=listing.get('transmission'),
                        body_type=listing.get('body_type'),
                        color=listing.get('color'),
                        brand=listing.get('brand'),
                        model=listing.get('model'),
                        raw_data=listing
                    )
                    db.add(db_listing)
                    count += 1
                else:
                    # Update existing listing
                    existing.price = listing.get('price')
                    existing.mileage = listing.get('mileage')
                    existing.raw_data = listing
            except Exception as e:
                logger.error(f"Error saving listing: {str(e)}")
                continue
        
        db.commit()
        logger.info(f"Successfully saved {count} new listings to database")
        
    except Exception as e:
        logger.error(f"Error in scraping task {task_id}: {str(e)}", exc_info=True)
    finally:
        # Clean up task
        if task_id in active_tasks:
            del active_tasks[task_id]

@router.post("/scrape/yad2", status_code=status.HTTP_202_ACCEPTED)
async def scrape_yad2(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Trigger a Yad2 scraping job.
    
    Returns:
        Task ID and status URL
    """
    import uuid
    from datetime import datetime
    
    task_id = str(uuid.uuid4())
    
    # Create and store the task
    task = asyncio.create_task(run_scraper_and_save(task_id, db))
    active_tasks[task_id] = task
    
    return {
        "task_id": task_id,
        "status": "started",
        "details": {
            "started_at": datetime.utcnow().isoformat(),
            "scraper": "yad2",
            "status_url": f"/api/v1/scrape/status/{task_id}"
        }
    }

@router.get("/scrape/status/{task_id}")
async def get_scrape_status(task_id: str):
    """Get the status of a scraping task."""
    task = active_tasks.get(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found. It may have completed or never existed."
        )
    
    if task.done():
        if task.exception():
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(task.exception())
            }
        return {"task_id": task_id, "status": "completed"}
    
    return {"task_id": task_id, "status": "in_progress"}

@router.get("/scrape/active")
async def list_active_tasks():
    """List all active scraping tasks."""
    return {
        "active_tasks": [
            {"task_id": task_id, "status": "done" if task.done() else "in_progress"}
            for task_id, task in active_tasks.items()
        ]
    }
