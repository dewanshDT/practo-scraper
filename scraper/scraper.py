import os
import csv
import random
import time
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from utils import setup_logger, random_delay, random_user_agent, get_timestamp, handle_errors, validate_and_clean_data

# Load environment variables
load_dotenv()

# Configuration from environment variables
CITIES_FILE = os.path.join(os.path.dirname(__file__), "cities.txt")
MAX_PAGES_PER_CITY = int(os.getenv("MAX_PAGES_PER_CITY", 5))
REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", 2))
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", 5))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
OUTPUT_FILE = os.path.join("output", os.getenv("OUTPUT_FILE", "pediatricians_data.csv"))
TIMESTAMP_FORMAT = os.getenv("TIMESTAMP_FORMAT", "%Y-%m-%d_%H-%M-%S")
USER_AGENT_ROTATION = os.getenv("USER_AGENT_ROTATION", "true").lower() == "true"
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
STOP_ON_EMPTY_PAGE = os.getenv("STOP_ON_EMPTY_PAGE", "true").lower() == "true"
CONTINUE_ON_ERROR = os.getenv("CONTINUE_ON_ERROR", "true").lower() == "true"
BATCH_SAVE_SIZE = int(os.getenv("BATCH_SAVE_SIZE", 50))
EXTRACT_PHONE = os.getenv("EXTRACT_PHONE", "true").lower() == "true"

# Headers for CSV output
HEADERS = ["City", "Clinic", "Location", "Fee", "Experience", "Phone", "Timestamp"]

# Improved selectors with fallbacks
SELECTORS = {
    'cards': ['.reach-v2-card', '.doctor-card', '[data-qa-id="doctor_card"]'],
    'name': ['h2.u-color--primary', 'h2[data-qa-id="doctor_name"]', '.doctor-name', 'h2', 'h3'],
    'location': ['span.u-bold', '.location', '[data-qa-id="clinic_name"]', '.clinic-name'],
    'fee': ['span.u-bold', '.fee', '[data-qa-id="consultation_fee"]', '.consultation-fee'],
    'experience': ['span:has-text("years experience")', '.experience', '[data-qa-id="experience"]'],
    'contact_btn': ['button:has-text("Contact Clinic")', '.contact-btn', '[data-qa-id="contact"]'],
    'phone': ['.c-vn__number', '.phone-number', '[data-qa-id="phone"]'],
    'next_btn': ['a.paginator__next', '.next-page', '[data-qa-id="next_page"]']
}

# Setup logger
logger = setup_logger()

def load_cities():
    """Load cities from text file"""
    try:
        with open(CITIES_FILE, "r") as f:
            cities = [line.strip().lower() for line in f if line.strip()]
        logger.info(f"Loaded {len(cities)} cities from {CITIES_FILE}")
        return cities
    except FileNotFoundError:
        logger.error(f"Cities file not found: {CITIES_FILE}")
        return []
    except Exception as e:
        logger.error(f"Error loading cities: {str(e)}")
        return []

def init_browser(playwright):
    """Initialize browser with anti-blocking settings"""
    # Proxy configuration (if enabled)
    proxy_config = None
    if os.getenv("PROXY_ENABLED", "false").lower() == "true":
        proxy_server = os.getenv("PROXY_SERVER")
        proxy_user = os.getenv("PROXY_USER")
        proxy_password = os.getenv("PROXY_PASSWORD")
        
        if proxy_server:
            proxy_config = {
                "server": proxy_server,
                "username": proxy_user,
                "password": proxy_password
            }
            logger.info(f"Using proxy: {proxy_server}")

    # Launch browser
    browser = playwright.chromium.launch(
        headless=HEADLESS,
        proxy=proxy_config,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding"
        ]
    )
    
    context = browser.new_context(
        user_agent=random_user_agent() if USER_AGENT_ROTATION else None,
        viewport={"width": 1366, "height": 768},
        java_script_enabled=True,
        ignore_https_errors=True
    )
    
    # Block unnecessary resources
    def route_handler(route):
        if any(ext in route.request.url for ext in [".jpg", ".png", ".gif", ".css", ".woff2", ".svg", ".ico"]):
            route.abort()
        else:
            route.continue_()
    
    context.route("**/*", route_handler)
    
    return browser, context

def find_element_with_selectors(element, selectors, method='query_selector'):
    """Try multiple selectors to find an element"""
    for selector in selectors:
        try:
            if method == 'query_selector':
                result = element.query_selector(selector)
                if result:
                    return result
            elif method == 'query_selector_all':
                result = element.query_selector_all(selector)
                if result:
                    return result
        except Exception as e:
            logger.debug(f"Selector '{selector}' failed: {str(e)}")
            continue
    return None

def extract_doctor_data(card, city):
    """Extract data from a single doctor card with improved error handling"""
    try:
        # Extract name
        name_element = find_element_with_selectors(card, SELECTORS['name'])
        if not name_element:
            logger.warning("Could not find doctor name")
            return None
        name = name_element.inner_text().strip()
        
        # Extract location - use specific data-qa-id attributes
        location = "N/A"
        
        # Extract the three components
        clinic_name_element = card.query_selector('[data-qa-id="doctor_clinic_name"]')
        practice_locality_element = card.query_selector('[data-qa-id="practice_locality"]')
        practice_city_element = card.query_selector('[data-qa-id="practice_city"]')
        
        # Get text from each element
        clinic_name = clinic_name_element.inner_text().strip() if clinic_name_element else ""
        practice_locality = practice_locality_element.inner_text().strip() if practice_locality_element else ""
        practice_city = practice_city_element.inner_text().strip() if practice_city_element else ""
        
        # Clean any trailing commas from individual components
        clinic_name = clinic_name.rstrip(',').strip()
        practice_locality = practice_locality.rstrip(',').strip()  
        practice_city = practice_city.rstrip(',').strip()
        
        # Debug logging
        logger.debug(f"Clinic: '{clinic_name}', Locality: '{practice_locality}', City: '{practice_city}'")
        
        # Format as: ${doctor_clinic_name}, ${practice_locality}, ${practice_city}
        location_parts = []
        if clinic_name:
            location_parts.append(clinic_name)
        if practice_locality:
            location_parts.append(practice_locality)
        if practice_city:
            location_parts.append(practice_city)
        
        if location_parts:
            location = ", ".join(location_parts)
            logger.debug(f"Found location: {location}")
        else:
            logger.debug("No location data found in data-qa-id attributes")
        
        # Extract fee - improved logic for consultation fee
        fee = "N/A"
        
        # Primary: Try specific consultation fee selector first
        fee_element = card.query_selector('[data-qa-id="consultation_fee"]')
        if fee_element:
            fee_text = fee_element.inner_text().strip()
            logger.debug(f"Found consultation fee element: {fee_text}")
        else:
            # Secondary: Look for fee-related patterns in specific containers
            fee_selectors = [
                '[data-qa-id*="fee"]',
                '[class*="consultation-fee"]',
                '[class*="fee"]',
                'span:has-text("₹")',
                '.fee',
                'span.u-bold'
            ]
            
            fee_text = "N/A"
            for selector in fee_selectors:
                try:
                    elements = card.query_selector_all(selector)
                    for element in elements:
                        text = element.inner_text().strip()
                        # Check if this looks like a consultation fee
                        if ('₹' in text or 
                            (text.isdigit() and len(text) >= 2 and len(text) <= 5) or
                            'consultation' in text.lower() or
                            'fee' in text.lower()):
                            # Avoid non-fee values
                            if not any(exclude in text.lower() for exclude in [
                                'available today', 'on - call', 'call now', 'book appointment',
                                'consult online', 'video consult', 'chat', 'book now', 'contact',
                                'patient stories', 'experience', 'years'
                            ]):
                                fee_text = text
                                logger.debug(f"Found fee with selector {selector}: {fee_text}")
                                break
                    if fee_text != "N/A":
                        break
                except Exception as e:
                    logger.debug(f"Fee selector {selector} failed: {str(e)}")
                    continue
        
        # Tertiary: Look specifically for currency patterns if no structured fee found
        if fee_text == "N/A":
            try:
                # Look for any element containing currency or fee-like patterns
                all_elements = card.query_selector_all('span, div')
                for element in all_elements:
                    text = element.inner_text().strip()
                    # Look for currency patterns or fee indicators
                    if (('₹' in text and len(text) <= 20) or 
                        ('fee' in text.lower() and any(char.isdigit() for char in text)) or
                        ('consultation' in text.lower() and any(char.isdigit() for char in text))):
                        # Avoid common non-fee texts
                        if not any(exclude in text.lower() for exclude in [
                            'patient stories', 'experience overall', 'available today',
                            'on - call', 'book appointment', 'video consult'
                        ]):
                            fee_text = text
                            logger.debug(f"Found fee with currency pattern: {fee_text}")
                            break
            except Exception as e:
                logger.debug(f"Fee currency search failed: {str(e)}")
        
        fee = fee_text if 'fee_text' in locals() and fee_text != "N/A" else "N/A"
        
        # Extract experience with better error handling
        experience = "N/A"
        try:
            # Try multiple approaches for experience
            exp_selectors = [
                '[data-qa-id="experience"]',
                'span:has-text("year experience")',
                'span:has-text("years experience")', 
                'span:has-text("year")',
                'span:has-text("years")',
                '[class*="experience"]'
            ]
            
            for selector in exp_selectors:
                try:
                    exp_element = card.query_selector(selector)
                    if exp_element:
                        exp_text = exp_element.inner_text().strip()
                        # Extract actual number of years
                        years_match = re.search(r'(\d+)\s*(?:years?|yrs?)', exp_text.lower())
                        if years_match:
                            years = years_match.group(1)
                            experience = f"{years} years"
                            logger.debug(f"Found experience with selector {selector}: {experience}")
                            break
                        elif exp_text and 'years experience overall' not in exp_text.lower():
                            experience = exp_text
                            logger.debug(f"Found experience text with selector {selector}: {experience}")
                            break
                except Exception as e:
                    logger.debug(f"Experience selector {selector} failed: {str(e)}")
                    continue
            
            # If no structured experience found, try general search
            if experience == "N/A":
                try:
                    all_text_elements = card.query_selector_all('span, div')
                    for element in all_text_elements:
                        text = element.inner_text().strip()
                        # Look for experience patterns
                        years_match = re.search(r'(\d+)\s*(?:years?|yrs?)\s*(?:experience|exp)', text.lower())
                        if years_match:
                            years = years_match.group(1)
                            experience = f"{years} years"
                            logger.debug(f"Found experience in general search: {experience}")
                            break
                except:
                    pass
                    
        except (AttributeError, PlaywrightTimeoutError) as e:
            logger.debug(f"Experience extraction failed: {str(e)}")
        
        # Extract phone number - simplified without button clicking
        phone = "N/A"
        
        if EXTRACT_PHONE:
            try:
                # Look for visible phone numbers without clicking buttons
                phone_selectors = [
                    '[data-qa-id="phone_number"]',
                    '.c-vn__number',
                    '.phone-number',
                    '[data-qa-id="phone"]'
                ]
                
                for selector in phone_selectors:
                    try:
                        phone_element = card.query_selector(selector)
                        if phone_element:
                            phone_text = phone_element.inner_text().strip()
                            if phone_text:
                                phone = phone_text
                                logger.debug(f"Found phone: {phone}")
                                break
                    except Exception as e:
                        logger.debug(f"Phone selector {selector} failed: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Error during phone extraction: {str(e)}")
        else:
            logger.debug("Phone extraction disabled")
        
        data = {
            "city": city,
            "clinic": name,
            "location": location,
            "fee": fee,
            "experience": experience,
            "phone": phone,
            "timestamp": get_timestamp()
        }
        
        # Validate and clean data
        cleaned_data = validate_and_clean_data(data)
        if not cleaned_data:
            logger.warning(f"Data validation failed for: {name}")
            return None
            
        return cleaned_data
        
    except Exception as e:
        logger.error(f"Error extracting doctor data: {str(e)}")
        return None

def scrape_city(page, city, existing_data=None):
    """Scrape pediatricians for a single city with URL-based pagination"""
    if existing_data is None:
        existing_data = set()
    
    base_url = f"https://www.practo.com/{city}/pediatrician"
    logger.info(f"Scraping: {base_url}")
    
    data = []
    
    for page_num in range(1, MAX_PAGES_PER_CITY + 1):
        # Construct URL with page parameter
        if page_num == 1:
            url = base_url  # First page doesn't need page parameter
        else:
            url = f"{base_url}?page={page_num}"
        
        logger.info(f"Scraping page {page_num} of {MAX_PAGES_PER_CITY} for {city}...")
        logger.info(f"URL: {url}")
        
        try:
            # Navigate to the specific page
            page.goto(url, timeout=60000)
            
            # Try multiple selectors for cards
            cards_found = False
            for selector in SELECTORS['cards']:
                try:
                    page.wait_for_selector(selector, timeout=15000)
                    cards_found = True
                    break
                except PlaywrightTimeoutError:
                    continue
            
            if not cards_found:
                logger.warning(f"Could not find any doctor cards on page {page_num} for {city}")
                # If no cards found on this page, try next page (might be empty pages)
                continue
                
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout loading page {page_num} for {city}: {str(e)}")
            continue
        except Exception as e:
            logger.error(f"Failed to load page {page_num} for {city}: {str(e)}")
            continue
        
        # Random delay between page requests
        delay = random_delay(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        logger.debug(f"Random delay: {delay:.2f} seconds")
        
        try:
            # Find cards using flexible selectors
            cards = None
            for selector in SELECTORS['cards']:
                cards = page.query_selector_all(selector)
                if cards:
                    break
            
            if not cards:
                logger.info(f"No cards found on page {page_num} for {city}")
                # If no cards on this page, we might have reached the end
                logger.info(f"Reached end of results at page {page_num} for {city}")
                break
                
            logger.info(f"Found {len(cards)} doctor cards on page {page_num}")
            
            page_data_count = 0
            for i, card in enumerate(cards):
                try:
                    doctor_data = extract_doctor_data(card, city)
                    if doctor_data:
                        # Create unique identifier for deduplication
                        unique_id = f"{doctor_data['clinic']}_{doctor_data['location']}"
                        if unique_id not in existing_data:
                            data.append(doctor_data)
                            existing_data.add(unique_id)
                            page_data_count += 1
                            logger.info(f"✅ Scraped {i+1}/{len(cards)}: {doctor_data['clinic']} in {doctor_data['location']}")
                        else:
                            logger.debug(f"Duplicate found, skipping: {doctor_data['clinic']}")
                    else:
                        logger.warning(f"❌ Failed to extract data from card {i+1}")
                    
                except Exception as e:
                    logger.error(f"Error processing card {i+1}: {str(e)}")
            
            logger.info(f"📄 Page {page_num} summary: {page_data_count} new records added")
            
            # If no new data was found on this page, we might have reached the end
            if page_data_count == 0 and STOP_ON_EMPTY_PAGE:
                logger.info(f"No new data found on page {page_num}, stopping pagination for {city}")
                break
                
        except Exception as e:
            logger.error(f"Error on page {page_num}: {str(e)}")
            if not handle_errors(page, e, city, url, logger):
                continue  # Try next page instead of breaking
    
    logger.info(f"🏁 Completed {city}: {len(data)} unique records scraped across {min(page_num, MAX_PAGES_PER_CITY)} pages")
    return data

def save_to_csv(data, filename):
    """Save scraped data to CSV file with improved error handling"""
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Check if file exists to determine if we need headers
        file_exists = os.path.exists(filename)
        
        with open(filename, "a" if file_exists else "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            
            # Write headers only if file is new
            if not file_exists:
                writer.writeheader()
            
            for row in data:
                try:
                    writer.writerow({
                        "City": row["city"],
                        "Clinic": row["clinic"],
                        "Location": row["location"],
                        "Fee": row["fee"],
                        "Experience": row["experience"],
                        "Phone": row["phone"],
                        "Timestamp": row["timestamp"]
                    })
                except Exception as e:
                    logger.error(f"Error writing row: {str(e)}")
                    
        logger.info(f"💾 Saved {len(data)} records to {filename}")
        return True
        
    except PermissionError as e:
        logger.error(f"Permission denied writing to {filename}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to save CSV: {str(e)}")
        return False

def load_existing_data(filename):
    """Load existing data for deduplication"""
    existing_data = set()
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    unique_id = f"{row.get('Clinic', '')}_{row.get('Location', '')}"
                    existing_data.add(unique_id)
            logger.info(f"Loaded {len(existing_data)} existing records for deduplication")
    except Exception as e:
        logger.warning(f"Could not load existing data: {str(e)}")
    return existing_data

def main():
    """Main execution function with improved error handling and progress tracking"""
    cities = load_cities()
    if not cities:
        logger.error("No cities to scrape. Exiting.")
        return
    
    logger.info(f"🚀 Starting scraper for {len(cities)} cities")
    
    # Load existing data for deduplication
    existing_data = load_existing_data(OUTPUT_FILE)
    
    all_data = []
    successful_cities = 0
    failed_cities = 0
    
    with sync_playwright() as playwright:
        try:
            browser, context = init_browser(playwright)
            page = context.new_page()
            
            for i, city in enumerate(cities, 1):
                logger.info(f"📍 Processing city {i}/{len(cities)}: {city.upper()}")
                
                try:
                    city_data = scrape_city(page, city, existing_data)
                    if city_data:
                        all_data.extend(city_data)
                        successful_cities += 1
                        logger.info(f"✅ Finished {city} - {len(city_data)} new records")
                        
                        # Save data incrementally to prevent loss
                        if len(all_data) >= BATCH_SAVE_SIZE:  # Save every BATCH_SAVE_SIZE records
                            save_to_csv(all_data, OUTPUT_FILE)
                            all_data = []  # Clear to save memory
                    else:
                        failed_cities += 1
                        logger.warning(f"⚠️  No data scraped for {city}")
                    
                    # Random delay between cities
                    if i < len(cities):  # Don't delay after last city
                        delay = random_delay(REQUEST_DELAY_MIN * 2, REQUEST_DELAY_MAX * 3)
                        logger.debug(f"Delay before next city: {delay:.2f} seconds")
                        
                except KeyboardInterrupt:
                    logger.info("⛔ Scraping interrupted by user")
                    break
                except Exception as e:
                    failed_cities += 1
                    logger.error(f"❌ Failed to scrape {city}: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"Browser initialization failed: {str(e)}")
            return
        finally:
            try:
                browser.close()
            except:
                pass
    
    # Save any remaining data
    if all_data:
        save_to_csv(all_data, OUTPUT_FILE)
    
    # Final summary
    total_records = successful_cities  # Approximation since we don't count exact records here
    logger.info(f"🎉 Scraping completed!")
    logger.info(f"📊 Summary: {successful_cities} successful cities, {failed_cities} failed cities")
    logger.info(f"📁 Output saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    logger.info("🔧 Starting Practo Scraper v2.0")
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⛔ Program interrupted by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {str(e)}")
    finally:
        logger.info("🏁 Scraping session ended")