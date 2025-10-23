#!/usr/bin/env python3
"""
Python Web Crawler v1.0.0
Recursive web crawler that respects depth limits and converts links to local references

Author: sjseo298
Repository: https://github.com/sjseo298/PythonHttpTracker
License: MIT
"""
import os
import re
import sys
import time
import json
import shutil
import urllib.parse
from pathlib import Path
from collections import deque
from urllib.parse import urljoin, urlparse, unquote
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, as_completed
from datetime import datetime, timedelta

# Auto-install dependencies if missing
try:
    # Try importing from current directory first (when run from src/)
    from dependency_installer import auto_install_dependencies, check_dependencies_only
except ImportError:
    try:
        # Try importing with src prefix (when run from project root)
        from src.dependency_installer import auto_install_dependencies, check_dependencies_only
    except ImportError:
        print("⚠️ Dependency installer not available. Checking manual imports...")
        auto_install_dependencies = None
        check_dependencies_only = None

if auto_install_dependencies and check_dependencies_only:
    # Check if any dependencies are missing
    installed, missing = check_dependencies_only()
    if missing:
        print("🔧 Missing dependencies detected. Installing automatically...")
        if not auto_install_dependencies(quiet=False):
            print("❌ Failed to install some dependencies. Please install manually:")
            for package in missing:
                print(f"  pip install {package}")
            sys.exit(1)
        print("✅ All dependencies installed successfully!")

try:
    import requests
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
    import yaml
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
    from rich.layout import Layout
    from rich.text import Text
    from rich.columns import Columns
except ImportError as e:
    print(f"❌ Error: Missing required dependency: {e}")
    print("Please install dependencies using:")
    print("  pip install requests beautifulsoup4 markdownify pyyaml rich")
    print("Or run: python src/dependency_installer.py")
    sys.exit(1)

# Import our database manager
try:
    # Try importing from current directory first (when run from src/)
    from database_manager import DatabaseManager
except ImportError:
    try:
        # Try importing with src prefix (when run from project root)
        from src.database_manager import DatabaseManager
    except ImportError:
        # Try adding src to path and importing
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        try:
            from database_manager import DatabaseManager
        except ImportError:
            print("❌ Error: DatabaseManager not found. Make sure database_manager.py is in src/")
            sys.exit(1)

# Import progress tracker
try:
    # Try importing from current directory first (when run from src/)
    from progress_tracker import ProgressTracker
except ImportError:
    try:
        # Try importing with src prefix (when run from project root)
        from src.progress_tracker import ProgressTracker
    except ImportError:
        print("❌ Error: ProgressTracker not found. Make sure progress_tracker.py is in src/")
        sys.exit(1)

# Import crawler orchestrator (optional - will use WebCrawler directly if not available)
try:
    from crawler_orchestrator import CrawlerOrchestrator
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    try:
        from src.crawler_orchestrator import CrawlerOrchestrator
        ORCHESTRATOR_AVAILABLE = True
    except ImportError:
        ORCHESTRATOR_AVAILABLE = False
        CrawlerOrchestrator = None

class WebCrawler:
    def __init__(self, config=None):
        # Load configuration from YAML or use defaults
        if config:
            self.config = config
        else:
            self.config = self.load_default_config()
        
        # Website configuration
        self.base_url = self.config.get('website', {}).get('base_url', '')
        self.base_domain = self.config.get('website', {}).get('base_domain', '')
        self.start_url = self.config.get('website', {}).get('start_url', '')
        self.valid_url_patterns = self.config.get('website', {}).get('valid_url_patterns', [])
        self.exclude_patterns = self.config.get('website', {}).get('exclude_patterns', [])
        
        # Crawling parameters
        self.max_depth = self.config.get('crawling', {}).get('max_depth', 1)
        self.space = self.config.get('crawling', {}).get('space_name', 'DEFAULT')
        self.max_workers = self.config.get('crawling', {}).get('max_workers', 5)
        self.request_delay = self.config.get('crawling', {}).get('request_delay', 0.5)
        self.request_timeout = self.config.get('crawling', {}).get('request_timeout', 30)
        
        # Output configuration
        self.output_format = self.config.get('output', {}).get('format', 'markdown').lower()
        self.output_dir = self.config.get('output', {}).get('output_dir', 'downloaded_content')
        self.resources_dir = self.config.get('output', {}).get('resources_dir', 'shared_resources')
        
        # Files and paths
        self.cookies_file = self.config.get('files', {}).get('cookies_file', 'config/cookies.txt')
        self.db_path = self.config.get('files', {}).get('database_file', 'crawler_data.db')
        
        # Initialize database manager
        self.db = DatabaseManager(self.db_path)
        
        # Initialize progress tracker
        self.progress_tracker = ProgressTracker()
        
        # Internal state
        self.session = requests.Session()
        self.download_queue = deque()
        
        # Load state from database
        self.downloaded_urls = self.db.get_downloaded_urls()
        self.active_downloads = set()  # Track URLs currently being downloaded
        self.downloaded_resources = self.db.get_downloaded_resources()
        self.url_to_filename = self.db.get_url_to_filename_mapping()
        self.transversal_resources = self.db.get_transversal_resources()
        
        # Granular lock system for thread-safety
        self.download_lock = threading.Lock()
        self.progress_lock = threading.Lock()
        self.queue_lock = threading.Lock()
        self.resource_lock = threading.Lock()
        self.active_downloads = set()
        self.active_resources = set()
        self.url_locks = {}
        self.resource_locks = {}
        
        # Create folder for shared resources
        self.shared_resources_dir = Path(f"{self.output_dir}/{self.resources_dir}")
        self.shared_resources_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup output directories with .gitkeep files
        self.setup_output_directories()
        
        # Load pending URLs from database
        self.load_progress()
        
        # Load cookies
        self.load_cookies()
        
        # Setup headers from config
        self.setup_headers()
    
    def load_default_config(self):
        """Loads default configuration if none provided"""
        return {
            'website': {
                'base_domain': 'example.com',
                'base_url': 'https://example.com',
                'start_url': 'https://example.com',
                'valid_url_patterns': ['/'],
                'exclude_patterns': ['/admin', '/login']
            },
            'crawling': {
                'max_depth': 1,
                'space_name': 'DEFAULT',
                'max_workers': 5,
                'request_delay': 0.5,
                'request_timeout': 30
            },
            'output': {
                'format': 'markdown',
                'output_dir': 'downloaded_content',
                'resources_dir': 'shared_resources'
            },
            'files': {
                'cookies_file': 'config/cookies.txt',
                'progress_file': 'download_progress.json'
            }
        }
    
    def setup_headers(self):
        """Configures HTTP headers from configuration"""
        default_headers = {
            'User-Agent': self.config.get('advanced', {}).get('user_agent', 
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Add custom headers from configuration
        custom_headers = self.config.get('advanced', {}).get('headers', {})
        default_headers.update(custom_headers)
        
        self.session.headers.update(default_headers)

    def setup_output_directories(self):
        """Create output directories and add .gitkeep files"""
        # Create main output directory
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create .gitkeep file in main output directory
        gitkeep_main = output_path / '.gitkeep'
        if not gitkeep_main.exists():
            gitkeep_main.write_text('# This file ensures the directory is tracked by Git\n# Downloaded content will be stored here\n')
            print(f"📁 Created .gitkeep in {output_path}")
        
        # Create .gitkeep in shared resources directory
        gitkeep_resources = self.shared_resources_dir / '.gitkeep'
        if not gitkeep_resources.exists():
            gitkeep_resources.write_text('# This file ensures the directory is tracked by Git\n# Shared resources (CSS, images) will be stored here\n')
            print(f"📁 Created .gitkeep in {self.shared_resources_dir}")

    def reload_config(self):
        """Reloads configuration from YAML file to pick up any changes"""
        try:
            config_path = 'config/config.yml'
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    updated_config = yaml.safe_load(f)
                    # Update configuration while preserving critical runtime state
                    if updated_config:
                        # Only update safe-to-change settings during runtime
                        content_settings = updated_config.get('content', {})
                        if 'download_resources' in content_settings:
                            self.config.setdefault('content', {})['download_resources'] = content_settings['download_resources']
                            print(f"🔄 Config reloaded: download_resources = {content_settings['download_resources']}")
                        
                        output_settings = updated_config.get('output', {})
                        if 'format' in output_settings:
                            old_format = self.output_format
                            self.output_format = output_settings['format'].lower()
                            if old_format != self.output_format:
                                print(f"🔄 Config reloaded: output_format = {self.output_format}")
        except Exception as e:
            print(f"⚠️ Error reloading config: {e}")

    def load_cookies(self):
        """Loads cookies from file in HTTP cookie string format"""
        cookies = {}
        try:
            with open(self.cookies_file, 'r') as f:
                content = f.read().strip()
                
                # If it's HTTP string format (separated by ;)
                if ';' in content:
                    for cookie_pair in content.split(';'):
                        cookie_pair = cookie_pair.strip()
                        if '=' in cookie_pair:
                            name, value = cookie_pair.split('=', 1)
                            cookies[name.strip()] = value.strip()
                else:
                    # Netscape format (separated by tabs)
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            parts = line.split('\t')
                            if len(parts) >= 7:
                                domain, flag, path, secure, expiration, name, value = parts[:7]
                                cookies[name] = value
            
            for name, value in cookies.items():
                self.session.cookies.set(name, value, domain='segurosti.atlassian.net')
            print(f"✓ Loaded {len(cookies)} cookies")
        except Exception as e:
            print(f"Error loading cookies: {e}")

    def load_progress(self):
        """Loads pending URLs from database"""
        try:
            # Get pending URLs from database
            pending_urls = self.db.get_pending_urls()
            self.download_queue = deque(pending_urls)
            
            # Get statistics
            stats = self.db.get_stats()
            total_downloaded = stats.get('total_documents', 0)
            pending_count = len(self.download_queue)
            
            if total_downloaded > 0 or pending_count > 0:
                print(f"✓ Progress loaded: {total_downloaded} documents downloaded, {pending_count} pending")
                
                # Reload configuration to pick up any changes made while stopped
                self.reload_config()
            else:
                print("📂 Starting fresh crawl - no previous progress found")
                
        except Exception as e:
            print(f"❌ Error loading progress: {e}")

    def save_progress(self):
        """Progress is automatically saved to database during operations"""
        # No explicit save needed - database operations are atomic
        # This method is kept for compatibility but could be removed
        pass

    def acquire_url_lock(self, url):
        """Acquires an exclusive lock for a specific URL"""
        with self.download_lock:
            # If URL is already being processed, don't continue
            if url in self.active_downloads:
                return False
            # If already downloaded, don't continue
            if url in self.downloaded_urls:
                return False
            # Mark as active and create lock if it doesn't exist
            self.active_downloads.add(url)
            if url not in self.url_locks:
                self.url_locks[url] = threading.Lock()
        
        # Acquire the specific URL lock
        self.url_locks[url].acquire()
        return True

    def release_url_lock(self, url):
        """Releases the lock for a specific URL"""
        if url in self.url_locks:
            self.url_locks[url].release()
        with self.download_lock:
            self.active_downloads.discard(url)

    def acquire_resource_lock(self, resource_url):
        """Acquires an exclusive lock for a specific resource"""
        with self.resource_lock:
            # If resource is already being processed, don't continue
            if resource_url in self.active_resources:
                return False
            # If already downloaded, don't continue
            if resource_url in self.downloaded_resources:
                return False
            # Mark as active and create lock if it doesn't exist
            self.active_resources.add(resource_url)
            if resource_url not in self.resource_locks:
                self.resource_locks[resource_url] = threading.Lock()
        
        # Acquire the specific resource lock
        self.resource_locks[resource_url].acquire()
        return True

    def release_resource_lock(self, resource_url):
        """Releases the lock for a specific resource"""
        if resource_url in self.resource_locks:
            self.resource_locks[resource_url].release()
        with self.resource_lock:
            self.active_resources.discard(resource_url)

    def clean_url(self, url):
        """Cleans a URL by removing parameters, anchors, etc."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def is_transversal_resource(self, url):
        """Detects if a resource is transversal (common to multiple pages)"""
        # ALL resources are considered transversal by default
        # Only exclude very specific cases if any
        return True

    def get_resource_directory(self, url, page_resources_dir):
        """Determines which directory to save the resource in"""
        # All resources are transversal, but organized in different folders
        if any(cdn_domain in url for cdn_domain in [
            'media-cdn.atlassian.com',
            'avatar-management--avatars.us-west-2.prod.public.atl-paas.net',
            'secure.gravatar.com'
        ]):
            # Create subdirectory for CDN images
            cdn_dir = self.shared_resources_dir / "cdn_images"
            cdn_dir.mkdir(exist_ok=True)
            return cdn_dir
        else:
            # Confluence resources go in the main shared_resources folder
            return self.shared_resources_dir

    def is_atlassian_resource(self, url):
        """Checks if a URL is an Atlassian resource we should download"""
        return any(domain in url for domain in [
            'segurosti.atlassian.net',
            'media-cdn.atlassian.com',
            'id-frontend.prod-east.frontend.public.atl-paas.net',
            'avatar-management--avatars.us-west-2.prod.public.atl-paas.net',
            'secure.gravatar.com'  # User avatars
        ])

    def is_valid_url(self, url):
        """Checks if the URL is valid for download according to configuration"""
        if not url or not url.startswith(('http://', 'https://')):
            return False
        
        parsed = urlparse(url)
        
        # Verificar dominio base
        if self.base_domain and parsed.netloc != self.base_domain:
            return False
        
        # Verificar patrones excluidos
        for exclude_pattern in self.exclude_patterns:
            if exclude_pattern in url:
                return False
        
        # Verificar patrones válidos
        if self.valid_url_patterns:
            valid = False
            for valid_pattern in self.valid_url_patterns:
                if valid_pattern in url:
                    valid = True
                    break
            if not valid:
                return False
        
        return True
        
        # Filter problematic URLs
        bad_patterns = ['login', 'logout', 'edit', 'create', 'delete', 'admin', 'export', 'action=']
        return not any(pattern in url.lower() for pattern in bad_patterns)

    def extract_links(self, html_content, current_url):
        """Extracts Confluence links from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = set()
        
        # Find all href links
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Convert to absolute URL
            absolute_url = urljoin(current_url, href)
            
            if self.is_valid_url(absolute_url):
                # Clean unnecessary parameters
                parsed = urlparse(absolute_url)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                links.add(clean_url)
        
        return links

    def url_to_local_path(self, url):
        """Converts URL to local file path"""
        parsed = urlparse(url)
        path = parsed.path
        
        # Create relative path based on site structure
        # Remove common prefixes if configured
        if path.startswith('/wiki/'):
            path = path[6:]  # For Confluence-type sites
        elif path.startswith('/docs/'):
            path = path[6:]  # For documentation sites
        elif path.startswith('/help/'):
            path = path[6:]  # For help sites
        
        # If path is empty, use index
        if not path or path == '/':
            path = 'index'
        
        # Convert to file path with appropriate extension
        extension = '.md' if self.output_format == 'markdown' else '.html'
        if path.endswith('/'):
            path += f'index{extension}'
        elif not path.endswith(('.html', '.md')):
            path += extension
        
        # Clean problematic characters
        path = re.sub(r'[<>:"|?*]', '_', path)
        path = unquote(path)
        
        # Ensure path is relative and within output directory
        path = path.lstrip('/')
        path = f"{self.output_dir}/{path}"
        
        return path

    def download_url(self, url, depth):
        """Downloads a specific URL"""
        # Clean URL for consistency
        parsed = urlparse(url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        if clean_url in self.downloaded_urls:
            local_path = self.url_to_filename.get(clean_url, "unknown")
            print(f"{'  ' * (self.max_depth - depth)}🔄 Already downloaded: {Path(local_path).name}")
            return None
        
        print(f"{'  ' * (self.max_depth - depth)}[Depth {depth}] Downloading: {clean_url}")
        
        # Mark as downloading in database
        if not self.db.mark_url_downloading(clean_url):
            print(f"{'  ' * (self.max_depth - depth)}⚠️ URL already being processed")
            return None
        
        start_time = time.time()
        
        try:
            response = self.session.get(clean_url, timeout=30)
            response.raise_for_status()
            
            # Check for authentication errors
            if self.is_authentication_error(response.text, clean_url):
                error_msg = "Authentication error: Page requires login or cookies expired"
                print(f"{'  ' * (self.max_depth - depth)}🔐 {error_msg}")
                self.show_cookie_help()
                self.db.mark_url_failed(clean_url, error_msg)
                return None
            
            # Create local directory
            local_path = self.url_to_local_path(clean_url)
            full_path = Path(local_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Process content before saving
            processed_content = self.process_content(response.text, clean_url, str(full_path))
            
            # Save file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            
            # Calculate file size and download time
            file_size = full_path.stat().st_size
            download_time = time.time() - start_time
            
            # Extract and save new links
            links_extracted = 0
            if depth > 0:
                print(f"{'  ' * (self.max_depth - depth)}📋 Extracting links (next depth: {depth-1})")
                links = self.extract_links(response.text, clean_url)
                
                # Add discovered links to database
                urls_data = []
                for link in links:
                    if link not in self.downloaded_urls:
                        link_clean = self.clean_url(link)
                        urls_data.append((link, link_clean, depth - 1, clean_url))
                
                if urls_data:
                    links_extracted = self.db.add_discovered_urls_batch(urls_data)
                    print(f"{'  ' * (self.max_depth - depth)}🔗 Added {links_extracted} new links to database")
            else:
                print(f"{'  ' * (self.max_depth - depth)}🛑 Depth 0 reached - no more links followed")
            
            # Mark as completed in database
            self.db.mark_url_completed(clean_url, str(full_path), file_size, download_time, links_extracted, depth)
            
            # Update local state
            self.downloaded_urls.add(clean_url)
            self.url_to_filename[clean_url] = str(full_path)
            
            # Update progress tracker
            self.progress_tracker.update_stat('urls_downloaded')
            if links_extracted > 0:
                self.progress_tracker.update_stat('urls_discovered', increment=links_extracted)
            self.progress_tracker.update_stat('total_size', increment=file_size)
            
            print(f"{'  ' * (self.max_depth - depth)}✓ Saved: {local_path} ({file_size:,} bytes)")
            
            return response.text
            
        except Exception as e:
            print(f"{'  ' * (self.max_depth - depth)}❌ Error downloading {url}: {e}")
            # Mark as failed in database
            self.db.mark_url_failed(clean_url, str(e))
            
            # Update progress tracker for failed URLs
            self.progress_tracker.update_stat('urls_failed')
            
            return None

    def is_authentication_error(self, response_text: str, url: str) -> bool:
        """Detect if the response is an authentication error page"""
        auth_error_indicators = [
            "Log in with Atlassian account",
            "We tried to load scripts but something went wrong",
            "id-frontend.prod-east.frontend.public.atl-paas.net",
            "Sign in to Atlassian",
            "Please log in to access this page",
            "Authentication required",
            "Access denied",
            "You must log in",
            "Session expired"
        ]
        
        response_lower = response_text.lower()
        for indicator in auth_error_indicators:
            if indicator.lower() in response_lower:
                return True
        
        # Check if response is too short (likely an error page)
        if len(response_text.strip()) < 500:
            return True
            
        return False

    def show_cookie_help(self):
        """Show helpful instructions for updating cookies"""
        print("\n" + "="*60)
        print("🔐 AUTHENTICATION ERROR DETECTED")
        print("="*60)
        print("The crawler encountered authentication errors. Your cookies may be expired.")
        print("\nTo fix this:")
        print("1. Open your browser and go to: https://segurosti.atlassian.net")
        print("2. Log in with your credentials")
        print("3. Open Developer Tools (F12) → Network tab")
        print("4. Refresh the page and find any request to segurosti.atlassian.net")
        print("5. Copy the Cookie header value from the request")
        print("6. Update config/cookies.txt with the new cookie string")
        print("\nExample cookie format:")
        print("tenant.session.token=...; JSESSIONID=...; AWSALB=...")
        print("="*60 + "\n")

    def download_url_parallel(self, url_depth_pair):
        """Thread-safe function to download an individual URL in parallel"""
        url, depth = url_depth_pair
        clean_url = self.clean_url(url)
        
        # Check if already downloaded using database (non-blocking check)
        if clean_url in self.downloaded_urls:
            local_path = self.url_to_filename.get(clean_url, "unknown")
            print(f"{'  ' * (self.max_depth - depth)}🔄 Already downloaded: {Path(local_path).name}")
            return None
        
        # Quick non-blocking check for duplicate processing
        with self.queue_lock:
            if clean_url in self.active_downloads:
                print(f"{'  ' * (self.max_depth - depth)}⚠️ URL already being processed")
                return None
            self.active_downloads.add(clean_url)
        
        start_time = time.time()
        
        try:
            # Create a new session for this thread (thread-safe) with optimized timeouts
            local_session = requests.Session()
            local_session.cookies.update(self.session.cookies)
            local_session.headers.update(self.session.headers)
            
            # Optimized timeout settings - connection timeout: 5s, read timeout: 15s
            timeout = (5, 15)  # (connect_timeout, read_timeout)
            
            # Perform the download with aggressive timeout
            response = local_session.get(clean_url, timeout=timeout)
            response.raise_for_status()
            
            # Check for authentication errors
            if self.is_authentication_error(response.text, clean_url):
                error_msg = "Authentication error: Page requires login or cookies expired"
                print(f"{'  ' * (self.max_depth - depth)}🔐 {error_msg}")
                self.show_cookie_help()
                self.db.mark_url_failed(clean_url, error_msg)
                return None
            
            # Generate local path
            local_path = self.url_to_local_path(clean_url)
            full_path = Path(local_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Process content (this includes cleaning JS, updating links and downloading resources)
            processed_content = self.process_content(response.text, clean_url, str(full_path))
            
            # Save the processed file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            
            # Calculate file size and download time
            file_size = full_path.stat().st_size
            download_time = time.time() - start_time
            
            # Extract and save new links
            links_extracted = 0
            if depth > 0:
                print(f"{'  ' * (self.max_depth - depth)}📋 Extracting links (next depth: {depth-1})")
                links = self.extract_links(response.text, clean_url)
                
                # Add discovered links to database
                urls_data = []
                for link in links:
                    if link not in self.downloaded_urls:
                        link_clean = self.clean_url(link)
                        urls_data.append((link, link_clean, depth - 1, clean_url))
                
                if urls_data:
                    links_extracted = self.db.add_discovered_urls_batch(urls_data)
                    print(f"{'  ' * (self.max_depth - depth)}🔗 Added {links_extracted} new links to database")
                    
                    # Add to download queue for processing
                    with self.queue_lock:
                        for link, link_clean, new_depth, parent in urls_data:
                            if link_clean not in self.downloaded_urls and link_clean not in self.active_downloads:
                                self.download_queue.append((link_clean, new_depth))
            else:
                print(f"{'  ' * (self.max_depth - depth)}🛑 Depth 0 reached - no more links followed")
            
            # Mark as completed in database
            self.db.mark_url_completed(clean_url, str(full_path), file_size, download_time, links_extracted, depth)
            
            # Update local state
            self.downloaded_urls.add(clean_url)
            self.url_to_filename[clean_url] = str(full_path)
            
            # Update progress tracker
            self.progress_tracker.update_stat('urls_downloaded')
            if links_extracted > 0:
                self.progress_tracker.update_stat('urls_discovered', increment=links_extracted)
            self.progress_tracker.update_stat('total_size', increment=file_size)
            
            print(f"{'  ' * (self.max_depth - depth)}✓ Saved: {local_path} ({file_size:,} bytes)")
            
            return response.text
            
        except Exception as e:
            print(f"{'  ' * (self.max_depth - depth)}❌ Error downloading {url}: {e}")
            # Mark as failed in database
            self.db.mark_url_failed(clean_url, str(e))
            
            # Update progress tracker for failed URLs
            self.progress_tracker.update_stat('urls_failed')
            
            return None

    def process_content(self, html_content, current_url, filename):
        """Processes HTML content: updates links, cleans JS, downloads resources and converts to Markdown if necessary"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            changes_made = False
            
            # Update links
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                absolute_url = urljoin(current_url, href)
                
                # Clean the absolute URL (remove parameters, anchors, etc.)
                parsed = urlparse(absolute_url)
                clean_absolute_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                
                # If it's a valid Confluence URL, convert to local path
                if self.is_valid_url(clean_absolute_url):
                    # Generate the local path this URL would have
                    target_local_path = self.url_to_local_path(clean_absolute_url)
                    target_file = Path(target_local_path)
                    
                    # Calculate relative path from current file
                    current_dir = Path(filename).parent
                    
                    try:
                        relative_path = os.path.relpath(target_file, current_dir)
                        # Ensure link has correct extension
                        expected_extension = '.md' if self.output_format == 'markdown' else '.html'
                        if not relative_path.endswith((expected_extension, '.html', '.md')):
                            relative_path += expected_extension
                        a_tag['href'] = relative_path.replace('\\', '/')
                        changes_made = True
                    except ValueError:
                        # If relative path cannot be calculated, use absolute local
                        target_path = str(target_file).replace('\\', '/')
                        expected_extension = '.md' if self.output_format == 'markdown' else '.html'
                        if not target_path.endswith((expected_extension, '.html', '.md')):
                            target_path += expected_extension
                        a_tag['href'] = target_path
                        changes_made = True
            
            # Clean JavaScript
            self.clean_javascript_in_soup(soup)
            
            # Download resources (CSS, images) only if enabled in current config
            if self.config.get('content', {}).get('download_resources', True):
                self.download_resources(soup, current_url, filename)
            
            # Convert to Markdown if necessary
            if self.output_format == 'markdown':
                # Extract only main content (remove navigation, etc.)
                main_content = self.extract_main_content(soup)
                markdown_content = md(str(main_content), 
                                    heading_style="ATX",  # Use # for headings
                                    bullets="-",          # Use - for lists
                                    convert=['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                                            'ul', 'ol', 'li', 'a', 'strong', 'em', 'code', 'pre',
                                            'blockquote', 'img', 'table', 'tr', 'td', 'th'])
                
                # Add metadata at the beginning
                metadata = f"# {soup.title.string if soup.title else 'Confluence Page'}\n\n"
                metadata += f"**Original URL:** {current_url}\n\n"
                metadata += "---\n\n"
                
                return metadata + markdown_content
            else:
                return str(soup)
                
        except Exception as e:
            print(f"❌ Error processing content from {filename}: {e}")
            return html_content

    def extract_main_content(self, soup):
        """Extracts main page content, removing navigation and unnecessary elements"""
        # Find main Confluence content
        main_content = soup.find('div', {'id': 'main-content'}) or \
                      soup.find('div', {'class': 'wiki-content'}) or \
                      soup.find('main') or \
                      soup.find('article') or \
                      soup.find('div', {'class': 'content'})
        
        if main_content:
            # Remove navigation and Confluence-specific UI elements
            for element in main_content.find_all(['nav', 'header', 'footer']):
                element.decompose()
            
            # Remove elements with Confluence-specific classes
            for class_name in ['page-metadata', 'page-toolbar', 'breadcrumbs', 
                              'space-tools-section', 'aui-toolbar']:
                for element in main_content.find_all(attrs={'class': class_name}):
                    element.decompose()
            
            return main_content
        else:
            # If no main content found, use the entire body
            return soup.find('body') or soup



    def clean_javascript_in_soup(self, soup):
        """Cleans JavaScript from a BeautifulSoup object"""
        # Remove scripts
        for script in soup.find_all('script'):
            script.decompose()
        
        # Remove JavaScript events
        for tag in soup.find_all():
            for attr in list(tag.attrs.keys()):
                if attr.lower().startswith('on'):  # onclick, onload, etc.
                    del tag.attrs[attr]
        
        # Remove meta refresh
        for meta in soup.find_all('meta', attrs={'http-equiv': 'refresh'}):
            meta.decompose()
        
        # Remove noscript
        for noscript in soup.find_all('noscript'):
            noscript.decompose()

    def download_resources(self, soup, base_url, html_file_path):
        """Downloads resources (CSS, images, etc.) referenced in HTML"""
        page_resources_dir = Path(html_file_path).parent / "resources"
        page_resources_dir.mkdir(exist_ok=True)
        
        # Download CSS
        for link in soup.find_all('link', rel='stylesheet'):
            if link.get('href'):
                try:
                    resource_url = urljoin(base_url, link['href'])
                    if self.is_atlassian_resource(resource_url):
                        target_dir = self.get_resource_directory(resource_url, page_resources_dir)
                        filename = self.download_single_resource(resource_url, target_dir, 'css')
                        if filename:
                            # Update reference in HTML
                            relative_path = os.path.relpath(filename, Path(html_file_path).parent)
                            link['href'] = relative_path.replace('\\', '/')
                except Exception as e:
                    print(f"❌ Error downloading CSS {link.get('href')}: {e}")
        
        # Download images
        for img in soup.find_all('img'):
            if img.get('src'):
                try:
                    resource_url = urljoin(base_url, img['src'])
                    if self.is_atlassian_resource(resource_url):
                        target_dir = self.get_resource_directory(resource_url, page_resources_dir)
                        filename = self.download_single_resource(resource_url, target_dir, 'img')
                        if filename:
                            # Update reference in HTML
                            relative_path = os.path.relpath(filename, Path(html_file_path).parent)
                            img['src'] = relative_path.replace('\\', '/')
                except Exception as e:
                    print(f"❌ Error downloading image {img.get('src')}: {e}")

    def download_single_resource(self, url, resources_dir, resource_type):
        """Downloads a single resource and returns the filename (thread-safe)"""
        # Check if already downloaded using database
        if self.db.is_resource_downloaded(url):
            existing_path = self.db.get_resource_path(url)
            if existing_path and Path(existing_path).exists():
                print(f"{'  ' * (self.max_depth - 0)}📎 Resource already downloaded: {Path(existing_path).name}")
                return existing_path
        
        # Try to acquire exclusive lock for this resource
        if not self.acquire_resource_lock(url):
            # If already being processed, check if exists in transversal resources
            if url in self.transversal_resources:
                existing_file = Path(self.transversal_resources[url])
                if existing_file.exists():
                    print(f"{'  ' * (self.max_depth - 0)}📎 Transversal resource already downloaded: {existing_file.name}")
                    return str(existing_file)
            return None
        
        start_time = time.time()
        
        try:
            # Generate filename
            parsed_url = urlparse(url)
            filename = Path(parsed_url.path).name
            if not filename or '.' not in filename:
                # Generate name based on type
                extension = '.css' if resource_type == 'css' else '.png'
                filename = f"resource_{hash(url) % 10000}{extension}"
            
            file_path = resources_dir / filename
            
            # Check if file already exists locally (double-check with lock)
            if file_path.exists():
                print(f"{'  ' * (self.max_depth - 0)}📎 Resource already exists: {filename}")
                
                # Add to database
                file_size = file_path.stat().st_size
                is_transversal = self.is_transversal_resource(url)
                self.db.add_downloaded_resource(url, str(file_path), resource_type, file_size, None, None, is_transversal)
                
                # Thread-safe update
                with self.resource_lock:
                    self.downloaded_resources.add(url)
                    if is_transversal:
                        self.transversal_resources[url] = str(file_path)
                
                return str(file_path)
            
            # Create a new session for thread-safety with optimized timeouts
            local_session = requests.Session()
            local_session.cookies.update(self.session.cookies)
            local_session.headers.update(self.session.headers)
            
            # Much shorter timeout for resources - they should be faster
            timeout = (3, 10)  # (connect_timeout, read_timeout)
            response = local_session.get(url, timeout=timeout)
            response.raise_for_status()
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            # Calculate file size and download time
            file_size = file_path.stat().st_size
            download_time = time.time() - start_time
            
            # Add to database
            is_transversal = self.is_transversal_resource(url)
            self.db.add_downloaded_resource(url, str(file_path), resource_type, file_size, download_time, None, is_transversal)
            
            # Thread-safe state update
            with self.resource_lock:
                self.downloaded_resources.add(url)
                if is_transversal:
                    self.transversal_resources[url] = str(file_path)
                    print(f"{'  ' * (self.max_depth - 0)}📎 Transversal resource saved: {filename}")
                else:
                    print(f"{'  ' * (self.max_depth - 0)}📎 Specific resource saved: {filename}")
                
                # Update progress tracker
                self.progress_tracker.update_stat('resources_downloaded')
                self.progress_tracker.update_stat('total_size', increment=file_size)
                
            return str(file_path)
            
        except Exception as e:
            print(f"❌ Error downloading resource {url}: {e}")
            return None
        finally:
            # Always release the resource lock
            self.release_resource_lock(url)

    def download_recursive(self, start_url):
        """Recursively downloads from the initial URL using parallelism"""
        
        # Clean initial URL for consistency
        parsed = urlparse(start_url)
        clean_start_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # Only add initial URL to queue if no queue loaded and not already downloaded
        if not self.download_queue and clean_start_url not in self.downloaded_urls:
            # Add initial URL to database as discovered
            self.db.add_discovered_url(start_url, clean_start_url, self.max_depth, None)
            self.download_queue.append((clean_start_url, self.max_depth))
        
        # Initialize progress tracking with existing data
        existing_downloaded = len(self.downloaded_urls)
        existing_resources = len(self.downloaded_resources)
        
        self.progress_tracker.update_stat('urls_queued', len(self.download_queue))
        self.progress_tracker.update_stat('current_depth', self.max_depth)
        self.progress_tracker.update_stat('urls_downloaded', existing_downloaded)
        self.progress_tracker.update_stat('resources_downloaded', existing_resources)
        
        # Calculate total size of already downloaded content
        total_size = 0
        try:
            stats = self.db.get_crawl_statistics()
            total_size = stats.get('total_size', 0)
            # Also update discovered URLs from database
            total_urls = stats.get('total_urls', 0)
            if total_urls > existing_downloaded:
                self.progress_tracker.update_stat('urls_discovered', total_urls)
        except:
            pass
        self.progress_tracker.update_stat('total_size', total_size)
        
        # Initialize progress bar with total URLs (discovered + pending)
        total_discovered = self.progress_tracker.stats['urls_discovered'] + len(self.download_queue)
        initial_total = max(total_discovered, existing_downloaded + len(self.download_queue), 1)
        self.progress_tracker.initialize_progress_bar(initial_total)
        
        # Start progress display with Rich Live
        with Live(self.progress_tracker.create_progress_panel(), refresh_per_second=2) as live:
            try:
                # Process download queue with true parallelism
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all URLs to the thread pool at once for true parallelism
                    active_futures = {}
                    future_start_times = {}  # Track when each future started
                    max_future_timeout = 60  # Maximum time to allow a future to run (seconds)
                    
                    while self.download_queue or active_futures:
                        # Cancel futures that are taking too long
                        current_time = time.time()
                        futures_to_cancel = []
                        for future, start_time in future_start_times.items():
                            if current_time - start_time > max_future_timeout:
                                futures_to_cancel.append(future)
                        
                        for future in futures_to_cancel:
                            if future in active_futures:
                                url_depth = active_futures.pop(future)
                                future.cancel()  # Try to cancel
                                future_start_times.pop(future, None)
                                self.progress_tracker.increment_stat('urls_failed')
                                self.progress_tracker.update_stat('last_error', f'Timeout after {max_future_timeout}s: {url_depth[0]}')
                                print(f"⏰ Cancelled timeout future: {url_depth[0]}")
                        
                        # Submit new jobs while we have capacity and pending URLs
                        while len(active_futures) < self.max_workers and self.download_queue:
                            url_depth = self.download_queue.popleft()
                            future = executor.submit(self.download_url_parallel, url_depth)
                            active_futures[future] = url_depth
                            future_start_times[future] = current_time
                            
                            # Update progress tracker
                            self.progress_tracker.update_stat('urls_queued', len(self.download_queue))
                            self.progress_tracker.update_stat('active_threads', len(active_futures))
                            live.update(self.progress_tracker.create_progress_panel())
                        
                        # Process completed jobs
                        if active_futures:
                            # Check for completed futures with a very short timeout to avoid blocking
                            completed_futures = []
                            
                            # Use a very short timeout to keep the system responsive
                            try:
                                for future in as_completed(active_futures.keys(), timeout=0.1):
                                    completed_futures.append(future)
                                    # Process one completed job and continue immediately
                                    break
                            except TimeoutError:
                                # No jobs completed yet, that's ok - continue to submit more if possible
                                completed_futures = []
                            
                            # Handle completed futures
                            for future in completed_futures:
                                url_depth = active_futures.pop(future)
                                future_start_times.pop(future, None)  # Clean up timing tracking
                                try:
                                    result = future.result(timeout=0.1)  # Very short timeout on result
                                    if result:
                                        # Update last processed URL
                                        self.progress_tracker.update_stat('last_url', url_depth[0])
                                except TimeoutError:
                                    # Result not ready yet, put it back for next iteration
                                    active_futures[future] = url_depth
                                    future_start_times[future] = current_time  # Reset timing
                                except Exception as exc:
                                    self.progress_tracker.increment_stat('urls_failed')
                                    self.progress_tracker.update_stat('last_error', str(exc))
                                
                                # Update active threads count
                                self.progress_tracker.update_stat('active_threads', len(active_futures))
                                # Update progress display
                                live.update(self.progress_tracker.create_progress_panel())
                        
                        # Brief pause to prevent busy waiting, but keep system responsive
                        if not self.download_queue and not active_futures:
                            break
                        elif not completed_futures and active_futures:
                            # If we have active futures but none completed, short pause
                            time.sleep(0.05)
                
                # Final update
                self.progress_tracker.update_stat('urls_queued', 0)
                live.update(self.progress_tracker.create_progress_panel())
                
            except KeyboardInterrupt:
                self.progress_tracker.update_stat('last_error', 'Interrupted by user')
                live.update(self.progress_tracker.create_progress_panel())
                print(f"\n🛑 Download interrupted by user")
                raise
        
        return len(self.downloaded_urls)
    
    def crawl(self):
        """
        Main crawl entry point - wrapper around download_recursive for compatibility
        This method is called by CrawlerOrchestrator
        """
        return self.download_recursive(self.start_url)

def load_config():
    """Loads configuration from YAML file or returns default configuration"""
    config_path = 'config/config.yml'
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                print(f"✓ Configuration loaded from {config_path}")
                return config
        except Exception as e:
            print(f"⚠️  Error loading YAML configuration: {e}")
            print("📄 Using default configuration")
    else:
        print(f"📄 {config_path} not found, using default configuration")
    
    return None

def check_existing_content(config):
    """Check if there's existing downloaded content and database progress"""
    output_dir = config.get('output', {}).get('output_dir', 'downloaded_content')
    db_path = config.get('files', {}).get('database_file', 'crawler_data.db')
    
    has_files = False
    has_database = False
    
    # Check if output directory exists and has content
    if os.path.exists(output_dir):
        # Count files in the directory (excluding directories)
        file_count = sum(1 for root, dirs, files in os.walk(output_dir) for file in files)
        if file_count > 0:
            has_files = True
    
    # Check if database exists and has progress
    if os.path.exists(db_path):
        try:
            from database_manager import DatabaseManager
            db = DatabaseManager(db_path)
            url_count = db.get_total_urls_count()
            if url_count > 0:
                has_database = True
            db.close()
        except Exception as e:
            print(f"⚠️  Error checking database: {e}")
    
    return has_files, has_database

def show_startup_menu(has_files, has_database, output_dir, db_path):
    """Show interactive menu for handling existing content"""
    print("\n" + "="*60)
    print("🔍 EXISTING CONTENT DETECTED")
    print("="*60)
    
    if has_files:
        file_count = sum(1 for root, dirs, files in os.walk(output_dir) for file in files)
        print(f"📁 Downloaded files found: {file_count} files in {output_dir}")
    
    if has_database:
        try:
            from database_manager import DatabaseManager
            db = DatabaseManager(db_path)
            stats = db.get_crawl_statistics()
            print(f"📊 Database progress: {stats['total_urls']} URLs, {stats['downloaded_urls']} downloaded")
            db.close()
        except:
            print(f"📊 Database progress: Found existing progress data")
    
    print("\nChoose an option:")
    print("1️⃣  Delete all and start fresh (removes all files and database)")
    print("2️⃣  Keep files but reset progress (discover new/updated content)")
    print("3️⃣  Continue from where we left off (resume existing progress)")
    print("4️⃣  Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-4): ").strip()
            if choice in ['1', '2', '3', '4']:
                return choice
            else:
                print("❌ Invalid choice. Please enter 1, 2, 3, or 4")
        except KeyboardInterrupt:
            print("\n👋 Exiting...")
            sys.exit(0)

def handle_existing_content_choice(choice, output_dir, db_path):
    """Handle user's choice for existing content"""
    if choice == '1':
        # Delete all and start fresh
        print("\n🗑️  Deleting all existing content...")
        try:
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)
                print(f"✓ Deleted directory: {output_dir}")
            
            if os.path.exists(db_path):
                os.remove(db_path)
                print(f"✓ Deleted database: {db_path}")
            
            print("✅ All content deleted successfully. Starting fresh...")
            return True
        except Exception as e:
            print(f"❌ Error deleting content: {e}")
            sys.exit(1)
    
    elif choice == '2':
        # Keep files but reset progress
        print("\n🔄 Resetting progress while keeping files...")
        try:
            if os.path.exists(db_path):
                from database_manager import DatabaseManager
                db = DatabaseManager(db_path)
                db.reset_progress()
                db.close()
                print("✓ Database progress reset")
            
            print("✅ Progress reset. Will discover new/updated content...")
            return True
        except Exception as e:
            print(f"❌ Error resetting progress: {e}")
            sys.exit(1)
    
    elif choice == '3':
        # Continue from existing progress
        print("\n▶️  Continuing from existing progress...")
        return True
    
    elif choice == '4':
        # Exit
        print("\n👋 Exiting...")
        sys.exit(0)
    
    return False

def main():
    """
    Main entry point for the web crawler
    
    NEW: The crawler now supports Confluence API mode!
    - Automatically detects Confluence sites
    - Uses REST API if credentials are available (.env or confluence_token.txt)
    - Falls back to HTML mode if no credentials
    
    To enable Confluence API mode:
    1. Create config/.env with CONFLUENCE_TOKEN, CONFLUENCE_EMAIL, CONFLUENCE_BASE_URL
    2. Or use confluence_token.txt (legacy)
    
    The orchestrator will automatically select the best crawler for your site.
    """
    # Load YAML configuration first
    config = load_config()
    
    # If there are command line arguments, use them to override configuration
    if len(sys.argv) >= 2 and sys.argv[1] not in ['-h', '--help']:
        # Command line mode (backward compatibility)
        if len(sys.argv) < 2:
            print("Usage: python3 web_crawler.py <START_URL> [DEPTH] [SPACE] [FORMAT] [THREADS]")
            print("Or use config/config.yml file for advanced configuration")
            print("\nExamples:")
            print("  python3 web_crawler.py 'https://example.com/docs'")
            print("  python3 web_crawler.py 'https://example.com/wiki' 3 SPACE markdown 8")
            print("Available formats: markdown (default), html")
            print("Concurrent threads: 1-50 (default: 5)")
            sys.exit(1)
        
        start_url = sys.argv[1]
        depth = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        space = sys.argv[3] if len(sys.argv) > 3 else 'DEFAULT'
        output_format = sys.argv[4] if len(sys.argv) > 4 else 'markdown'
        max_workers = int(sys.argv[5]) if len(sys.argv) > 5 else 5
        
        # Validate format
        if output_format not in ['markdown', 'html']:
            print(f"❌ Invalid format: {output_format}. Use 'markdown' or 'html'")
            sys.exit(1)
        
        # Validate number of threads
        if max_workers < 1 or max_workers > 50:
            print(f"❌ Invalid number of threads: {max_workers}. Use between 1 and 50")
            sys.exit(1)
        
        # Create configuration from command line arguments
        if config is None:
            config = {}
        
        # Override configuration with command line arguments
        config.setdefault('website', {})['start_url'] = start_url
        config.setdefault('crawling', {})['max_depth'] = depth
        config.setdefault('crawling', {})['space_name'] = space
        config.setdefault('crawling', {})['max_workers'] = max_workers
        config.setdefault('output', {})['format'] = output_format
        
        print(f"📄 Output format: {output_format.upper()}")
        
    elif config is None:
        print("❌ Error: YAML configuration or command line arguments required")
        print("📄 Create a config/config.yml file or provide arguments")
        sys.exit(1)
    else:
        # Pure YAML configuration mode
        start_url = config.get('website', {}).get('start_url')
        if not start_url:
            print("❌ Error: start_url not defined in configuration")
            sys.exit(1)
        print(f"📄 Output format: {config.get('output', {}).get('format', 'markdown').upper()}")
    
    # Check cookies file
    cookies_file = config.get('files', {}).get('cookies_file', 'config/cookies.txt')
    if not os.path.exists(cookies_file):
        print(f"❌ Error: {cookies_file} file not found")
        print(f"📄 Copy config/cookies.template.txt to {cookies_file} and configure your cookies")
        sys.exit(1)
    
    # Check for existing content and handle user choice
    has_files, has_database = check_existing_content(config)
    if has_files or has_database:
        output_dir = config.get('output', {}).get('output_dir', 'downloaded_content')
        db_path = config.get('files', {}).get('database_file', 'crawler_data.db')
        choice = show_startup_menu(has_files, has_database, output_dir, db_path)
        handle_existing_content_choice(choice, output_dir, db_path)
    
    # Create crawler with configuration
    # Use orchestrator if available (Confluence API support), otherwise use WebCrawler directly
    if ORCHESTRATOR_AVAILABLE:
        print("🔍 Using intelligent crawler selection (Confluence API + HTML modes available)")
        orchestrator = CrawlerOrchestrator(config)
        orchestrator.run()
    else:
        print("🔍 Using HTML crawler mode")
        crawler = WebCrawler(config)
        pages_downloaded = crawler.download_recursive(start_url)
        
        max_workers = config.get('crawling', {}).get('max_workers', 5)
        output_format = config.get('output', {}).get('format', 'markdown')
        
        print(f"\n✅ Process completed: {pages_downloaded} pages downloaded in {output_format.upper()} format")
        print(f"🧵 Threads used: {max_workers}")

if __name__ == "__main__":
    main()
