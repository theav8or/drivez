# Car Listing Aggregator

A real-time car listing aggregator that scrapes and normalizes car listings from multiple sources.

## Features

- Real-time car listing aggregation (every 10-15 minutes)
- Data normalization and standardization
- REST API with FastAPI
- Real-time updates via WebSocket
- Admin dashboard for monitoring
- User authentication and alerts

## Tech Stack

- Backend: Python + FastAPI
- Database: PostgreSQL
- Caching/Queues: Redis
- Scraping: Playwright
- Background Jobs: Celery
- Monitoring: Sentry

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Initialize database:
```bash
alembic upgrade head
```

5. Run the application:
```bash
uvicorn app.main:app --reload
```

## Scraper

To run the scraper for an extended period (e.g., 8 hours):

### Basic Usage (8-hour run)
```bash
timeout 8h uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Run in Background
To run the scraper in the background and keep logs:
```bash
nohup timeout 8h uvicorn app.main:app --host 0.0.0.0 --port 8000 > scraper.log 2>&1 &
```

### Monitoring and Control
- Check if scraper is running:
  ```bash
  ps aux | grep uvicorn
  ```

- View logs:
  ```bash
  tail -f scraper.log
  ```

- Stop the scraper:
  ```bash
  pkill -f "uvicorn app.main:app"
  ```

## Project Structure

```
.
├── app/                    # Backend application
│   ├── api/               # API routes and endpoints
│   ├── config/            # Configuration files
│   ├── core/              # Core application logic and settings
│   ├── db/                # Database models and session management
│   ├── exceptions/        # Custom exception handlers
│   ├── schemas/           # Pydantic models and validation schemas
│   ├── scrapers/          # Web scraping logic and utilities
│   ├── services/          # Business logic and service layer
│   └── utils/             # Helper functions and utilities
├── frontend/              # Frontend React application
│   ├── public/           # Static assets
│   └── src/              # React source code
│       ├── api/          # API client and services
│       ├── components/   # Reusable UI components
│       ├── features/     # Feature-based modules
│       ├── store/        # Redux store and slices
│       └── types/        # TypeScript type definitions
├── alembic/              # Database migrations
│   ├── versions/        # Migration files
│   └── env.py           # Migration environment
└── tests/                # Backend test files
```
