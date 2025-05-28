import random
import time
import logging
from datetime import datetime
from fake_useragent import UserAgent

def setup_logger():
    logger = logging.getLogger('practo_scraper')
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File handler
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(f'scraper_log_{timestamp}.log')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger

def random_delay(min_delay, max_delay):
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)
    return delay

def random_user_agent():
    ua = UserAgent()
    return ua.random

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def handle_errors(page, error, city, url, logger):
    logger.error(f"Error in {city} ({url}): {str(error)}")
    
    # Capture screenshot for debugging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"error_{city}_{timestamp}.png"
    page.screenshot(path=screenshot_path, full_page=True)
    logger.info(f"Screenshot saved: {screenshot_path}")
    
    # Try to recover by reloading
    try:
        page.reload()
        page.wait_for_load_state("networkidle")
        return True
    except:
        return False