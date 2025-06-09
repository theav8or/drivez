# Yad2 Car Listings Scraper

This project provides a robust solution for scraping car listings from Yad2 and storing them in a database. The system is designed to be maintainable, scalable, and easy to use.

## Features

- **Database Integration**: Automatically stores scraped data in a SQL database
- **Rate Limiting**: Implements delays between requests to avoid detection
- **Error Handling**: Comprehensive error handling and retry mechanisms
- **Headless Browsing**: Uses Playwright for reliable web scraping
- **Data Normalization**: Cleans and normalizes scraped data
- **Command Line Interface**: Easy-to-use CLI for running scrapers

## Prerequisites

- Python 3.8+
- Playwright
- SQLAlchemy
- Other dependencies listed in `requirements.txt`

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

2. **Configure the database**:
   Update the database connection string in `.env`:
   ```
   DATABASE_URL=sqlite:///./car_listings.db
   ```

3. **Initialize the database**:
   ```bash
   python scripts/init_database.py
   ```

## Usage

### Run the Scraper

```bash
# Run with default settings (50 listings, headless mode)
python scripts/run_scraper.py

# Scrape a specific number of listings
python scripts/run_scraper.py --max-listings 100

# Run in non-headless mode (for debugging)
python scripts/run_scraper.py --no-headless
```

### Database Management

```bash
# Initialize the database (create tables and add initial data)
python scripts/init_database.py

# Clean up old listings (older than 30 days)
python scripts/cleanup_database.py

# Clean up listings older than 60 days
python scripts/cleanup_database.py --days 60
```

## Project Structure

```
.
├── app/
│   ├── db/                 # Database models and session management
│   ├── scrapers/           # Scraper implementations
│   ├── services/           # Business logic services
│   └── schemas/            # Pydantic models for data validation
├── scripts/
│   ├── init_database.py    # Initialize database schema and data
│   ├── run_scraper.py      # CLI for running the scraper
│   └── cleanup_database.py # Clean up old records
└── SCRAPER_README.md       # This file
```

## Error Handling

The system includes comprehensive error handling:
- Automatic retries for failed requests
- Rate limiting to avoid IP bans
- Detailed logging for debugging

## Maintenance

### Adding New Fields

1. Update the SQLAlchemy models in `app/db/models/car.py`
2. Create and run a new database migration:
   ```bash
   alembic revision --autogenerate -m "Add new field description"
   alembic upgrade head
   ```

### Updating Scraping Logic

1. Modify the relevant methods in `app/scrapers/yad2_enhanced.py`
2. Update the data processing in `app/services/data_service.py` if needed

## License

This project is licensed under the MIT License - see the LICENSE file for details.
