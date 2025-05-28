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

## Project Structure

```
.
├── app/
│   ├── api/           # API routes
│   ├── core/          # Core application logic
│   ├── db/           # Database models and migrations
│   ├── scrapers/     # Web scraping logic
│   ├── services/     # Business logic services
│   └── utils/        # Utility functions
├── tests/            # Test files
└── alembic/          # Database migrations
```
