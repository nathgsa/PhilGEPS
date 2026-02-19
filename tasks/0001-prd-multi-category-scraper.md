# Product Requirements Document: Multi-Category PhilGEPS Scraper Enhancement

## Introduction/Overview

This document outlines the requirements for enhancing the existing PhilGEPS scraper (`final_working_scraper.py`) to support scraping multiple predefined procurement categories in a single execution. Currently, the scraper is hardcoded to scrape only one category (Printing Services, BusCatID=29). This enhancement will allow users to select from seven predefined categories, scrape multiple categories at once, automatically merge the results, and clean the data using the existing `data_cleaner.py`.

**Problem:** Users must manually run the scraper multiple times and manually merge/clean data when collecting procurement information across different categories.

**Solution:** Create a multi-category scraper orchestrator that automates category selection, scraping, merging, and data cleaning in a single workflow.

## Goals

1. Enable scraping of multiple predefined PhilGEPS categories in a single execution
2. Provide flexible input methods (command-line and config file) for category selection
3. Automatically merge data from all selected categories into one consolidated CSV
4. Integrate automatic data cleaning using the existing data cleaner
5. Implement robust error handling with retry capability and per-category failure tolerance
6. Maintain backward compatibility with existing scraper functionality

## User Stories

1. **As a procurement researcher**, I want to scrape multiple categories at once so that I can gather comprehensive data without running the script multiple times.

2. **As a data analyst**, I want the system to automatically merge and clean data from multiple categories so that I receive analysis-ready data in one file.

3. **As a power user**, I want to select categories via either command-line or config file so that I can choose the most convenient method for my workflow.

4. **As an operator**, I want the scraper to continue if one category fails so that I don't lose data from successful categories.

5. **As a system administrator**, I want configurable retry logic so that transient network issues don't cause complete failures.

## Functional Requirements

### 1. Predefined Categories

The system **must** include seven predefined categories with their names, BusCatIDs, and full URLs:

- **Packaging Supplies** (BusCatID=28)

  - URL: `https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=28&type=category&ClickFrom=OpenOpp`

- **Printing Services** (BusCatID=29) - _currently used in the existing scraper_

  - URL: `https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=29&type=category&ClickFrom=OpenOpp`

- **Printing Supplies** (BusCatID=51)

  - URL: `https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=51&type=category&ClickFrom=OpenOpp`

- **Graphics Design** (BusCatID=64)

  - URL: `https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=64&type=category&ClickFrom=OpenOpp`

- **Corporate Giveaways** (BusCatID=71)

  - URL: `https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=71&type=category&ClickFrom=OpenOpp`

- **Tokens** (BusCatID=129)

  - URL: `https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=129&type=category&ClickFrom=OpenOpp`

- **Educational** (BusCatID=134)
  - URL: `https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=134&type=category&ClickFrom=OpenOpp`

### 2. Category Selection Methods

**FR-2.1:** Users **must** be able to select categories via command-line arguments using category names or IDs.

- Example: `--categories "Educational,Tokens,Packaging Supplies"`
- Example: `--categories "134,129,28"`

**FR-2.2:** Users **must** be able to provide a JSON or YAML configuration file listing desired categories.

- Example: `--config categories_config.json`

**FR-2.3:** The system **must** support scraping a single category or multiple categories.

**FR-2.4:** If no category is specified, the system **must** display a user-friendly menu with numbered options and allow simple number selection (e.g., "Enter 1-7 to select a category, or 'all' for all categories").

**FR-2.5:** The system **must** validate category names/IDs and display helpful error messages in plain English for invalid selections (e.g., "Sorry, 'Education' is not valid. Did you mean 'Educational'? Available options are: Packaging Supplies, Printing Services, etc.").

### 3. URL Format Support

**FR-3.1:** The system **must** accept full PhilGEPS category URLs as input.

**FR-3.2:** The system **must** extract the BusCatID from provided URLs using regex pattern matching.

**FR-3.3:** The system **must** validate that URLs match the expected PhilGEPS category page format.

**FR-3.4:** The system **must** reject invalid or malformed URLs with clear error messages.

### 4. Data Collection

**FR-4.1:** The system **must** scrape each selected category sequentially (not in parallel).

**FR-4.2:** The scraped data already contains a "category" field from PhilGEPS, so no additional category tracking column is needed.

**FR-4.3:** The system **must** display user-friendly progress information showing:

- Which category is currently being scraped (e.g., "📋 Scraping: Educational Services...")
- Page-by-page progress within each category (e.g., "Processing page 3 of 15...")
- Number of entries found per category (e.g., "Found 23 opportunities so far...")
- Estimated time remaining when possible

**FR-4.4:** The system **must** save intermediate CSV files for each category before merging (to prevent data loss).

### 5. Data Merging

**FR-5.1:** The system **must** merge all category data into a single CSV file.

**FR-5.2:** The system **must** remove duplicate entries based on refID (keeping the first occurrence).

**FR-5.3:** The system **must** preserve the order of entries (first category's entries first, then subsequent categories).

**FR-5.4:** The system **must** report the number of duplicate entries removed during merging.

### 6. Data Cleaning Integration

**FR-6.1:** After merging, the system **must** automatically invoke `PhilGEPSDataCleaner` from `data_cleaner.py` on the merged CSV.

**FR-6.2:** The system **must** pass the appropriate input and output file paths to the data cleaner.

**FR-6.3:** The final output **must** be the cleaned, merged CSV file with standardized date and currency formats.

**FR-6.4:** Users **must** be able to skip the automatic cleaning step via a `--no-clean` flag.

### 7. Error Handling

**FR-7.1:** If one category fails to scrape, the system **must** continue with remaining categories.

**FR-7.2:** The system **must** implement retry logic (configurable, default 2 retries) for failed categories.

**FR-7.3:** The system **must** wait a configurable amount of time between retry attempts (default 5 seconds).

**FR-7.4:** The system **must** generate a user-friendly summary report at the end showing:

- Successfully scraped categories with entry counts (e.g., "✅ Educational: 45 opportunities found")
- Failed categories with simple error messages (e.g., "❌ Graphics Design: Failed - Network timeout")
- Total entries collected across all categories (e.g., "📊 Total: 127 opportunities collected")
- Total entries in final merged file after deduplication (e.g., "📄 Final file: 120 unique opportunities")
- Number of duplicate entries removed (e.g., "🔄 Removed 7 duplicate entries")

**FR-7.5:** The system **must** save the summary report to a text file alongside the output CSV.

### 8. Configuration File Support

**FR-8.1:** The system **must** support a JSON configuration file format.

**FR-8.2:** The configuration file **must** allow defining:

- Category selections (by name or ID)
- Output file path for merged CSV
- Output file path for cleaned CSV
- Retry count
- Delay between requests
- Maximum pages per category
- Whether to skip cleaning step

**FR-8.3:** Command-line arguments **must** override configuration file settings when both are provided.

**FR-8.4:** The system **must** provide an example configuration file template (`categories_config.json`).

### 9. Command-Line Interface

**FR-9.1:** The system **must** maintain backward compatibility with existing CLI arguments from `final_working_scraper.py`:

- `--limit`: Number of detail pages to scrape (0 for all)
- `--output`: Output CSV filepath
- `--delay`: Seconds to sleep between detail requests

**FR-9.2:** New CLI arguments **must** include:

- `--categories`: Comma-separated list of category names or IDs
- `--config`: Path to configuration file
- `--no-clean`: Skip automatic data cleaning step
- `--retry-count`: Number of retry attempts for failed categories (default: 2)
- `--merged-output`: Output file for merged (pre-cleaned) CSV
- `--final-output`: Output file for final cleaned CSV

**FR-9.3:** The system **must** display comprehensive help text with simple examples when `--help` is used, written for non-programmers.

**FR-9.4:** The system **must** validate all argument values and display clear, helpful error messages for invalid inputs in plain English.

**FR-9.5:** The system **must** provide an interactive mode when run without arguments, guiding users through category selection step-by-step.

**FR-9.6:** The system **must** include a `--simple` or `--guided` mode that provides maximum assistance for non-technical users.

## Non-Goals (Out of Scope)

The following are explicitly **not** included in this enhancement:

1. Auto-discovery of all available PhilGEPS categories beyond the seven predefined ones
2. GUI interface for category selection
3. Real-time progress dashboard or web interface
4. Database storage (CSV output only)
5. Parallel/concurrent scraping of multiple categories
6. Custom category definitions beyond the seven predefined categories
7. Scheduling or automated periodic scraping
8. Email notifications or alerts
9. Data visualization or reporting features
10. API endpoint creation

## Design Considerations

### User Interface

- Command-line interface should be intuitive for **non-programmers** and junior developers
- Progress messages should be clear, friendly, and informative with plain English
- Error messages should be actionable and written in simple terms (tell user exactly what to do)
- Summary report should be easy to read and understand for business users
- All prompts and help text should avoid technical jargon

### File Structure

```
/tasks/                          # PRD and task documentation
/final_working_scraper.py        # Modified to accept category URL
/multi_category_scraper.py       # NEW: Main orchestrator
/data_cleaner.py                 # Existing (no changes needed)
/categories_config.json          # NEW: Example config template
/output/                         # Directory for output files
  /raw/                          # Intermediate per-category CSVs
  /merged/                       # Merged CSV before cleaning
  /cleaned/                      # Final cleaned CSV
  /reports/                      # Summary reports
```

## Technical Considerations

### Architecture

**1. Refactor `final_working_scraper.py`:**

- Modify `collect_detail_links()` to accept a `category_url` parameter
- Ensure `parse_detail()` function remains unchanged
- Add category configuration constants at module level

**2. Create `multi_category_scraper.py`:**

- Main orchestrator that imports functions from `final_working_scraper.py`
- Handles CLI argument parsing
- Manages configuration file loading
- Orchestrates category selection and scraping
- Implements CSV merging with deduplication
- Invokes data cleaner
- Generates summary report

**3. Category Configuration Structure:**

```python
PREDEFINED_CATEGORIES = {
    28: {
        "name": "Packaging Supplies",
        "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=28&type=category&ClickFrom=OpenOpp"
    },
    29: {
        "name": "Printing Services",
        "url": "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&BusCatID=29&type=category&ClickFrom=OpenOpp"
    },
    # ... other categories
}
```

### Integration Points

- **Import from `data_cleaner.py`:** `PhilGEPSDataCleaner` class
- **Import from `final_working_scraper.py`:** `collect_detail_links()`, `parse_detail()`, session objects
- **Use pandas** for reliable CSV merging and deduplication
- **Use JSON** for configuration file parsing

### Dependencies

**Existing:**

- playwright
- beautifulsoup4
- requests
- pandas (already used in data_cleaner.py)

**New:**

- None (all required libraries already present)

### Error Handling Strategy

1. **Network errors:** Retry with exponential backoff
2. **Invalid categories:** Fail fast with clear error message
3. **Scraping failures:** Log error, continue with next category
4. **Merging failures:** Critical error, abort with detailed message
5. **Cleaning failures:** Optional (can skip with `--no-clean`)

## Success Metrics

The feature will be considered successful when:

1. ✅ Users can successfully scrape 2+ categories in one execution
2. ✅ Merged CSV contains deduplicated entries from all selected categories
3. ✅ Final output is automatically cleaned with proper date and currency formatting
4. ✅ System successfully recovers from single category failures without losing data
5. ✅ Zero data loss compared to running scraper separately for each category and manually merging
6. ✅ Summary report accurately reflects scraping results and any errors
7. ✅ Configuration file method works as reliably as command-line method

## Non-Programmer User Experience

### Interactive Mode Design

**When users run the script without arguments:**

```
Welcome to PhilGEPS Multi-Category Scraper! 📋

This tool will help you collect procurement opportunities from multiple categories.

Available categories:
1. Packaging Supplies
2. Printing Services
3. Printing Supplies
4. Graphics Design
5. Corporate Giveaways
6. Tokens
7. Educational

Please select categories (enter numbers separated by commas, or 'all' for all categories):
>
```

**Progress Messages:**

```
📋 Starting to scrape: Educational Services
⏳ Processing page 3 of 15...
✅ Found 23 opportunities so far...
⏱️  Estimated time remaining: 5 minutes
```

**Error Messages:**

```
❌ Sorry, 'Education' is not a valid category name.
💡 Did you mean 'Educational'?
📝 Available options: Packaging Supplies, Printing Services, Printing Supplies, Graphics Design, Corporate Giveaways, Tokens, Educational
```

**Success Summary:**

```
🎉 Scraping completed successfully!

📊 Results Summary:
✅ Educational: 45 opportunities found
✅ Tokens: 32 opportunities found
❌ Graphics Design: Failed - Network timeout (will retry)
📄 Final file: 77 unique opportunities saved to 'philgeps_merged_cleaned.csv'
🔄 Removed 0 duplicate entries

📁 Files created:
- philgeps_merged_cleaned.csv (final results)
- scraping_summary.txt (detailed report)
```

## Open Questions

1. **Dry-run mode:** Should there be a `--dry-run` flag to preview what would be scraped without actually scraping?

   - _Recommendation:_ Yes, add in future enhancement

2. **Progress bars:** Do you want progress bars for better UX during long scraping sessions?

   - _Recommendation:_ Use simple text-based progress (e.g., "Processing page 5/20") to avoid new dependencies

3. **Intermediate files:** Should intermediate per-category CSV files be saved or only the final merged file?

   - _Recommendation:_ Save intermediate files to prevent data loss and allow inspection

4. **Default behavior:** What should happen if no categories are specified (scrape all seven, or prompt user)?

   - _Recommendation:_ Prompt user with numbered list for better UX

5. **Retry delay:** Should retry delay increase exponentially or remain constant?
   - _Recommendation:_ Constant delay (5 seconds) to keep logic simple

---

## Document Metadata

- **Version:** 1.0
- **Created:** October 21, 2025
- **Author:** Product Requirements Team
- **Target Audience:** Junior to Mid-level Python Developers
- **Estimated Effort:** 2-3 days development + 1 day testing
- **Priority:** High
