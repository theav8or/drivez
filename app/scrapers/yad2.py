
        """Return a random delay between requests to avoid being blocked."""
        return random.uniform(*self.delay_range)

    async def _navigate_to_page(self, page, url: str, retry_count: int = 0) -> bool:
        """Navigate to a URL with retry logic."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            # Wait for the page to be fully loaded
            await page.wait_for_load_state("networkidle")
            return True
        except PlaywrightTimeoutError:
            if retry_count < self.max_retries:
                logger.warning(f"Timeout loading {url}, retrying... (Attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(await self._get_random_delay() * 2)  # Longer delay on retry
                return await self._navigate_to_page(page, url, retry_count + 1)
            logger.error(f"Failed to load {url} after {self.max_retries} attempts")
            return False
        except Exception as e:
            logger.error(f"Error navigating to {url}: {str(e)}")
            return False

    async def scrape_listings(self) -> List[Dict]:
        """
        Scrape car listings from Yad2 with pagination support.
        
        Returns:
            List of scraped car listings
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-gpu'
                ]
            )
            context = await browser.new_context(
                user_agent=self.headers["User-Agent"],
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True
            )
            
            # Block unnecessary resources to speed up scraping
            await context.route('**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,eot}', lambda route: route.abort())
            
            page = await context.new_page()
            all_listings = []
            
            try:
                # Start from the first page
                current_page = 1
                next_page_url = self.search_url
                
                while next_page_url:
                    logger.info(f"Scraping page {current_page}: {next_page_url}")
                    
                    # Navigate to the page
                    success = await self._navigate_to_page(page, next_page_url)
                    if not success:
                        logger.error(f"Failed to navigate to page {current_page}")
                        break
                    
                    # Wait for listings to load
                    try:
                        await page.wait_for_selector(".feeditem:not(.feeditem-premium)", timeout=10000)
                    except PlaywrightTimeoutError:
                        logger.warning(f"No listings found on page {current_page}, stopping pagination")
                        break
                    
                    # Extract listings from current page
                    page_listings = await self._extract_page_listings(page)
                    logger.info(f"Found {len(page_listings)} listings on page {current_page}")
                    
                    # Add to all listings if not already processed
                    for listing in page_listings:
                        if listing.get('url') and listing['url'] not in self.processed_urls:
                            all_listings.append(listing)
                            self.processed_urls.add(listing['url'])
                    
                    # Find next page URL
                    next_page_url = await self._get_next_page_url(page, current_page)
                    current_page += 1
                    
                    # Add a small delay between page requests
                    if next_page_url:
                        delay = await self._get_random_delay()
                        logger.debug(f"Waiting {delay:.2f} seconds before next page...")
                        await asyncio.sleep(delay)
                
                return all_listings
            
            except Exception as e:
                logger.error(f"Error during scraping: {str(e)}", exc_info=True)
                return all_listings
            
            finally:
                await browser.close()
    
    async def _get_next_page_url(self, page, current_page: int) -> Optional[str]:
        """Find the URL for the next page of results, ensuring it's within the cars section."""
        try:
            # First, verify we're still in the cars section
            if not page.url.startswith(f"{self.base_url}/vehicles/cars"):
                logger.warning(f"Navigated outside of cars section: {page.url}")
                return None
                
            # Look for pagination buttons
            next_buttons = await page.query_selector_all('a[data-page]')
            
            for button in next_buttons:
                page_num = await button.get_attribute('data-page')
                if page_num and page_num.isdigit() and int(page_num) == current_page + 1:
                    href = await button.get_attribute('href')
                    if href and '/vehicles/cars' in href:
                        return urljoin(self.base_url, href)
            
            # Alternative method: Look for 'Next' button
            next_buttons = await page.query_selector_all('a:has-text("הבא"), a:has-text("Next")')
            if next_buttons:
                href = await next_buttons[0].get_attribute('href')
                if href and '/vehicles/cars' in href:
                    return urljoin(self.base_url, href)
            
            # If no next button found, try to construct the next page URL
            parsed_url = urlparse(page.url)
            
            # Ensure we're still in the cars section
            if not parsed_url.path.startswith('/vehicles/cars'):
                return None
            
            # Update the page parameter
            query_params = parse_qs(parsed_url.query)
            if 'page' in query_params:
                query_params['page'] = [str(int(query_params['page'][0]) + 1)]
            else:
                query_params['page'] = [str(current_page + 1)]
            
            # Rebuild the URL with updated page parameter
            new_query = '&'.join([f"{k}={v[0]}" for k, v in query_params.items()])
            next_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{new_query}"
            
            return next_url
            
        except Exception as e:
            logger.warning(f"Error finding next page URL: {str(e)}")
            return None
    
    async def _extract_page_listings(self, page) -> List[Dict]:
        """Extract all listings from the current page."""
        listings = []
        
        # Find all listing elements
        items = await page.query_selector_all(".feeditem:not(.feeditem-premium)")
        
        for item in items:
            try:
                listing = await self._extract_listing_data(item)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.error(f"Error extracting listing: {str(e)}")
                continue
        
        return listings

    async def _extract_listing_data(self, item) -> Optional[Dict]:
        """Extract data from a single listing element."""
        try:
            # Skip if not a valid item
            if not item or not hasattr(item, 'query_selector'):
                return None
                
            # Initialize listing data with default values
            listing_data = {
                'source': 'yad2',
                'source_id': '',
                'url': '',
                'title': '',
                'price': 0,
                'mileage': None,
                'year': None,
                'location': '',
                'description': '',
                'yad2_id': '',
                'fuel_type': '',
                'transmission': '',
                'body_type': '',
                'color': '',
                'status': 'active',
                'brand': '',
                'model': '',
                'last_scraped_at': datetime.utcnow().isoformat()
            }
            
            # Extract URL and ID
            link_elem = await item.query_selector('a[href*="/item/"]')
            if link_elem:
                href = await link_elem.get_attribute('href')
                if href:
                    listing_data['url'] = urljoin(self.base_url, href)
                    # Extract Yad2 ID from URL
                    match = re.search(r'/item/([a-f0-9]+)', href)
                    if match:
                        listing_data['source_id'] = match.group(1)
                        listing_data['yad2_id'] = match.group(1)
            
            # Extract title
            title_elem = await item.query_selector('.title')
            if title_elem:
                listing_data['title'] = (await title_elem.text_content() or '').strip()
                
                # Try to extract brand and model from title
                title_parts = listing_data['title'].split()
                if len(title_parts) >= 2:
                    listing_data['brand'] = title_parts[0]
                    listing_data['model'] = ' '.join(title_parts[1:3]) if len(title_parts) > 2 else title_parts[1]
            
            # Extract price
            price_elem = await item.query_selector('.price')
            if price_elem:
                try:
                    price_text = (await price_elem.text_content() or '').replace(',', '').replace('₪', '').strip()
                    if price_text.isdigit():
                        listing_data['price'] = float(price_text)
                except (ValueError, AttributeError):
                    pass
            
            # Extract other details
            details = await item.query_selector_all('.data')
            for detail in details:
                try:
                    text = (await detail.text_content() or '').strip()
                    if 'ק"מ' in text:
                        mileage = ''.join(filter(str.isdigit, text))
                        if mileage:
                            listing_data['mileage'] = int(mileage)
                    elif 'שנת' in text and text.replace('שנת', '').strip().isdigit():
                        listing_data['year'] = int(text.replace('שנת', '').strip())
                    elif 'יד' in text and 'מ' in text:  # Manual transmission
                        listing_data['transmission'] = 'manual'
                    elif 'אוטומט' in text:  # Automatic transmission
                        listing_data['transmission'] = 'automatic'
                    elif 'דיזל' in text:
                        listing_data['fuel_type'] = 'diesel'
                    elif 'בנזין' in text:
                        listing_data['fuel_type'] = 'petrol'
                    elif 'היברידי' in text:
                        listing_data['fuel_type'] = 'hybrid'
                    elif 'חשמלי' in text:
                        listing_data['fuel_type'] = 'electric'
                except Exception as e:
                    logger.debug(f"Error parsing detail '{text}': {str(e)}")
            
            # Extract location
            location_elem = await item.query_selector('.subtitle')
            if location_elem:
                listing_data['location'] = (await location_elem.text_content() or '').strip()
            
            return listing_data
            
        except Exception as e:
            logger.error(f"Error extracting listing data: {str(e)}")
            return None
    
    async def normalize_and_store(self, listings: List[Dict]) -> None:
        """Normalize and store the scraped listings in the database."""
        if not listings:
            return
        
        normalized_listings = []
        for listing in listings:
            try:
                # Normalize the listing data
                normalized = normalize_car_data(listing)
                if normalized:
                    normalized_listings.append(normalized)
            except Exception as e:
                logger.error(f"Error normalizing listing: {str(e)}")
                continue
        
        # TODO: Store the normalized listings in the database
        logger.info(f"Successfully normalized {len(normalized_listings)}/{len(listings)} listings")
