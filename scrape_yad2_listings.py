#!/usr/bin/env python3
"""
Script to scrape car listings directly from Yad2 website.
"""
import os
import sys
import json
import time
import logging
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scrape_yad2.log')
    ]
)
logger = logging.getLogger(__name__)

# Base URL for Yad2 cars search
BASE_URL = 'https://www.yad2.co.il/vehicles/cars'

# Headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,he;q=0.8',
    'Referer': 'https://www.yad2.co.il/',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def get_next_data(session: requests.Session, url: str) -> Optional[Dict]:
    """Extract the __NEXT_DATA__ from the page."""
    try:
        logger.info(f"Fetching page: {url}")
        response = session.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')
        
        if not script_tag:
            logger.error("No __NEXT_DATA__ script tag found")
            return None
            
        return json.loads(script_tag.string)
        
    except Exception as e:
        logger.error(f"Error getting page data: {e}")
        return None

def extract_listings(data: Dict) -> List[Dict]:
    """Extract listings from the Next.js data."""
    listings = []
    
    try:
        # The structure might vary, so we need to be defensive
        props = data.get('props', {})
        page_props = props.get('pageProps', {})
        dehydrated_state = page_props.get('dehydratedState', {})
        queries = dehydrated_state.get('queries', [])
        
        # Look for the feed data in the queries
        for query in queries:
            query_data = query.get('state', {}).get('data', {})
            
            # Check if this is the feed data
            if 'platinum' in query_data and 'private' in query_data:
                # Combine all listing types
                for listing_type in ['platinum', 'boost', 'solo', 'commercial', 'private']:
                    listings.extend(query_data.get(listing_type, []))
                break
                
        logger.info(f"Extracted {len(listings)} listings from page")
        
    except Exception as e:
        logger.error(f"Error extracting listings: {e}")
    
    return listings

def normalize_listing(listing: Dict) -> Dict:
    """Normalize listing data to a consistent format."""
    try:
        # Extract basic information
        title = listing.get('title', '')
        price = listing.get('price', 0)
        year = listing.get('year', '')
        km = listing.get('kilometers', 0)
        
        # Extract details from the additional_info dictionary
        additional_info = listing.get('additional_info', {})
        
        # Extract specific details
        fuel_type = additional_info.get('fuel_type', '')
        hand = additional_info.get('hand', '')
        test_date = additional_info.get('test_date', '')
        
        # Create the normalized listing
        normalized = {
            'id': listing.get('id', ''),
            'title': title,
            'price': price,
            'year': year,
            'km': km,
            'fuel_type': fuel_type,
            'hand': hand,
            'test_date': test_date,
            'link': f"https://www.yad2.co.il/item/{listing.get('id', '')}",
            'description': listing.get('description', ''),
            'location': listing.get('location', ''),
            'images': listing.get('images', []),
            'date': listing.get('date', '')
        }
        
        return normalized
        
    except Exception as e:
        logger.error(f"Error normalizing listing: {e}")
        return {}

def main():
    """Main function to scrape Yad2 car listings."""
    try:
        logger.info("Starting Yad2 car listings scraper...")
        
        # Set up session
        session = requests.Session()
        
        # Get the first page
        next_data = get_next_data(session, BASE_URL)
        
        if not next_data:
            logger.error("Failed to get initial page data")
            return
            
        # Extract listings
        raw_listings = extract_listings(next_data)
        
        if not raw_listings:
            logger.warning("No listings found on the first page")
            return
            
        # Normalize and process listings
        listings = []
        for i, listing in enumerate(raw_listings[:10], 1):  # Limit to 10 listings
            logger.info(f"Processing listing {i}/{min(10, len(raw_listings))}")
            normalized = normalize_listing(listing)
            if normalized:
                listings.append(normalized)
            
            # Add a small delay between requests
            time.sleep(1)
        
        # Print the results
        print("\n" + "="*100)
        print(f"FOUND {len(listings)} CAR LISTINGS:")
        print("="*100)
        
        for i, listing in enumerate(listings, 1):
            print(f"\n{'*'*50} LISTING {i} {'*'*50}")
            print(f"TITLE: {listing.get('title', 'N/A')}")
            print(f"PRICE: ₪{listing.get('price', 'N/A')}")
            print(f"YEAR: {listing.get('year', 'N/A')}")
            print(f"KM: {listing.get('km', 'N/A')}")
            print(f"FUEL TYPE: {listing.get('fuel_type', 'N/A')}")
            print(f"HAND: {listing.get('hand', 'N/A')}")
            print(f"TEST DATE: {listing.get('test_date', 'N/A')}")
            print(f"LOCATION: {listing.get('location', 'N/A')}")
            print(f"LINK: {listing.get('link', 'N/A')}")
            print("\nDESCRIPTION:")
            print(listing.get('description', 'No description'))
        
        print("\n" + "="*100)
        logger.info(f"Successfully scraped {len(listings)} car listings.")
        
        # Save results to JSON file
        with open('yad2_listings.json', 'w', encoding='utf-8') as f:
            json.dump(listings, f, ensure_ascii=False, indent=2)
        logger.info("Saved results to 'yad2_listings.json'")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()
