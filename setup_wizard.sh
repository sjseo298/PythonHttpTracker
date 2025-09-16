#!/bin/bash

# ============================================================================
# Python Web Crawler - Interactive Setup & Management Wizard
# ============================================================================
# This interactive wizard helps you:
# - Set up and configure the Python Web Crawler
# - Create custom YAML configurations through guided questions
# - Run examples and test different website types
# - Manage downloads and view statistics
# - Clean up and maintain your crawler installations

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_section() {
    echo -e "\n${BLUE}============================================================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}============================================================================${NC}\n"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to run Python with virtual environment if available
run_python() {
    if [ -f ".venv/bin/python" ]; then
        .venv/bin/python "$@"
    else
        python3 "$@"
    fi
}

# Check if Python is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    print_info "Python 3 found: $(python3 --version)"
}

# Check if required packages are installed
check_dependencies() {
    print_info "Checking Python dependencies..."
    
    packages=("requests" "beautifulsoup4" "markdownify" "pyyaml" "rich")
    
    # Check if virtual environment exists
    if [ ! -d ".venv" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv .venv
    fi
    
    # Activate virtual environment and check packages
    source .venv/bin/activate
    
    for package in "${packages[@]}"; do
        package_name=${package//-/_}
        if python -c "import ${package_name}" 2>/dev/null; then
            print_info "✓ $package is installed"
        else
            print_warning "✗ $package is not installed"
            print_info "Installing $package..."
            pip install "$package"
        fi
    done
    
    print_info "✓ All dependencies are ready"
}

# Setup configuration
setup_config() {
    print_section "Setting up configuration"
    
    if [ ! -f "config/config.yml" ]; then
        if [ -f "config/config.yml.example" ]; then
            print_info "Configuration file not found."
            echo "Options:"
            echo "  1) Copy example configuration (manual edit required)"
            echo "  2) Use interactive wizard to create configuration"
            
            read -p "Choose option [1-2]: " config_option
            case $config_option in
                2)
                    create_yaml_config
                    return
                    ;;
                *)
                    print_info "Copying example configuration..."
                    cp config/config.yml.example config/config.yml
                    print_warning "Please edit config/config.yml with your website details"
                    ;;
            esac
        else
            print_error "No configuration template found"
            exit 1
        fi
    else
        print_info "Configuration file already exists"
    fi
    
    # Handle cookies setup
    if [ ! -f "config/cookies.txt" ]; then
        if [ -f "config/cookies.template.txt" ]; then
            print_info "Cookie file not found."
            
            read -p "Do you need authentication cookies? (y/N): " needs_cookies
            if [[ $needs_cookies =~ ^[Yy]$ ]]; then
                cp config/cookies.template.txt config/cookies.txt
                print_info "✓ Created config/cookies.txt from template"
                print_warning "Please configure your authentication cookies in config/cookies.txt"
                
                read -p "Do you want to configure cookies now? (Y/n): " configure_now
                if [[ ! $configure_now =~ ^[Nn]$ ]]; then
                    print_info "Please enter your cookie string (from browser Developer Tools):"
                    print_info "Note: Press Ctrl+V to paste, then press Enter when done"
                    echo -n "Cookies: "
                    read -r cookie_string
                    if [ -n "$cookie_string" ]; then
                        # Remove any leading/trailing whitespace and save to file
                        echo "$cookie_string" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' > config/cookies.txt
                        print_info "✓ Cookies configured successfully"
                        print_info "✓ Saved $(wc -c < config/cookies.txt) characters"
                    fi
                fi
            else
                print_info "Skipping cookie configuration (anonymous access)"
            fi
        fi
    else
        print_info "Cookie file already exists"
    fi
}

# Configure cookies interactively
configure_cookies() {
    print_section "Cookie Configuration"
    
    print_info "Cookie configuration options:"
    echo "  1) Enter cookies manually (paste from browser)"
    echo "  2) Load cookies from a file"
    echo "  3) View current cookies"
    echo "  4) Clear cookies"
    echo "  0) Back to main menu"
    echo ""
    
    read -p "Choose an option [0-4]: " cookie_option
    
    case $cookie_option in
        1)
            print_info "Manual cookie entry:"
            print_info "1. Open your browser and login to your target website"
            print_info "2. Open Developer Tools (F12) → Network tab"
            print_info "3. Refresh the page and find any request"
            print_info "4. Copy the 'Cookie' header value"
            print_info "5. Paste it below (press Enter when done)"
            echo ""
            echo -n "Enter cookies: "
            
            # Use a more robust method to read cookies
            IFS= read -r cookie_string
            
            if [ -n "$cookie_string" ]; then
                # Clean up the cookie string and save
                echo "$cookie_string" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' > config/cookies.txt
                print_info "✓ Cookies saved to config/cookies.txt"
                print_info "✓ Saved $(wc -c < config/cookies.txt) characters"
                
                # Show first 100 characters for verification
                echo "First 100 characters: $(head -c 100 config/cookies.txt)..."
            else
                print_warning "No cookies provided"
            fi
            ;;
        2)
            read -p "Enter path to cookie file: " cookie_file
            if [ -f "$cookie_file" ]; then
                cp "$cookie_file" config/cookies.txt
                print_info "✓ Cookies loaded from $cookie_file"
            else
                print_error "File not found: $cookie_file"
            fi
            ;;
        3)
            if [ -f "config/cookies.txt" ]; then
                echo "Current cookies (first 200 characters):"
                head -c 200 config/cookies.txt
                echo "..."
                echo ""
                echo "Total size: $(wc -c < config/cookies.txt) characters"
            else
                print_warning "No cookies file found"
            fi
            ;;
        4)
            if [ -f "config/cookies.txt" ]; then
                rm config/cookies.txt
                print_info "✓ Cookies cleared"
            else
                print_warning "No cookies file to clear"
            fi
            ;;
        0)
            return
            ;;
        *)
            print_error "Invalid option"
            ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
}

# ============================================================================
# EXAMPLE USAGE FUNCTIONS
# ============================================================================

# Example 1: Confluence Documentation
example_confluence() {
    print_section "Example 1: Confluence Documentation Site"
    
    print_info "This example shows how to download a Confluence space"
    print_info "Configuration:"
    echo "  - URL: https://company.atlassian.net/wiki/spaces/DOCS"
    echo "  - Format: Markdown"
    echo "  - Max Depth: 2"
    echo "  - Workers: 5"
    
    read -p "Do you want to run this example? (y/N): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_python src/web_crawler.py \
            "https://company.atlassian.net/wiki/spaces/DOCS/overview" \
            2 \
            DOCS \
            markdown \
            5
    fi
}

# Example 2: Documentation Site
example_docs() {
    print_section "Example 2: Documentation Site"
    
    print_info "This example shows how to download a documentation site"
    print_info "Configuration:"
    echo "  - URL: https://docs.python.org/3/"
    echo "  - Format: HTML"
    echo "  - Max Depth: 1"
    echo "  - Workers: 3"
    
    read -p "Do you want to run this example? (y/N): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_python src/web_crawler.py \
            "https://docs.python.org/3/" \
            1 \
            PYTHON_DOCS \
            html \
            3
    fi
}

# Example 3: Using YAML Configuration
example_yaml() {
    print_section "Example 3: Using YAML Configuration"
    
    print_info "This example shows how to use YAML configuration"
    print_info "Make sure you have configured config/config.yml first"
    
    if [ ! -f "config/config.yml" ]; then
        print_error "No config.yml found. Please set up configuration first."
        return 1
    fi
    
    read -p "Do you want to run with YAML configuration? (Y/n): " -r
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        run_python src/web_crawler.py
    fi
}

# Example 4: GitBook Style Site
example_gitbook() {
    print_section "Example 4: GitBook Style Documentation"
    
    print_info "This example shows how to download GitBook-style documentation"
    print_info "Configuration:"
    echo "  - URL: https://developer.mozilla.org/en-US/docs/Web"
    echo "  - Format: Markdown"
    echo "  - Max Depth: 2"
    echo "  - Workers: 8"
    
    read -p "Do you want to run this example? (y/N): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_python src/web_crawler.py \
            "https://developer.mozilla.org/en-US/docs/Web" \
            2 \
            MDN_WEB \
            markdown \
            8
    fi
}

# Example 5: Large Site with Resume
example_large_site() {
    print_section "Example 5: Large Site with Resume Capability"
    
    print_info "This example shows how to handle large sites with resume functionality"
    print_info "The crawler will save progress and can be resumed if interrupted"
    print_info "Configuration:"
    echo "  - URL: https://en.wikipedia.org/wiki/Python_(programming_language)"
    echo "  - Format: Markdown"
    echo "  - Max Depth: 1"
    echo "  - Workers: 10"
    
    print_warning "This may download many files. You can interrupt with Ctrl+C and resume later."
    
    read -p "Do you want to run this example? (y/N): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_python src/web_crawler.py \
            "https://en.wikipedia.org/wiki/Python_(programming_language)" \
            1 \
            WIKIPEDIA \
            markdown \
            10
    fi
}

# Custom configuration
custom_crawler() {
    print_section "Custom Crawler Configuration"
    
    print_info "Enter your custom configuration:"
    
    read -p "Enter the starting URL: " start_url
    read -p "Enter maximum depth (default: 2): " max_depth
    max_depth=${max_depth:-2}
    
    read -p "Enter space name (default: CUSTOM): " space_name
    space_name=${space_name:-CUSTOM}
    
    read -p "Enter output format (html/markdown, default: markdown): " format
    format=${format:-markdown}
    
    read -p "Enter number of workers (default: 5): " workers
    workers=${workers:-5}
    
    print_info "Running crawler with configuration:"
    echo "  - URL: $start_url"
    echo "  - Depth: $max_depth"
    echo "  - Space: $space_name"
    echo "  - Format: $format"
    echo "  - Workers: $workers"
    
    run_python src/web_crawler.py "$start_url" "$max_depth" "$space_name" "$format" "$workers"
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

# Clean previous downloads
clean_downloads() {
    print_section "Cleaning Previous Downloads"
    
    print_warning "This will remove all downloaded content and progress files"
    read -p "Are you sure you want to continue? (y/N): " -r
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf downloaded_content/
        rm -rf shared_resources/
        rm -f download_progress.json
        print_info "Cleaned up previous downloads"
    fi
}

# Show download statistics
show_stats() {
    print_section "Download Statistics"
    
    if [ -f "download_progress.json" ]; then
        print_info "Progress file found, analyzing..."
        
        # Count completed downloads
        completed=$(run_python -c "
import json
try:
    with open('download_progress.json', 'r') as f:
        data = json.load(f)
    print(f'Completed URLs: {len(data.get(\"completed_urls\", []))}')
    print(f'Pending URLs: {len(data.get(\"url_queue\", []))}')
    print(f'Downloaded Resources: {len(data.get(\"downloaded_resources\", []))}')
except Exception as e:
    print(f'Error reading progress file: {e}')
")
        echo "$completed"
    else
        print_info "No progress file found"
    fi
    
    if [ -d "downloaded_content" ]; then
        print_info "Content directory statistics:"
        echo "  - Total files: $(find downloaded_content -type f | wc -l)"
        echo "  - Total size: $(du -sh downloaded_content 2>/dev/null | cut -f1)"
    fi
    
    if [ -d "shared_resources" ]; then
        print_info "Resources directory statistics:"
        echo "  - Total resources: $(find shared_resources -type f | wc -l)"
        echo "  - Total size: $(du -sh shared_resources 2>/dev/null | cut -f1)"
    fi
}

# Interactive YAML configuration generator
create_yaml_config() {
    print_section "Interactive YAML Configuration Generator"
    
    print_info "This wizard will help you create a custom config.yml file"
    print_info "Press Enter for default values shown in [brackets]"
    echo ""
    print_info "How URL patterns work:"
    echo "  - Patterns are substrings that must be contained in URLs"
    echo "  - Example: '/wiki/spaces/AR/' will match any URL containing that text"
    echo "  - This includes all sub-pages like '/wiki/spaces/AR/pages/123/something'"
    echo "  - Be specific to avoid downloading unwanted content"
    echo ""
    
    # Website Configuration
    print_info "=== Website Configuration ==="
    
    read -p "Enter the starting URL: " start_url
    while [ -z "$start_url" ]; do
        print_error "Starting URL is required!"
        read -p "Enter the starting URL: " start_url
    done
    
    # Extract domain from URL
    base_domain=$(echo "$start_url" | sed -E 's|https?://([^/]+).*|\1|')
    base_url=$(echo "$start_url" | sed -E 's|(https?://[^/]+).*|\1|')
    
    echo "Detected domain: $base_domain"
    echo "Detected base URL: $base_url"
    
    read -p "Is this correct? (Y/n): " -r
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        read -p "Enter the base domain: " base_domain
        read -p "Enter the base URL: " base_url
    fi
    
    echo ""
    print_info "=== URL Patterns ==="
    print_info "Define which URL patterns should be crawled"
    print_info "Examples: /docs/, /wiki/spaces/AR/, /api/v1/"
    print_info "The crawler will match URLs that contain these patterns"
    echo ""
    
    valid_patterns=()
    while true; do
        read -p "Valid URL pattern (empty line to finish): " pattern
        if [ -z "$pattern" ]; then
            break
        fi
        
        # Auto-suggest related patterns
        if [[ "$pattern" == */spaces/* ]]; then
            print_info "Added pattern: $pattern"
            valid_patterns+=("$pattern")
            
            # Suggest including sub-pages
            read -p "Also include all sub-pages under this space? (Y/n): " include_sub
            if [[ ! $include_sub =~ ^[Nn]$ ]]; then
                if [[ "$pattern" != */* ]]; then
                    pattern="$pattern/"
                fi
                if [[ "$pattern" != */pages/* ]]; then
                    sub_pattern="${pattern}pages/"
                    print_info "Added pattern: $sub_pattern (for sub-pages)"
                    valid_patterns+=("$sub_pattern")
                fi
            fi
            
        elif [[ "$pattern" == */docs/* ]] || [[ "$pattern" == */wiki/* ]]; then
            print_info "Added pattern: $pattern"
            valid_patterns+=("$pattern")
            
            # Suggest including sub-sections
            read -p "Include all sub-sections under this path? (Y/n): " include_sub
            if [[ ! $include_sub =~ ^[Nn]$ ]]; then
                if [[ "$pattern" != */ ]]; then
                    pattern="$pattern/"
                fi
                print_info "This will match all URLs containing: $pattern"
            fi
            
        else
            print_info "Added pattern: $pattern"
            valid_patterns+=("$pattern")
            
            # For any other pattern, ask if they want to include sub-paths
            if [[ "$pattern" == */ ]] || [[ "$pattern" == */* ]]; then
                read -p "Include all sub-paths under '$pattern'? (Y/n): " include_sub
                if [[ ! $include_sub =~ ^[Nn]$ ]]; then
                    print_info "This will match all URLs containing: $pattern"
                fi
            fi
        fi
        
        echo ""
    done
    
    if [ ${#valid_patterns[@]} -eq 0 ]; then
        print_warning "No patterns specified, using default based on start URL"
        path_part=$(echo "$start_url" | sed -E 's|https?://[^/]+(/[^?#]*)?.*|\1|')
        if [ "$path_part" != "/" ] && [ -n "$path_part" ]; then
            valid_patterns+=("$path_part")
        else
            valid_patterns+=("/")
        fi
    fi
    
    echo ""
    print_info "=== Exclude Patterns ==="
    print_info "Define URL patterns to exclude (one per line, empty line to finish)"
    
    exclude_patterns=()
    while true; do
        read -p "Exclude pattern (e.g., /admin, /login): " pattern
        if [ -z "$pattern" ]; then
            break
        fi
        exclude_patterns+=("$pattern")
        print_info "Added exclude pattern: $pattern"
    done
    
    # Add common exclude patterns if none specified
    if [ ${#exclude_patterns[@]} -eq 0 ]; then
        exclude_patterns=("/admin" "/login" "/logout" "action=" "?delete")
    fi
    
    echo ""
    print_info "=== Crawling Parameters ==="
    
    read -p "Maximum crawling depth [2]: " max_depth
    max_depth=${max_depth:-2}
    
    read -p "Space/section name [DOCS]: " space_name
    space_name=${space_name:-DOCS}
    
    read -p "Number of parallel workers [8]: " max_workers
    max_workers=${max_workers:-8}
    
    read -p "Delay between requests in seconds [0.5]: " request_delay
    request_delay=${request_delay:-0.5}
    
    read -p "Request timeout in seconds [30]: " request_timeout
    request_timeout=${request_timeout:-30}
    
    echo ""
    print_info "=== Output Configuration ==="
    
    read -p "Output format (html/markdown) [markdown]: " output_format
    output_format=${output_format:-markdown}
    
    read -p "Output directory [downloaded_content]: " output_dir
    output_dir=${output_dir:-downloaded_content}
    
    read -p "Resources directory [shared_resources]: " resources_dir
    resources_dir=${resources_dir:-shared_resources}
    
    echo ""
    print_info "=== Authentication Configuration ==="
    
    read -p "Does this website require authentication (cookies)? (y/N): " needs_auth
    if [[ $needs_auth =~ ^[Yy]$ ]]; then
        print_info "Setting up cookie authentication..."
        
        # Create cookies file from template
        if [ ! -f "config/cookies.txt" ]; then
            if [ -f "config/cookies.template.txt" ]; then
                cp config/cookies.template.txt config/cookies.txt
                print_info "✓ Created config/cookies.txt from template"
            fi
        fi
        
        print_info "Cookie setup instructions:"
        echo "  1. Open your browser and login to: $base_domain"
        echo "  2. Open Developer Tools (F12) → Network tab"
        echo "  3. Refresh the page and find any request to $base_domain"
        echo "  4. Copy the 'Cookie' header value"
        echo "  5. Paste it into config/cookies.txt (replace the template content)"
        echo ""
        
        read -p "Do you want to configure cookies now? (Y/n): " configure_cookies
        if [[ ! $configure_cookies =~ ^[Nn]$ ]]; then
            print_info "Please enter your cookie string (paste the Cookie header):"
            print_info "Note: Press Ctrl+V to paste, then press Enter when done"
            echo -n "Cookies: "
            read -r cookie_string
            
            if [ -n "$cookie_string" ]; then
                # Remove any leading/trailing whitespace and save to file
                echo "$cookie_string" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' > config/cookies.txt
                print_info "✓ Cookies saved to config/cookies.txt"
                print_info "✓ Saved $(wc -c < config/cookies.txt) characters"
            else
                print_warning "No cookies provided. You can configure them later in config/cookies.txt"
            fi
        else
            print_warning "Remember to configure config/cookies.txt before running the crawler"
        fi
    else
        print_info "No authentication required - using anonymous access"
    fi
    
    echo ""
    print_info "=== Advanced Options ==="
    
    read -p "Remove JavaScript from HTML? (Y/n): " remove_js
    if [[ $remove_js =~ ^[Nn]$ ]]; then
        remove_javascript="false"
    else
        remove_javascript="true"
    fi
    
    read -p "Download resources (CSS, images, etc.)? (Y/n): " download_res
    if [[ $download_res =~ ^[Nn]$ ]]; then
        download_resources="false"
    else
        download_resources="true"
    fi
    
    read -p "Enable verbose logging? (y/N): " verbose_log
    if [[ $verbose_log =~ ^[Yy]$ ]]; then
        verbose="true"
    else
        verbose="false"
    fi
    
    # Generate YAML file
    config_file="config/config.yml"
    
    print_section "Generating Configuration File"
    
    cat > "$config_file" << EOF
# Generated YAML configuration
# Created on: $(date)
# Start URL: $start_url

# ============================================================================
# WEBSITE CONFIGURATION
# ============================================================================
website:
  base_domain: "$base_domain"
  base_url: "$base_url"
  start_url: "$start_url"
  
  valid_url_patterns:
EOF

    for pattern in "${valid_patterns[@]}"; do
        echo "    - \"$pattern\"" >> "$config_file"
    done
    
    cat >> "$config_file" << EOF
  
  exclude_patterns:
EOF

    for pattern in "${exclude_patterns[@]}"; do
        echo "    - \"$pattern\"" >> "$config_file"
    done

    cat >> "$config_file" << EOF

# ============================================================================
# CRAWLING PARAMETERS
# ============================================================================
crawling:
  max_depth: $max_depth
  space_name: "$space_name"
  max_workers: $max_workers
  request_delay: $request_delay
  request_timeout: $request_timeout
  max_retries: 3

# ============================================================================
# OUTPUT CONFIGURATION
# ============================================================================
output:
  format: "$output_format"
  output_dir: "$output_dir"
  resources_dir: "$resources_dir"
  separate_spaces: true
  preserve_structure: true

# ============================================================================
# FILES CONFIGURATION
# ============================================================================
files:
  cookies_file: "config/cookies.txt"
  progress_file: "download_progress.json"
  resume_downloads: true

# ============================================================================
# CONTENT PROCESSING
# ============================================================================
content:
  remove_javascript: $remove_javascript
  clean_html: true
  remove_elements:
    - "script"
    - "noscript"
    - "iframe[src*='ads']"
    - ".advertisement"
    - "#sidebar"
  
  download_resources: $download_resources
  resource_types:
    - "css"
    - "js"
    - "png"
    - "jpg"
    - "jpeg"
    - "gif"
    - "svg"
    - "ico"
    - "woff"
    - "woff2"
    - "ttf"

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
logging:
  verbose: $verbose
  log_resources: false
  log_urls: true

# ============================================================================
# ADVANCED CONFIGURATION
# ============================================================================
advanced:
  user_agent: "Python-WebCrawler/3.0"
  headers:
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    Accept-Language: "en-US,en;q=0.5"
    Accept-Encoding: "gzip, deflate"
    Connection: "keep-alive"
  
  verify_ssl: true
  allow_redirects: true
  max_file_size: 0
  
  cdn_domains:
    - "cdn.jsdelivr.net"
    - "cdnjs.cloudflare.com"
    - "ajax.googleapis.com"
    - "fonts.googleapis.com"
    - "fonts.gstatic.com"
EOF

    print_info "✓ Configuration file created: $config_file"
    echo ""
    
    print_info "Configuration Summary:"
    echo "  - Website: $base_domain"
    echo "  - Start URL: $start_url"
    echo "  - Max Depth: $max_depth"
    echo "  - Workers: $max_workers"
    echo "  - Format: $output_format"
    echo "  - URL Patterns (will crawl URLs containing these):"
    for pattern in "${valid_patterns[@]}"; do
        echo "    * $pattern"
    done
    echo "  - Exclude patterns: ${#exclude_patterns[@]}"
    echo ""
    
    read -p "Do you want to run with YAML configuration? (Y/n): " run_now
    if [[ ! $run_now =~ ^[Nn]$ ]]; then
        print_info "Starting crawler..."
        run_python src/web_crawler.py
    else
        print_info "Configuration saved. You can run the crawler later with:"
        print_info "./setup_wizard.sh (option 6) or: run_python src/web_crawler.py"
    fi
}

# ============================================================================
# MAIN MENU
# ============================================================================

show_menu() {
    print_section "Python Web Crawler - Interactive Setup Wizard"
    
    echo "This wizard helps you configure, run, and manage the web crawler."
    echo ""
    echo "Choose an option:"
    echo ""
    echo "Setup & Configuration:"
    echo "  1) Check dependencies and setup configuration"
    echo "  2) Create YAML configuration (Interactive wizard)"
    echo "  3) Configure authentication cookies"
    echo "  4) Clean previous downloads"
    echo ""
    echo "Run Examples:"
    echo "  5) Confluence documentation site"
    echo "  6) Documentation site (Python docs)"
    echo "  7) Using YAML configuration"
    echo "  8) GitBook style documentation"
    echo "  9) Large site with resume capability"
    echo ""
    echo "Custom Configuration:"
    echo " 10) Custom crawler configuration"
    echo ""
    echo "Utilities:"
    echo " 11) Show download statistics"
    echo "  0) Exit"
    echo ""
}

# Main execution
main() {
    # We're already in the project root since the script is in the root
    
    # Check if we're in the right directory
    if [ ! -f "src/web_crawler.py" ]; then
        print_error "web_crawler.py not found. Make sure you're in the project root directory."
        exit 1
    fi
    
    while true; do
        show_menu
        read -p "Enter your choice [0-11]: " choice
        
        case $choice in
            1)
                check_python
                check_dependencies
                setup_config
                ;;
            2)
                create_yaml_config
                ;;
            3)
                configure_cookies
                ;;
            4)
                clean_downloads
                ;;
            5)
                example_confluence
                ;;
            6)
                example_docs
                ;;
            7)
                example_yaml
                ;;
            8)
                example_gitbook
                ;;
            9)
                example_large_site
                ;;
            10)
                custom_crawler
                ;;
            11)
                show_stats
                ;;
            0)
                print_info "Goodbye!"
                exit 0
                ;;
            *)
                print_error "Invalid option. Please choose 0-11."
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# Run main function
main "$@"
