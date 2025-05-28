import os
import csv
import random
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from .utils import setup_logger, random_delay, random_user_agent, get_timestamp, handle_errors

# Load environment variables
load_dotenv()

# Configuration from environment variables
CITIES_FILE = "cities.txt"
MAX_PAGES_PER_CITY = int(os.getenv("MAX_PAGES_PER_CITY", 5))
REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", 2))
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", 5))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
OUTPUT_FILE = os.path.join("output", os.getenv("OUTPUT_FILE", "pediatricians_data.csv"))
TIMESTAMP_FORMAT = os.getenv("TIMESTAMP_FORMAT", "%Y-%m-%d_%H-%M-%S")
USER_AGENT_ROTATION = os.getenv("USER_AGENT_ROTATION", "true").lower() == "true"

# Headers for CSV output
HEADERS = ["City", "Clinic", "Location", "Fee", "Experience", "Phone", "Timestamp"]

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
        headless=True,
        proxy=proxy_config,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--no-sandbox",
            "--disable-setuid-sandbox"
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
        if any(ext in route.request.url for ext in [".jpg", ".png", ".gif", ".css", ".woff2"]):
            route.abort()
        else:
            route.continue_()
    
    context.route("**/*", route_handler)
    
    return browser, context

def scrape_city(page, city):
    """Scrape pediatricians for a single city"""
    url = f"https://www.practo.com/{city}/pediatrician"
    logger.info(f"Scraping: {url}")
    
    try:
        page.goto(url, timeout=60000)
        page.wait_for_selector(".reach-v2-card", timeout=15000)
    except Exception as e:
        logger.error(f"Failed to load page for {city}: {str(e)}")
        return []
    
    data = []
    page_count = 1
    
    while page_count <= MAX_PAGES_PER_CITY:
        logger.info(f"Scraping page {page_count} of {MAX_PAGES_PER_CITY}...")
        delay = random_delay(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        logger.debug(f"Random delay: {delay:.2f} seconds")
        
        try:
            cards = page.query_selector_all(".reach-v2-card")
            
            if not cards:
                logger.info(f"No cards found on page {page_count} for {city}")
                break
                
            for i, card in enumerate(cards):
                try:
                    # Extract basic info
                    name = card.query_selector("h2.u-color--primary").inner_text()
                    location = card.query_selector_all("span.u-bold")[0].inner_text()
                    fee = card.query_selector_all("span.u-bold")[1].inner_text()
                    
                    # Handle optional fields
                    try:
                        exp = card.query_selector("xpath=.//span[contains(., 'years experience')]").inner_text()
                    except:
                        exp = "N/A"
                    
                    phone = "N/A"
                    
                    # Try to get phone number
                    try:
                        contact_btn = card.query_selector("button:has-text('Contact Clinic')")
                        if contact_btn:
                            contact_btn.click()
                            page.wait_for_selector(".c-vn__number", timeout=3000)
                            phone = page.query_selector(".c-vn__number").inner_text()
                            # Close contact overlay
                            page.keyboard.press("Escape")
                            page.wait_for_timeout(1000)
                    except:
                        pass
                    
                    data.append({
                        "city": city,
                        "clinic": name,
                        "location": location,
                        "fee": fee,
                        "experience": exp,
                        "phone": phone,
                        "timestamp": get_timestamp()
                    })
                    
                    logger.info(f"Scraped {i+1}/{len(cards)}: {name} in {location}")
                    
                except Exception as e:
                    logger.error(f"Error processing card {i+1}: {str(e)}")
            
            # Try pagination
            next_btn = page.query_selector("xpath=//a[contains(@class, 'paginator__next')]")
            if next_btn and next_btn.is_enabled() and page_count < MAX_PAGES_PER_CITY:
                next_btn.click()
                page.wait_for_selector(".reach-v2-card", timeout=10000)
                page_count += 1
            else:
                logger.info(f"Reached last page for {city}")
                break
                
        except Exception as e:
            logger.error(f"Error on page {page_count}: {str(e)}")
            if not handle_errors(page, e, city, url, logger):
                break
    
    return data

def save_to_csv(data, filename):
    """Save scraped data to CSV file"""
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            for row in data:
                writer.writerow({
                    "City": row["city"],
                    "Clinic": row["clinic"],
                    "Location": row["location"],
                    "Fee": row["fee"],
                    "Experience": row["experience"],
                    "Phone": row["phone"],
                    "Timestamp": row["timestamp"]
                })
        logger.info(f"Saved {len(data)} records to {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save CSV: {str(e)}")
        return False

def main():
    cities = load_cities()
    if not cities:
        return
    
    all_data = []
    
    with sync_playwright() as playwright:
        browser, context = init_browser(playwright)
        page = context.new_page()
        
        for city in cities:
            city_data = scrape_city(page, city)
            all_data.extend(city_data)
            logger.info(f"✅ Finished {city} - {len(city_data)} records")
            
            # Random delay between cities
            delay = random_delay(REQUEST_DELAY_MIN * 2, REQUEST_DELAY_MAX * 3)
            logger.debug(f"Delay before next city: {delay:.2f} seconds")
        
        browser.close()
    
    # Save all data to CSV
    if all_data:
        save_to_csv(all_data, OUTPUT_FILE)
    else:
        logger.warning("No data scraped")

if __name__ == "__main__":
    logger.info("Starting Practo Scraper")
    main()
    logger.info("Scraping completed")