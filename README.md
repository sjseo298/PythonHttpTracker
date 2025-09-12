# Python Web Crawler

A high-performance, configurable web crawler for mirroring websites with parallel processing, intelligent link conversion, and multiple output formats.

## 🚀 Features

- **🌐 Universal Web Crawling**: Works with any website (Confluence, documentation sites, wikis, etc.)
- **⚡ Parallel Processing**: Configurable multi-threaded downloads for maximum speed
- **📝 Multiple Output Formats**: HTML and Markdown with intelligent content extraction
- **🔗 Smart Link Conversion**: Converts web links to local file references automatically
- **🎨 Resource Management**: Downloads and organizes CSS, images, and other assets
- **📊 Progress Tracking**: Resume functionality for large crawling jobs
- **🛡️ Thread-Safe**: Advanced locking mechanisms prevent race conditions
- **⚙️ Highly Configurable**: YAML configuration files + command-line interface
- **🍪 Cookie Authentication**: Support for authenticated sessions

## 🏗️ Architecture

```
PythonHttpTracker/
├── src/
│   └── web_crawler.py       # Main crawler engine with integrated HTML cleaning
├── config/
│   ├── config.yml.example  # Configuration template
│   └── cookies.template.txt # Cookie template
├── setup_wizard.sh         # Interactive setup wizard
└── README.md               # This documentation
```

### Core Components

1. **WebCrawler Class**: Main crawler engine with parallel processing
2. **Configuration System**: YAML-based configuration with CLI override support
3. **Link Processing**: Intelligent link extraction and local path conversion
4. **Resource Management**: Shared resource handling with deduplication
5. **Content Processing**: HTML cleaning, JavaScript removal, and Markdown conversion

## 📦 Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Quick Start

1. **Clone the repository**:
```bash
git clone https://github.com/sjseo298/PythonHttpTracker.git
cd PythonHttpTracker
```

2. **Run the interactive setup wizard**:
```bash
./setup_wizard.sh
```

The wizard will guide you through:
- Installing dependencies
- Creating configuration files
- Setting up authentication
- Running your first crawl

**Alternatively, you can set up manually:**

3. **Install dependencies**:
```bash
pip install requests beautifulsoup4 markdownify pyyaml
```

4. **Configure your target website**:
```bash
cp config/config.yml.example config/config.yml
# Edit config.yml with your website details
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

## ⚙️ Configuration

### YAML Configuration File

Create your configuration from the example template:

```bash
cp config/config.yml.example config/config.yml
# Edit config.yml with your website details
```

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
# Basic usage
python src/web_crawler.py "https://example.com/docs"

# Advanced usage
python src/web_crawler.py "https://example.com/wiki" 3 WIKI markdown 10
#                          URL                      depth space format workers
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

- **v1.0.0**: Initial release with basic crawling
- **v2.0.0**: Added parallel processing and YAML configuration
- **v2.1.0**: Added Markdown support and resource management
- **v3.0.0**: Complete rewrite with universal web support

---

**Made with ❤️ for the web scraping community**
