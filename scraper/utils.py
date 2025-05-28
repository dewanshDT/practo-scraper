import random
import time
import logging
import re
import os
from datetime import datetime
from fake_useragent import UserAgent

def setup_logger():
    """Setup logger with both console and file handlers"""
    logger = logging.getLogger('practo_scraper')
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File handler
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'scraper_log_{timestamp}.log')
    
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    logger.info(f"📝 Log file created: {log_file}")
    return logger

def random_delay(min_delay, max_delay):
    """Generate and apply random delay between requests"""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)
    return delay

def random_user_agent():
    """Generate random user agent string"""
    try:
        ua = UserAgent()
        return ua.random
    except Exception:
        # Fallback user agents if fake-useragent fails
        fallback_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        return random.choice(fallback_agents)

def get_timestamp():
    """Get current timestamp in standardized format"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def clean_text(text):
    """Clean and normalize text data"""
    if not text or text == "N/A":
        return "N/A"
    
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove trailing commas and clean punctuation
    text = text.rstrip(',').strip()
    
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s\-.,₹()]', '', text)
    
    return text if text else "N/A"

def clean_fee(fee_text):
    """Clean and standardize fee information - returns number only (INR assumed)"""
    if not fee_text or fee_text == "N/A":
        return "N/A"
    
    # Handle common non-fee values
    non_fee_values = [
        "available today", "on - call", "call", "book appointment",
        "consult online", "video consult", "chat", "book", "available",
        "call now", "contact", "enquire", "book now"
    ]
    
    if fee_text.lower().strip() in non_fee_values:
        return "N/A"
    
    # Remove common text that's not part of the fee
    fee_text = re.sub(r'consultation fee at clinic', '', fee_text, flags=re.IGNORECASE)
    fee_text = re.sub(r'consultation fee', '', fee_text, flags=re.IGNORECASE)
    fee_text = re.sub(r'at clinic', '', fee_text, flags=re.IGNORECASE)
    
    # Extract fee with currency symbol (return number only)
    fee_match = re.search(r'₹\s*(\d+(?:,\d+)*)', fee_text)
    if fee_match:
        return fee_match.group(1)  # Return number without ₹ symbol
    
    # Extract fee with Rs./rs (return number only)
    rs_match = re.search(r'(?:rs\.?|RS\.?)\s*(\d+(?:,\d+)*)', fee_text, flags=re.IGNORECASE)
    if rs_match:
        return rs_match.group(1)  # Return number without Rs prefix
    
    # Extract standalone numbers that look like fees (reasonable range)
    number_match = re.search(r'\b(\d{2,5})\b', fee_text)
    if number_match:
        number = int(number_match.group(1))
        # Reasonable fee range: 100 to 50000
        if 100 <= number <= 50000:
            return str(number)  # Return as string number
    
    # If it contains digits but doesn't match patterns, clean and return
    if re.search(r'\d', fee_text):
        cleaned = re.sub(r'[^\d,.]', '', fee_text)  # Remove everything except digits, commas, dots
        if cleaned and cleaned.replace(',', '').replace('.', '').isdigit():
            return cleaned
    
    return clean_text(fee_text)

def clean_experience(exp_text):
    """Clean and standardize experience information"""
    if not exp_text or exp_text == "N/A":
        return "N/A"
    
    # Extract years of experience
    exp_match = re.search(r'(\d+)\s*(?:years?|yrs?)', exp_text.lower())
    if exp_match:
        years = exp_match.group(1)
        return f"{years} years"
    
    return clean_text(exp_text)

def clean_phone(phone_text):
    """Clean and standardize phone number"""
    if not phone_text or phone_text == "N/A":
        return "N/A"
    
    # Extract phone number (Indian format)
    phone_match = re.search(r'(\+?91[-\s]?)?([6-9]\d{9})', phone_text)
    if phone_match:
        return f"+91-{phone_match.group(2)}"
    
    # Extract 10-digit number
    digits_only = re.sub(r'[^\d]', '', phone_text)
    if len(digits_only) == 10 and digits_only[0] in '6789':
        return f"+91-{digits_only}"
    elif len(digits_only) == 12 and digits_only.startswith('91'):
        return f"+91-{digits_only[2:]}"
    
    return clean_text(phone_text)

def validate_and_clean_data(data):
    """Validate and clean scraped data"""
    if not data or not isinstance(data, dict):
        return None
    
    # Required fields validation
    if not data.get('clinic') or not data.get('city'):
        return None
    
    # Clean all fields
    cleaned_data = {
        'city': clean_text(data.get('city', '')).lower(),
        'clinic': clean_text(data.get('clinic', '')),
        'location': clean_text(data.get('location', '')),
        'fee': clean_fee(data.get('fee', '')),
        'experience': clean_experience(data.get('experience', '')),
        'phone': clean_phone(data.get('phone', '')),
        'timestamp': data.get('timestamp', get_timestamp())
    }
    
    # Final validation - ensure we have meaningful data
    if cleaned_data['clinic'] == "N/A" or len(cleaned_data['clinic']) < 2:
        return None
    
    return cleaned_data

def handle_errors(page, error, city, url, logger):
    """Enhanced error handling with recovery attempts"""
    logger.error(f"Error in {city} ({url}): {str(error)}")
    
    # Create screenshots directory
    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)
    
    # Capture screenshot for debugging
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(screenshot_dir, f"error_{city}_{timestamp}.png")
        page.screenshot(path=screenshot_path, full_page=True)
        logger.info(f"📸 Screenshot saved: {screenshot_path}")
    except Exception as e:
        logger.warning(f"Could not capture screenshot: {str(e)}")
    
    # Try to recover by reloading
    recovery_attempts = 3
    for attempt in range(recovery_attempts):
        try:
            logger.info(f"🔄 Recovery attempt {attempt + 1}/{recovery_attempts}")
            
            # Wait a bit before retry
            time.sleep(2 ** attempt)  # Exponential backoff
            
            # Reload page
            page.reload(timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            
            logger.info("✅ Page recovered successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Recovery attempt {attempt + 1} failed: {str(e)}")
            
    logger.error("❌ All recovery attempts failed")
    return False

def extract_phone_from_page(page, logger):
    """Try to extract phone number by clicking contact buttons"""
    try:
        # Multiple selectors for contact buttons
        contact_selectors = [
            'button:has-text("Contact Clinic")',
            'button:has-text("Call")',
            'a:has-text("Contact")',
            '.contact-btn',
            '[data-qa-id="contact"]'
        ]
        
        for selector in contact_selectors:
            try:
                contact_btn = page.query_selector(selector)
                if contact_btn and contact_btn.is_visible():
                    contact_btn.click()
                    
                    # Wait for phone number to appear
                    phone_selectors = ['.c-vn__number', '.phone-number', '[data-qa-id="phone"]']
                    for phone_selector in phone_selectors:
                        try:
                            page.wait_for_selector(phone_selector, timeout=3000)
                            phone_element = page.query_selector(phone_selector)
                            if phone_element:
                                phone = phone_element.inner_text().strip()
                                
                                # Close any overlays
                                try:
                                    page.keyboard.press("Escape")
                                    page.wait_for_timeout(1000)
                                except:
                                    pass
                                
                                return clean_phone(phone)
                        except:
                            continue
                    break
            except Exception as e:
                logger.debug(f"Contact button extraction failed with {selector}: {str(e)}")
                continue
                
    except Exception as e:
        logger.debug(f"Phone extraction failed: {str(e)}")
    
    return "N/A"

def create_progress_bar(current, total, width=50):
    """Create a simple text-based progress bar"""
    percent = (current / total) * 100
    filled = int(width * current // total)
    bar = '█' * filled + '░' * (width - filled)
    return f'|{bar}| {percent:.1f}% ({current}/{total})'

def log_memory_usage():
    """Log current memory usage if psutil is available"""
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        return f"Memory: {memory_mb:.1f}MB"
    except ImportError:
        return "Memory: N/A (psutil not installed)"
    except Exception:
        return "Memory: N/A"