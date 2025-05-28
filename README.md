# Practo Scraper v2.0 🏥

A robust, production-ready web scraper for extracting pediatrician information from Practo.com across multiple Indian cities.

## ✨ Features

### 🔧 **Core Improvements**

- **Fixed import issues** - Absolute imports for proper module loading
- **Enhanced error handling** - Specific exception handling with recovery mechanisms
- **Data validation & cleaning** - Automatic data cleaning and validation
- **Flexible selectors** - Multiple fallback selectors for robust scraping
- **Deduplication** - Automatic duplicate detection and removal
- **Incremental saving** - Data saved every N records to prevent loss
- **URL-based pagination** - Reliable pagination using `?page=N` parameters

### 🛡️ **Anti-Detection Features**

- User agent rotation with fallback options
- Random delays between requests (2-5 seconds)
- Browser stealth mode with anti-automation flags
- Resource blocking for faster scraping
- Proxy support (configurable)

### 📊 **Data Quality**

- **Smart data cleaning**: Standardized fees, phone numbers, experience
- **Input validation**: Ensures meaningful data collection
- **Timestamp tracking**: All records include collection time
- **UTF-8 encoding**: Proper handling of international characters

### 🔍 **Debugging & Monitoring**

- **Comprehensive logging**: Console + file logs with different levels
- **Error screenshots**: Automatic screenshot capture on errors
- **Progress tracking**: Real-time progress with emoji indicators
- **Memory monitoring**: Optional memory usage tracking
- **Recovery mechanisms**: Multi-attempt error recovery

## 📁 Project Structure

```
practo_scraper/
├── scraper/
│   ├── scraper.py          # Main scraping logic (enhanced)
│   ├── utils.py            # Utility functions (enhanced)
│   └── cities.txt          # Target cities list
├── output/                 # CSV output directory
├── logs/                   # Log files (auto-created)
├── screenshots/            # Error screenshots (auto-created)
├── docker-compose.yml      # Docker orchestration
├── Dockerfile             # Container configuration
├── requirements.txt       # Python dependencies
├── env.example            # Environment configuration example
└── README.md              # This file
```

## 🚀 Quick Start

### Method 1: Docker (Recommended)

1. **Clone and setup**:

   ```bash
   cd practo_scraper
   cp env.example .env  # Edit as needed
   ```

2. **Run with Docker**:
   ```bash
   docker-compose up --build
   ```

### Method 2: Local Python

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Setup environment**:

   ```bash
   cp env.example .env  # Edit configuration
   ```

3. **Run scraper**:
   ```bash
   cd scraper
   python scraper.py
   ```

## ⚙️ Configuration

Edit `.env` file to customize scraping behavior:

```env
# Scraping Settings
MAX_PAGES_PER_CITY=5          # Pages to scrape per city (uses ?page=N)
REQUEST_DELAY_MIN=2.0         # Minimum delay between requests
REQUEST_DELAY_MAX=5.0         # Maximum delay between requests
MAX_RETRIES=3                 # Max retry attempts on errors

# Output Settings
OUTPUT_FILE=pediatricians_data.csv  # Output filename
TIMESTAMP_FORMAT=%Y-%m-%d_%H-%M-%S  # Timestamp format

# Browser Settings
USER_AGENT_ROTATION=true      # Enable user agent rotation
HEADLESS=true                 # Run browser in headless mode

# Pagination Settings
STOP_ON_EMPTY_PAGE=true       # Stop when page has no new data
CONTINUE_ON_ERROR=true        # Continue to next page on errors

# Performance Settings
BATCH_SAVE_SIZE=50           # Save data every N records

# Proxy Settings (optional)
PROXY_ENABLED=false
PROXY_SERVER=http://proxy.example.com:8080
PROXY_USER=your_username
PROXY_PASSWORD=your_password
```

## 📊 Output Format

CSV file with the following columns:

| Column     | Description            | Example                      |
| ---------- | ---------------------- | ---------------------------- |
| City       | Target city            | `mumbai`                     |
| Clinic     | Doctor/Clinic name     | `Dr. Smith Pediatric Clinic` |
| Location   | Area/Address           | `Bandra West`                |
| Fee        | Consultation fee (INR) | `500`                        |
| Experience | Years of practice      | `15 years`                   |
| Phone      | Contact number         | `+91-9876543210`             |
| Timestamp  | Data collection time   | `2024-01-15 14:30:25`        |

## 🎯 Target Cities

Currently configured for 10 major Indian cities:

- Mumbai, Delhi, Bangalore, Kolkata, Chennai
- Pune, Hyderabad, Ahmedabad, Jaipur, Lucknow

Modify `scraper/cities.txt` to add/remove cities.

## 🛠️ Enhanced Features

### 🔄 **Error Recovery**

- Multi-attempt recovery with exponential backoff
- Page reload on failures
- Screenshot capture for debugging
- Graceful handling of network issues

### 🧹 **Data Cleaning**

- **Fee standardization**: `500`, `1000` (numbers only, INR assumed)
- **Phone formatting**: `+91-9876543210`
- **Experience parsing**: `15 years`
- **Text normalization**: Cleaned whitespace and special characters

### 📈 **Performance**

- **Incremental saving**: Data saved every N records (configurable)
- **Memory efficiency**: Periodic data clearing
- **Resource blocking**: Images, CSS, fonts blocked
- **Deduplication**: Prevents duplicate entries
- **URL-based pagination**: Direct page access via `?page=N` parameters
- **Smart pagination**: Stops when no new data found (configurable)

### 🔧 **Monitoring**

- **Real-time progress**: `📍 Processing city 3/10: MUMBAI`
- **Status indicators**: `✅ Success`, `❌ Failed`, `⚠️ Warning`
- **Performance metrics**: Memory usage, timing
- **Detailed logging**: Debug, info, warning, error levels

## 📝 Logging

Logs are saved to `logs/scraper_log_YYYYMMDD_HHMMSS.log` with:

- **Console output**: INFO level and above
- **File output**: DEBUG level and above
- **Error screenshots**: Saved to `screenshots/` directory

## 🐛 Troubleshooting

### Common Issues:

1. **Import Error**: Ensure you're running from the correct directory
2. **Playwright Error**: Run `playwright install chromium`
3. **Permission Error**: Check output directory permissions
4. **No Data**: Verify internet connection and city names

### Debug Mode:

Set `LOG_LEVEL=DEBUG` in `.env` for detailed logging.

## 🔮 Advanced Usage

### Custom Selectors

Modify `SELECTORS` dictionary in `scraper.py` for different websites or layout changes.

### Proxy Rotation

Enable `PROXY_ENABLED=true` and configure proxy settings for IP rotation.

### Parallel Processing

Future enhancement: Set `PARALLEL_CITIES=true` for concurrent city processing.

## 📊 Performance Metrics

**Typical Performance**:

- ~50-100 records per city
- ~2-3 minutes per city
- ~30-60 minutes for all 10 cities
- Memory usage: ~100-200MB

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make improvements
4. Test thoroughly
5. Submit a pull request

## ⚖️ Legal Notice

This scraper is for educational and research purposes. Please:

- Respect website terms of service
- Use reasonable delays between requests
- Don't overwhelm the target server
- Consider the website's robots.txt

## 📄 License

MIT License - Feel free to modify and distribute.

---

**Built with ❤️ for healthcare data research**
