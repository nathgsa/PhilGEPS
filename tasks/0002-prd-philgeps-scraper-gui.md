# Product Requirements Document: PhilGEPS Scraper GUI

## Introduction/Overview

This document outlines the requirements for creating a professional graphical user interface (GUI) for the PhilGEPS Multi-Category Scraper using CustomTkinter. The GUI will provide a user-friendly way for non-technical users to configure, run, and monitor the PhilGEPS scraping operations without using command-line interfaces.

**Problem:** The current PhilGEPS scraper requires technical knowledge to use (command-line, configuration files, understanding terminal output). Non-technical users cannot easily use the scraper.

**Solution:** Create a modern, intuitive desktop GUI that allows anyone to scrape PhilGEPS data with just a few clicks, monitor progress in real-time, and access results easily.

## Goals

1. Create an intuitive, beginner-friendly GUI for the PhilGEPS scraper
2. Support all existing scraper features (multi-category, configuration, data cleaning)
3. Provide real-time progress monitoring with visual feedback
4. Enable easy access to scraped data and reports
5. Work seamlessly on both Windows and macOS
6. Maintain compatibility with existing backend code (no modifications to original scraper logic)

## User Stories

1. **As a procurement analyst**, I want to select multiple categories with checkboxes so that I can easily choose what to scrape without typing category names.

2. **As a non-technical user**, I want to see real-time progress bars and status messages so that I know the scraper is working and when it will finish.

3. **As a researcher**, I want to configure scraping settings (delay, retry count, etc.) through input fields so that I can customize the scraper without editing configuration files.

4. **As a data consumer**, I want to view and open the scraped CSV files directly from the GUI so that I don't have to navigate through folders.

5. **As a Windows user**, I want the GUI to work the same way as it does on macOS so that I have a consistent experience.

6. **As a business user**, I want to save my preferred settings so that I don't have to reconfigure the scraper every time.

7. **As a user**, I want to see a summary of results (number of entries, success/failure by category) so that I know what data was collected.

8. **As a beginner**, I want helpful tooltips and clear error messages so that I understand what went wrong and how to fix it.

## Functional Requirements

### 1. Main Window Layout

**FR-1.1:** The GUI **must** use CustomTkinter framework for modern, cross-platform appearance.

**FR-1.2:** The main window **must** have a minimum size of 900x700 pixels with the ability to resize.

**FR-1.3:** The GUI **must** use a tabbed interface with the following tabs:
- "Scraper" - Main scraping interface
- "Configuration" - Advanced settings
- "Results" - View and manage output files
- "About" - Information and help

**FR-1.4:** The GUI **must** display the application name "PhilGEPS Scraper" and version number in the title bar.

**FR-1.5:** The GUI **must** use a modern color scheme (dark mode support recommended).

### 2. Category Selection (Scraper Tab)

**FR-2.1:** The GUI **must** display all 9 predefined categories as checkboxes:
- Packaging Supplies (28)
- Printing Services (29)
- Printing Supplies (51)
- Graphics Design (64)
- Corporate Giveaways (71)
- Tokens (129)
- Educational (134)
- General Merchandise (80)
- Reproduction Services (150)

**FR-2.2:** The GUI **must** provide a "Select All" button to check all categories at once.

**FR-2.3:** The GUI **must** provide a "Clear All" button to uncheck all categories.

**FR-2.4:** The GUI **must** display category names with their IDs in parentheses.

**FR-2.5:** The GUI **must** require at least one category to be selected before allowing scraping to start.

### 3. Basic Settings (Scraper Tab)

**FR-3.1:** The GUI **must** provide an input field for "Limit per category" (default: 0 for all).

**FR-3.2:** The GUI **must** provide an input field for "Delay between requests" (default: 0.5 seconds).

**FR-3.3:** The GUI **must** provide a checkbox for "Skip data cleaning" (default: unchecked).

**FR-3.4:** All input fields **must** validate user input and show error messages for invalid values.

### 4. Progress Monitoring (Scraper Tab)

**FR-4.1:** The GUI **must** display a main progress bar showing overall scraping progress.

**FR-4.2:** The GUI **must** display current status text showing which category is being scraped.

**FR-4.3:** The GUI **must** display a scrollable text area showing real-time log messages.

**FR-4.4:** The GUI **must** use color-coded messages:
- Green for success messages
- Yellow/Orange for warnings
- Red for errors
- Blue for informational messages

**FR-4.5:** The GUI **must** display estimated time remaining when possible.

**FR-4.6:** The GUI **must** show a summary of completed vs. total categories.

### 5. Control Buttons (Scraper Tab)

**FR-5.1:** The GUI **must** provide a "Start Scraping" button that:
- Validates all settings
- Disables itself when scraping is in progress
- Shows "Stop Scraping" when active

**FR-5.2:** The GUI **must** provide a "Stop Scraping" button to cancel operations.

**FR-5.3:** The GUI **must** provide a "Clear Log" button to clear the log text area.

**FR-5.4:** The GUI **must** provide an "Open Output Folder" button to open the output directory in file explorer.

### 6. Advanced Configuration (Configuration Tab)

**FR-6.1:** The GUI **must** provide input fields for:
- Retry count (default: 2)
- Max category workers (default: 2)
- Max detail workers (default: 5)
- Output directory path (with browse button)

**FR-6.2:** The GUI **must** provide a "Save Configuration" button to save settings to JSON file.

**FR-6.3:** The GUI **must** provide a "Load Configuration" button to load settings from JSON file.

**FR-6.4:** The GUI **must** provide a "Reset to Defaults" button to restore default settings.

**FR-6.5:** The GUI **must** auto-save the last used configuration on exit.

**FR-6.6:** The GUI **must** auto-load the last used configuration on startup.

### 7. Results Management (Results Tab)

**FR-7.1:** The GUI **must** display a list of all output files (raw, merged, cleaned) with:
- File name
- File size
- Number of rows (if CSV)
- Creation date/time
- Action buttons (Open, Delete, Export)

**FR-7.2:** The GUI **must** provide an "Open" button to open CSV files in the default spreadsheet application.

**FR-7.3:** The GUI **must** provide a "Delete" button with confirmation dialog to delete files.

**FR-7.4:** The GUI **must** provide a "Refresh" button to reload the file list.

**FR-7.5:** The GUI **must** display the most recent scraping summary report.

**FR-7.6:** The GUI **must** provide a "View Report" button to open the latest summary report.

### 8. Data Preview (Results Tab)

**FR-8.1:** The GUI **must** provide a data preview table showing the first 100 rows of selected CSV.

**FR-8.2:** The GUI **must** allow users to click on a file to preview its contents.

**FR-8.3:** The GUI **must** display total row count and column names for the selected file.

### 9. Error Handling

**FR-9.1:** The GUI **must** display user-friendly error messages in dialog boxes for:
- Missing dependencies
- Network connection issues
- Invalid configuration
- File access errors

**FR-9.2:** The GUI **must** log all errors to the log text area with timestamps.

**FR-9.3:** The GUI **must** prevent the application from crashing due to scraper errors.

**FR-9.4:** The GUI **must** provide a "Run Diagnostics" button to test PhilGEPS connection.

### 10. About/Help (About Tab)

**FR-10.1:** The GUI **must** display:
- Application version
- Brief description
- Original developer credits
- GUI developer credits
- Links to documentation

**FR-10.2:** The GUI **must** provide a "View Documentation" button to open README files.

**FR-10.3:** The GUI **must** provide a "Run System Check" button to verify dependencies.

**FR-10.4:** The GUI **must** display system information (OS, Python version, installed packages).

### 11. Threading and Responsiveness

**FR-11.1:** The GUI **must** run scraping operations in a separate thread to prevent UI freezing.

**FR-11.2:** The GUI **must** remain responsive during scraping operations.

**FR-11.3:** The GUI **must** allow cancellation of scraping operations.

**FR-11.4:** The GUI **must** properly clean up threads on application exit.

### 12. Cross-Platform Compatibility

**FR-12.1:** The GUI **must** work on both Windows and macOS without code changes.

**FR-12.2:** The GUI **must** automatically detect the platform and use appropriate file paths.

**FR-12.3:** The GUI **must** use platform-appropriate file dialogs.

**FR-12.4:** The GUI **must** import `windows_compat` module on Windows for encoding support.

## Non-Goals (Out of Scope)

The following are explicitly **not** included in this version:

1. Real-time data visualization or charts
2. Direct database integration
3. Scheduling/automation features
4. Email notifications
5. Multi-user support or user accounts
6. Cloud storage integration
7. Built-in data analysis tools
8. Export to formats other than CSV
9. Custom category creation (limited to predefined categories)
10. Network proxy configuration UI

## Design Considerations

### User Interface Design

- **Modern appearance**: Use CustomTkinter's built-in styling
- **Intuitive layout**: Logical grouping of related controls
- **Visual hierarchy**: Clear primary and secondary actions
- **Consistent spacing**: Use padding and margins appropriately
- **Color coding**: Use colors to indicate status (success, warning, error)
- **Icons**: Use simple icons where appropriate (optional, text is fine)

### Usability Principles

- **Progressive disclosure**: Basic options visible, advanced options in Configuration tab
- **Feedback**: Always show user what's happening (progress, status, messages)
- **Error prevention**: Validate inputs before starting operations
- **Clear language**: Use simple, non-technical language in UI
- **Help available**: Tooltips and help text where needed

### File Structure

```
scraper_gui.py              # Main GUI application file
├── imports
├── GUI class definition
├── Tab implementations
│   ├── Scraper tab
│   ├── Configuration tab
│   ├── Results tab
│   └── About tab
├── Helper methods
├── Threading implementation
└── Main entry point
```

## Technical Considerations

### Dependencies

**Required:**
- customtkinter (GUI framework)
- tkinter (standard library, base for CustomTkinter)
- threading (standard library, for background operations)
- json (standard library, for configuration)
- pathlib (standard library, for cross-platform paths)

**Existing:**
- All current scraper dependencies (playwright, pandas, requests, etc.)

### Integration with Existing Code

**Pattern:**
```python
# Import Windows compatibility first (on Windows)
import windows_compat

# Import scraper components
from multi_category_scraper import MultiCategoryScraper
from data_cleaner import PhilGEPSDataCleaner

# Run scraper in separate thread
def run_scraper_thread():
    scraper = MultiCategoryScraper()
    # Configure and run...
```

### Threading Strategy

- **Main thread**: GUI event loop (always responsive)
- **Worker thread**: Scraping operations (can be cancelled)
- **Communication**: Queue or callback for progress updates
- **Safety**: Thread-safe access to shared resources

### Configuration Management

```json
{
  "last_categories": [29, 134, 129],
  "limit": 0,
  "delay": 0.5,
  "retry_count": 2,
  "skip_cleaning": false,
  "max_category_workers": 2,
  "max_detail_workers": 5,
  "output_dir": "output",
  "window_geometry": "900x700+100+100"
}
```

### Error Handling Strategy

1. **Input validation**: Check all inputs before starting
2. **Try-catch blocks**: Wrap all operations in exception handlers
3. **User-friendly messages**: Convert technical errors to plain English
4. **Logging**: Log all errors for debugging
5. **Graceful degradation**: Continue operation if possible, fail safely if not

## Success Metrics

The GUI will be considered successful when:

1. ✅ Non-technical users can successfully scrape data without command-line knowledge
2. ✅ All scraper features are accessible through the GUI
3. ✅ Progress updates are visible and accurate
4. ✅ Application works on both Windows and macOS
5. ✅ No crashes or freezing during normal operations
6. ✅ Error messages are clear and actionable
7. ✅ Configuration can be saved and reloaded
8. ✅ Results are easily accessible and viewable

## Open Questions

1. **Icon design**: Should we include custom application icon, or use default?
   - _Recommendation:_ Start without custom icon, add later if needed

2. **Theme selection**: Should users be able to switch between light/dark themes?
   - _Recommendation:_ Provide theme toggle in Configuration tab

3. **Update checking**: Should the GUI check for updates?
   - _Recommendation:_ No, out of scope for v1.0

4. **Installation**: Should we create a standalone executable (e.g., using PyInstaller)?
   - _Recommendation:_ Future enhancement, provide Python script first

5. **Logging level**: Should users be able to adjust logging verbosity?
   - _Recommendation:_ Yes, add in Configuration tab (DEBUG, INFO, WARNING, ERROR)

---

## Document Metadata

- **Version:** 1.0
- **Created:** February 11, 2026
- **Author:** AI Development Team
- **Target Audience:** Python developers familiar with CustomTkinter
- **Estimated Effort:** 2-3 days development + 1 day testing
- **Priority:** High
- **Platform:** Windows & macOS
