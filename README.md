# Python Web Crawler

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)

A high-performance, configurable web crawler for mirroring websites with parallel processing, intelligent link conversion, SQLite database tracking, and automatic dependency management.

## 🚀 Features

- **🌐 Universal Web Crawling**: Works with any website (Confluence, documentation sites, wikis, etc.)
- **⚡ Parallel Processing**: Configurable multi-threaded downloads for maximum speed
- **📝 Multiple Output Formats**: HTML and Markdown with intelligent content extraction
- **🔗 Smart Link Conversion**: Converts web links to local file references automatically
- **🎨 Resource Management**: Downloads and organizes CSS, images, and other assets
- **� SQLite Database**: Robust progress tracking with atomic operations and concurrent access
- **📊 Advanced Reporting**: Comprehensive statistics and progress tracking
- **🔄 Auto-Migration**: Seamless migration from JSON to SQLite format
- **📦 Auto-Dependencies**: Automatic package installation without user intervention
- **🛡️ Thread-Safe**: Advanced locking mechanisms prevent race conditions
- **⚙️ Highly Configurable**: YAML configuration files + command-line interface
- **🍪 Cookie Authentication**: Support for authenticated sessions

## 🏗️ Architecture

```
PythonHttpTracker/
├── src/
│   ├── web_crawler.py         # Main crawler engine with SQLite integration
│   ├── database_manager.py    # SQLite database operations and management
│   ├── dependency_installer.py # Automatic dependency installation
│   ├── json_migrator.py       # Migration utility from JSON to SQLite
│   └── db_reporter.py         # Database reporting and statistics
├── config/
│   ├── config.yml.example    # Configuration template with database settings
│   └── cookies.template.txt  # Cookie template
├── setup_wizard.sh           # Interactive setup wizard
└── README.md                 # This documentation
```

### Core Components

1. **WebCrawler Class**: Main crawler engine with SQLite database integration
2. **DatabaseManager**: Complete SQLite abstraction with thread-safe operations
3. **DependencyInstaller**: Automatic installation of required Python packages
4. **JSONMigrator**: Migration utility for existing JSON progress files
5. **CrawlerReporter**: Advanced reporting and statistics generation
6. **Configuration System**: YAML-based configuration with database settings
7. **Link Processing**: Intelligent link extraction and local path conversion
8. **Resource Management**: Shared resource handling with deduplication

## 📦 Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### 🚀 Quick Start (Recommended)

1. **Clone the repository**:
```bash
git clone https://github.com/sjseo298/PythonHttpTracker.git
cd PythonHttpTracker
```

2. **Automatic Installation**:
```bash
python install.py
```

This intelligent installer will:
- ✅ Detect your environment (Dev Container, Codespace, local, etc.)
- ✅ Set up virtual environment (if needed)
- ✅ Install all required dependencies automatically
- ✅ Handle externally managed environments
- ✅ Verify installation completeness

### 🛠️ Alternative Installation Methods

#### Option 1: Interactive Setup Wizard
```bash
./setup_wizard.sh
```

The wizard guides you through:
- Installing dependencies automatically
- Creating configuration files
- Setting up authentication
- Running your first crawl

#### Option 2: Manual Installation
```bash
# Install dependencies from requirements.txt
pip install -r requirements.txt

# Or install individually
pip install requests>=2.25.0 beautifulsoup4>=4.9.0 markdownify>=0.11.0 PyYAML>=6.0 rich>=13.0.0
```

#### Option 3: Using Dependency Auto-Installer
```bash
# The crawler will automatically install missing dependencies when run
python src/web_crawler.py
```

### 📋 Next Steps

4. **Configure your target website**:
```bash
cp config/config.yml.example config/config.yml
# Edit config.yml with your website details and database settings
```

5. **Set up authentication** (if needed):
```bash
cp config/cookies.template.txt config/cookies.txt
# Add your authentication cookies to cookies.txt
```

6. **Run the crawler**:
```bash
python src/web_crawler.py
```

The crawler will automatically:
- Install missing dependencies
- Create SQLite database
- Migrate existing JSON progress files
- Start crawling with robust progress tracking

## ⚙️ Configuration

### YAML Configuration File

Create your configuration from the example template:

```bash
cp config/config.yml.example config/config.yml
# Edit config.yml with your website details and database settings
```

#### Key Configuration Sections:

- **Website**: Target site URL patterns and exclusions
- **Crawling**: Depth limits, workers, delays, and retry settings
- **Database**: SQLite settings, migration options, and performance tuning
- **Output**: Format selection (HTML/Markdown) and directory structure
- **Content**: Processing rules for HTML cleaning and resource handling
- **Files**: Cookie authentication and backup settings

#### Database Configuration

The crawler now uses SQLite for robust progress tracking:

```yaml
database:
  db_path: "crawler_data.db"          # SQLite database file
  auto_migrate_json: true             # Auto-migrate from JSON files
  json_backup_dir: "json_backups"     # Backup directory for JSON files
  keep_json_backup: true              # Keep JSON files after migration
  enable_wal_mode: true               # Better concurrency
  cache_size: 10000                   # Performance optimization
```

## 🗄️ Database Features

### SQLite Integration

The crawler uses SQLite for reliable progress tracking with these benefits:

- **Atomic Operations**: No data corruption from interruptions
- **Concurrent Access**: Thread-safe operations with proper locking
- **Efficient Queries**: Fast lookups for URL status and statistics
- **Data Integrity**: Foreign key constraints and transaction safety
- **Backup Support**: JSON export functionality for data portability

### Database Schema

The SQLite database includes these tables:

1. **discovered_urls**: Track all discovered URLs with status and metadata
2. **downloaded_documents**: Store information about downloaded HTML files
3. **downloaded_resources**: Track CSS, images, and other resource files
4. **url_mappings**: Map original URLs to local file paths
5. **crawler_stats**: Store crawling statistics and metrics

### Automatic Migration

Existing users with JSON progress files get automatic migration:

- Seamless conversion from JSON to SQLite format
- Automatic backup of original JSON files
- Zero data loss during migration
- Continued operation without interruption

## 📊 Reporting and Statistics

### Database Reports

Generate comprehensive crawling reports:

```bash
# Full report with statistics and breakdowns
python src/db_reporter.py

# Summary report only
python src/db_reporter.py --summary

# Progress overview
python src/db_reporter.py --progress

# Export completed URLs
python src/db_reporter.py --export-urls completed_urls.txt
```

### Report Features

- **URL Status Summary**: Breakdown by pending, downloading, completed, failed
- **Download Statistics**: Document and resource counts with sizes
- **Resource Analysis**: Breakdown by file types (CSS, images, etc.)
- **Recent Activity**: Daily download activity tracking
- **Failed URLs**: Analysis of failed downloads with retry counts
- **Progress Tracking**: Real-time progress bars and percentages

The main configuration is done through `config/config.yml`:

```yaml
# Website Configuration
website:
  base_domain: "your-site.com"
  base_url: "https://your-site.com"
  start_url: "https://your-site.com/docs"
  valid_url_patterns:
    - "/docs/"
    - "/wiki/"
  exclude_patterns:
    - "/admin"
    - "/login"

# Crawling Parameters
crawling:
  max_depth: 2
  space_name: "DOCS"
  max_workers: 8
  request_delay: 0.5
  request_timeout: 30

# Output Configuration
output:
  format: "markdown"  # or "html"
  output_dir: "downloaded_content"
  resources_dir: "shared_resources"
```

### Command Line Interface

For quick usage, you can also use command-line arguments:

```bash
# Basic usage (automatic dependency installation)
python src/web_crawler.py "https://example.com/docs"

# Advanced usage with all parameters
python src/web_crawler.py "https://example.com/wiki" 3 WIKI markdown 10
#                          URL                      depth space format workers

# Generate database reports
python src/db_reporter.py                    # Full report
python src/db_reporter.py --summary          # Summary only
python src/db_reporter.py --progress         # Progress only

# Export URLs by status
python src/db_reporter.py --export-urls completed.txt --export-status completed
```

### Automatic Dependency Management

The crawler automatically installs missing dependencies:

```bash
# Just run the crawler - dependencies will be installed automatically
python src/web_crawler.py

# Or manually install if preferred
pip install requests beautifulsoup4 markdownify pyyaml
```

### Interactive Setup Wizard

For an easier setup experience, use the interactive wizard:

```bash
./setup_wizard.sh
```

The wizard provides:
- Dependency checking and installation
- Interactive YAML configuration creation
- Step-by-step website setup
- Authentication configuration
- Example configurations for common sites

### Cookie Authentication

1. Copy the template:
```bash
cp config/cookies.template.txt config/cookies.txt
```

2. Get your cookies:
   - Open your browser and login to the target website
   - Open Developer Tools (F12) → Network tab
   - Refresh the page and copy the Cookie header from any request
   - Paste the cookie string into `config/cookies.txt`

Example format:
```
sessionid=abc123; csrftoken=def456; auth_token=ghi789
```

## 🚀 Usage Examples

### Example 1: Confluence Site

```yaml
# config/config.yml
website:
  base_domain: "company.atlassian.net"
  base_url: "https://company.atlassian.net"
  start_url: "https://company.atlassian.net/wiki/spaces/DOCS/overview"
  valid_url_patterns:
    - "/wiki/spaces/DOCS/"
  exclude_patterns:
    - "action="
    - "/admin"

crawling:
  max_depth: 2
  max_workers: 5
  
output:
  format: "markdown"
```

### Example 2: Documentation Site

```yaml
# config/config.yml
website:
  base_domain: "docs.example.com"
  base_url: "https://docs.example.com"
  start_url: "https://docs.example.com/v1/"
  valid_url_patterns:
    - "/v1/"
  exclude_patterns:
    - "/api/"

crawling:
  max_depth: 3
  max_workers: 10

output:
  format: "html"
```

### Example 3: Command Line Usage

```bash
# Download Confluence space with 8 parallel workers
python src/web_crawler.py "https://company.atlassian.net/wiki/spaces/TEAM" 2 TEAM markdown 8

# Download documentation site to HTML
python src/web_crawler.py "https://docs.example.com" 1 DOCS html 5
```

## 📊 Performance & Monitoring

### Progress Tracking

The crawler automatically saves progress to `download_progress.json` and can resume interrupted downloads:

```bash
# If download is interrupted, simply re-run the same command
python src/web_crawler.py "https://example.com/docs"
# ✓ Progress loaded: 45 URLs already downloaded, 23 pending
```

### Performance Tuning

- **max_workers**: Higher values = faster downloads, but may overload the server
- **request_delay**: Delay between requests to be respectful to the server
- **request_timeout**: Timeout for individual requests

Recommended settings:
- Small sites: `max_workers: 3-5`
- Large sites: `max_workers: 8-15`
- Slow servers: `request_delay: 1.0`

## 🛡️ Thread Safety

The crawler implements advanced thread-safe mechanisms:

- **URL Locks**: Prevent multiple threads from downloading the same page
- **Resource Locks**: Prevent duplicate resource downloads
- **Progress Locks**: Ensure safe progress file updates
- **Queue Locks**: Thread-safe queue management

## 📝 Output Formats

### Markdown Output

- Clean, readable Markdown files
- Intelligent content extraction (removes navigation, headers, footers)
- Local link conversion
- Metadata headers with original URLs
- ATX-style headings

### HTML Output

- Clean HTML with JavaScript removed
- CSS and resources downloaded and linked locally
- Local link conversion maintained
- Original page structure preserved

## 🐛 Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Check if cookies are correctly formatted in `config/cookies.txt`
   - Ensure cookies are not expired
   - Verify you have access to the target URLs

2. **Permission Errors**:
   - Check if you have write permissions in the output directory
   - Ensure the user running the script can create directories

3. **Network Errors**:
   - Check internet connectivity
   - Verify the target website is accessible
   - Consider increasing `request_timeout`

4. **Memory Issues**:
   - Reduce `max_workers` for large sites
   - Increase system memory or use swap space

### Debug Mode

Enable verbose logging by setting:
```yaml
logging:
  verbose: true
  log_resources: true
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Commit your changes: `git commit -am 'Add feature'`
5. Push to the branch: `git push origin feature-name`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Links

- **Repository**: https://github.com/sjseo298/PythonHttpTracker
- **Issues**: https://github.com/sjseo298/PythonHttpTracker/issues
- **Documentation**: https://github.com/sjseo298/PythonHttpTracker/wiki

## 🏷️ Version History

- **v1.0.0** (December 2024): Initial release
  - ✨ High-performance web crawler with parallel processing
  - 🌐 Universal web crawling support (Confluence, documentation sites, wikis)
  - ⚡ Multi-threaded downloads with configurable workers
  - 📝 Multiple output formats (HTML and Markdown)
  - 🔗 Smart link conversion to local references
  - 🎨 Automatic resource management (CSS, images, assets)
  - 📊 Progress tracking and resume functionality
  - 🛡️ Thread-safe architecture with advanced locking
  - ⚙️ YAML configuration with CLI override support
  - 🍪 Cookie authentication for protected sites
  - 🧹 Integrated HTML cleaning and JavaScript removal
  - 📋 Interactive setup wizard

---

**Made with ❤️ for the web scraping community**
