# Multi-Category PhilGEPS Scraper

A comprehensive Python tool for scraping procurement opportunities from multiple PhilGEPS categories in a single execution. This tool automates data collection, merging, and cleaning to provide analysis-ready procurement data.

## 🎯 Features

- **Multi-Category Support**: Scrape 7 predefined PhilGEPS categories simultaneously
- **User-Friendly Interface**: Interactive mode for non-programmers with numbered menus
- **Flexible Input Methods**: Command-line arguments, configuration files, or interactive mode
- **Automatic Data Processing**: Merging, deduplication, and data cleaning
- **Robust Error Handling**: Retry logic and per-category failure tolerance
- **Progress Tracking**: Real-time status updates with emojis and clear messages

## 📋 Supported Categories

1. **Packaging Supplies** (BusCatID: 28)
2. **Printing Services** (BusCatID: 29)
3. **Printing Supplies** (BusCatID: 51)
4. **Graphics Design** (BusCatID: 64)
5. **Corporate Giveaways** (BusCatID: 71)
6. **Tokens** (BusCatID: 129)
7. **Educational** (BusCatID: 134)
8. **Reproduction Services** (BusCatID: 150)

## 🚀 Quick Start

### Prerequisites

- Python 3.7+
- Virtual environment (recommended)

### Installation

1. **Clone or download the project**
2. **Set up virtual environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

### Basic Usage

#### Running a Single Category

**Option 1: Interactive Mode (Easiest)**

Run the script and select a single category number:

```bash
python multi_category_scraper.py
```

When prompted, enter just one number (e.g., `7` for Educational):

```
Enter numbers separated by commas (e.g., 1,3,7) or 'all' for all categories:
> 7
```

**Option 2: Configuration File (Recommended for Single Category)**

Create a configuration file with just one category:

```json
{
  "categories": ["Educational"],
  "limit": 0,
  "delay": 0.5,
  "no_clean": false,
  "retry_count": 2
}
```

Run with:

```bash
python multi_category_scraper.py --config categories_config.json
```

You can also use category IDs instead of names:

```json
{
  "categories": ["134"],
  "limit": 10
}
```

#### Running Multiple Categories

**Interactive Mode (Recommended for Beginners)**

Simply run the script without arguments for an interactive experience:

```bash
python multi_category_scraper.py
```

You'll see a numbered menu:

```
🎉 Welcome to PhilGEPS Multi-Category Scraper! 📋

Available categories:
1. Packaging Supplies (ID: 28)
2. Printing Services (ID: 29)
3. Printing Supplies (ID: 51)
4. Graphics Design (ID: 64)
5. Corporate Giveaways (ID: 71)
6. Tokens (ID: 129)
7. Educational (ID: 134)
8. Reproduction Services (ID: 150)

Enter numbers separated by commas (e.g., 1,3,7) or 'all' for all categories:
>
```

**Configuration File Mode**

Create a configuration file (`categories_config.json`):

```json
{
  "categories": ["Educational", "Tokens", "134", "71"],
  "limit": 10,
  "delay": 0.5,
  "no_clean": false,
  "retry_count": 2
}
```

Run with configuration:

```bash
python multi_category_scraper.py --config categories_config.json
```

**Note:** You can mix category names and IDs in the configuration file. Both `"Educational"` and `"134"` refer to the same category.

## 📁 Output Structure

The scraper creates an organized output structure:

```
output/
├── raw/                    # Intermediate per-category CSV files
│   ├── educational.csv
│   ├── tokens.csv
│   └── ...
├── merged/                 # Merged CSV before cleaning
│   └── philgeps_merged.csv
├── cleaned/               # Final cleaned CSV files
│   └── philgeps_merged_cleaned.csv
└── reports/               # Summary reports
    └── scraping_summary_[timestamp].txt
```

## ⚙️ Configuration Options

### Configuration File Format

```json
{
  "categories": ["Educational", "Tokens", "134", "71"],
  "limit": 0,
  "delay": 0.5,
  "no_clean": false,
  "retry_count": 2
}
```

**Configuration Parameters:**

- `categories`: List of category names or IDs to scrape
- `limit`: Maximum entries per category (0 = all)
- `delay`: Seconds to wait between requests
- `no_clean`: Skip automatic data cleaning
- `retry_count`: Number of retry attempts for failed categories

### Command-Line Arguments

When using `--config`, you can override settings from the config file:

| Argument        | Description                                               | Default | Notes                    |
| --------------- | --------------------------------------------------------- | ------- | ------------------------ |
| `--config`      | Path to configuration file                                | None    | Required for config mode |
| `--limit`       | Number of detail pages to scrape per category (0 for all) | 0       | Overrides config file    |
| `--delay`       | Seconds to sleep between detail requests                  | 0.5     | Overrides config file    |
| `--no-clean`    | Skip automatic data cleaning step                         | False   | Overrides config file    |
| `--retry-count` | Number of retry attempts for failed categories            | 2       | Overrides config file    |

**Note:** Category selection must be done via:

- Interactive mode (run without arguments)
- Configuration file (`--config` option)

**Example:** Override limit from config file:

```bash
python multi_category_scraper.py --config categories_config.json --limit 50
```

## 🔧 Advanced Usage

### Using Custom Category URLs

To scrape a category that's not in the predefined list, you need to add it to the code first (see [Adding New Categories](#adding-new-categories) section above). The scraper validates category URLs to ensure they match the PhilGEPS format before scraping.

### Error Handling

The scraper includes robust error handling:

- **Network Issues**: Automatic retry with exponential backoff
- **Invalid Categories**: Clear error messages with suggestions
- **Scraping Failures**: Continue with remaining categories
- **Data Processing Errors**: Graceful degradation with warnings

### Performance Optimization

- **Sequential Processing**: Prevents overwhelming the PhilGEPS server
- **Configurable Delays**: Adjust request timing to avoid rate limiting
- **Intermediate File Saving**: Prevents data loss during long scraping sessions
- **Memory Efficient**: Processes data in chunks to handle large datasets

## 📊 Data Output

### CSV Structure

The final cleaned CSV contains standardized columns:

- `refID`: Unique reference identifier
- `url`: Source URL
- `reference_number`: PhilGEPS reference number
- `procuring_entity`: Government entity name
- `title`: Opportunity title
- `category`: PhilGEPS category
- `abc_php`: Approved budget (cleaned numeric format)
- `date_published`: Publication date (YYYY-MM-DD format)
- `closing_datetime`: Closing date/time (YYYY-MM-DD format)
- `contact_person`: Contact information
- `contact_email`: Email address
- `contact_phone`: Phone number
- And more...

### Data Cleaning Features

- **Currency Standardization**: Converts PHP amounts to numeric format
- **Date Normalization**: Standardizes all dates to YYYY-MM-DD format
- **Deduplication**: Removes duplicate entries based on refID
- **Data Validation**: Ensures data integrity and consistency

## 🛠️ Development

### Project Structure

```
├── final_working_scraper.py    # Core scraping functions
├── multi_category_scraper.py   # Main orchestrator
├── data_cleaner.py            # Data cleaning utilities
├── categories_config.json     # Example configuration
├── requirements.txt           # Python dependencies
├── output/                    # Generated output files
└── tasks/                     # Documentation and task lists
```

### Adding New Categories

To scrape a category that's not in the predefined list, you need to add it to the `PREDEFINED_CATEGORIES` dictionary in `final_working_scraper.py`:

1. **Find the Category URL and BusCatID:**

   - Navigate to the PhilGEPS website
   - Go to the category page you want to scrape
   - Copy the URL from your browser
   - Extract the `BusCatID` parameter from the URL (e.g., `BusCatID=999`)

2. **Add to the Dictionary:**

   Open `final_working_scraper.py` and add your category to `PREDEFINED_CATEGORIES`:

```python
PREDEFINED_CATEGORIES = {
    # ... existing categories ...
    999: {
        "name": "New Category Name",
        "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=999&type=category&ClickFrom=OpenOpp"
    }
}
```

3. **Use Your New Category:**

   After adding the category, you can use it in:

   - **Interactive mode**: It will appear in the numbered menu
   - **Configuration file**: Use the name or ID you defined
   - **Example config:**

   ```json
   {
     "categories": ["New Category Name"],
     "limit": 10
   }
   ```

**Example:** To add a category with BusCatID 150:

```python
PREDEFINED_CATEGORIES = {
    # ... existing categories ...
    150: {
        "name": "Office Supplies",
        "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=150&type=category&ClickFrom=OpenOpp"
    }
}
```

## 🐛 Troubleshooting

### Common Issues

1. **"No links found"**: The category may be empty or the website structure changed
2. **Network timeouts**: Increase delay between requests or check internet connection
3. **Permission errors**: Ensure write permissions for the output directory
4. **Memory issues**: Reduce the limit parameter for large datasets

### Debug Mode

For detailed logging, modify the script to include debug output:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📝 Examples

### Example 1: Quick Single Category Scraping (Educational)

**Using Interactive Mode:**

```bash
python multi_category_scraper.py
# Then enter: 7
```

**Using Configuration File:**
Create `educational_config.json`:

```json
{
  "categories": ["Educational"],
  "limit": 10,
  "delay": 0.5
}
```

Run:

```bash
python multi_category_scraper.py --config educational_config.json
```

### Example 2: Single Category by ID

Create `tokens_config.json`:

```json
{
  "categories": ["129"],
  "limit": 20
}
```

Run:

```bash
python multi_category_scraper.py --config tokens_config.json
```

### Example 3: Multiple Categories

**Using Interactive Mode:**

```bash
python multi_category_scraper.py
# Then enter: 1,3,7
```

**Using Configuration File:**

```json
{
  "categories": ["Educational", "Tokens", "Corporate Giveaways"],
  "limit": 50,
  "delay": 1.0,
  "retry_count": 3
}
```

### Example 4: All Categories

**Using Interactive Mode:**

```bash
python multi_category_scraper.py
# Then enter: all
```

**Using Configuration File:**

```json
{
  "categories": [
    "Packaging Supplies",
    "Printing Services",
    "Printing Supplies",
    "Graphics Design",
    "Corporate Giveaways",
    "Tokens",
    "Educational"
  ],
  "limit": 0
}
```

### Example 5: Custom Settings for Single Category

```json
{
  "categories": ["Educational"],
  "limit": 100,
  "delay": 1.0,
  "no_clean": false,
  "retry_count": 5
}
```

## 📄 License

This project is provided as-is for educational and research purposes. Please respect the PhilGEPS website's terms of service and implement appropriate rate limiting.

## 🤝 Contributing

Contributions are welcome! Please ensure:

1. Code follows Python best practices
2. New features include appropriate error handling
3. Documentation is updated for new functionality
4. Tests are added for new features

## 📞 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the configuration examples
3. Ensure all dependencies are properly installed
4. Verify network connectivity to PhilGEPS

---

**Happy Scraping! 🎉**
