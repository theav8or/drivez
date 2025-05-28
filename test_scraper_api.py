import asyncio
import httpx
import uvicorn
from fastapi import FastAPI
from app.main import app
from app.api.api_v1.api import api_router

# Create a test client
client = httpx.AsyncClient(app=app, base_url="http://test")

async def test_scraper():
    # Test starting a scraping job
    print("Starting scraping job...")
    response = await client.post("/api/v1/scrape/yad2")
    assert response.status_code == 202
    task_data = response.json()
    print(f"Started task: {task_data}")
    
    # Check task status
    task_id = task_data["task_id"]
    print(f"\nChecking task status...")
    response = await client.get(f"/api/v1/scrape/status/{task_id}")
    print(f"Task status: {response.json()}")
    
    # List active tasks
    print("\nActive tasks:")
    response = await client.get("/api/v1/scrape/active")
    print(response.json())
    
    # Wait for task to complete (for demo purposes)
    print("\nWaiting for task to complete...")
    import time
    for _ in range(5):  # Check status every 2 seconds for 10 seconds
        response = await client.get(f"/api/v1/scrape/status/{task_id}")
        status = response.json()
        print(f"Current status: {status}")
        if status.get("status") == "completed":
            break
        await asyncio.sleep(2)
    
    # Check if we got any listings
    print("\nFetching listings...")
    response = await client.get("/api/v1/listings")
    listings = response.json()
    print(f"Found {len(listings)} listings")
    if listings:
        print(f"First listing: {listings[0]}")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_scraper())
