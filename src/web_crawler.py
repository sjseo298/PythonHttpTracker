#!/usr/bin/env python3
"""
Recursive web crawler that respects depth limits and converts links to local references
"""
import os
import re
import sys
import time
import json
import urllib.parse
from pathlib import Path
from collections import deque
from urllib.parse import urljoin, urlparse, unquote
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
    import yaml
except ImportError as e:
    print(f"❌ Error: Missing required dependency: {e}")
    print("Please install dependencies using:")
    print("  pip install requests beautifulsoup4 markdownify pyyaml")
    print("Or run the setup wizard: ./setup_wizard.sh")
    sys.exit(1)

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
        self.progress_file = self.config.get('files', {}).get('progress_file', 'download_progress.json')
        
        # Internal state
        self.session = requests.Session()
        self.downloaded_urls = set()
        self.downloaded_resources = set()
        self.transversal_resources = {}
        self.url_to_filename = {}
        self.download_queue = deque()
        
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
        
        # Load previous progress if it exists
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
        """Loads previous download progress"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.downloaded_urls = set(data.get('downloaded_urls', []))
                    self.url_to_filename = data.get('url_to_filename', {})
                    self.downloaded_resources = set(data.get('downloaded_resources', []))
                    self.transversal_resources = data.get('transversal_resources', {})
                    # Load download queue as well
                    saved_queue = data.get('download_queue', [])
                    self.download_queue = deque(saved_queue)
                print(f"✓ Progress loaded: {len(self.downloaded_urls)} URLs already downloaded, {len(self.download_queue)} pending")
        except Exception as e:
            print(f"❌ Error loading progress: {e}")

    def save_progress(self):
        """Saves current download progress"""
        try:
            data = {
                'downloaded_urls': list(self.downloaded_urls),
                'url_to_filename': self.url_to_filename,
                'downloaded_resources': list(self.downloaded_resources),
                'transversal_resources': self.transversal_resources,
                'download_queue': list(self.download_queue)  # Guardar la cola también
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Error saving progress: {e}")

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
            print(f"{'  ' * (self.max_depth - depth)}🔄 Already downloaded: {Path(self.url_to_filename[clean_url]).name}")
            return None
        
        print(f"{'  ' * (self.max_depth - depth)}[Depth {depth}] Downloading: {clean_url}")
        
        try:
            response = self.session.get(clean_url, timeout=30)
            response.raise_for_status()
            
            # Create local directory
            local_path = self.url_to_local_path(clean_url)
            full_path = Path(local_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Process content before saving
            processed_content = self.process_content(response.text, clean_url, str(full_path))
            
            # Save file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            
            self.downloaded_urls.add(clean_url)
            self.url_to_filename[clean_url] = str(full_path)
            
            # Save progress after each download
            self.save_progress()
            
            print(f"{'  ' * (self.max_depth - depth)}✓ Saved: {local_path}")
            
            # If depth is greater than 0, extract and queue links
            if depth > 0:
                print(f"{'  ' * (self.max_depth - depth)}📋 Extracting links (next depth: {depth-1})")
                links = self.extract_links(response.text, clean_url)
                new_links_count = 0
                for link in links:
                    if link not in self.downloaded_urls:
                        self.download_queue.append((link, depth - 1))
                        new_links_count += 1
                print(f"{'  ' * (self.max_depth - depth)}🔗 Added {new_links_count} links to queue")
            else:
                print(f"{'  ' * (self.max_depth - depth)}🛑 Depth 0 reached - no more links followed")
            
            return response.text
            
        except Exception as e:
            print(f"{'  ' * (self.max_depth - depth)}❌ Error downloading {url}: {e}")
            return None

    def download_url_parallel(self, url_depth_pair):
        """Thread-safe function to download an individual URL in parallel"""
        url, depth = url_depth_pair
        clean_url = self.clean_url(url)
        
        # Try to acquire exclusive lock for this URL
        if not self.acquire_url_lock(clean_url):
            return None  # Already being processed or already downloaded
        
        try:
            # Create a new session for this thread (thread-safe)
            local_session = requests.Session()
            local_session.cookies.update(self.session.cookies)
            local_session.headers.update(self.session.headers)
            
            # Perform the download
            response = local_session.get(clean_url, timeout=30)
            response.raise_for_status()
            
            # Generate local path
            local_path = self.url_to_local_path(clean_url)
            full_path = Path(local_path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Process content (this includes cleaning JS, updating links and downloading resources)
            processed_content = self.process_content(response.text, clean_url, str(full_path))
            
            # Save the processed file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            
            # Thread-safe state update
            with self.download_lock:
                self.downloaded_urls.add(clean_url)
                self.url_to_filename[clean_url] = str(full_path)
            
            # Thread-safe progress save
            with self.progress_lock:
                self.save_progress()
            
            print(f"{'  ' * (self.max_depth - depth)}✓ Saved: {local_path}")
            
            # If depth is greater than 0, extract and queue links
            if depth > 0:
                print(f"{'  ' * (self.max_depth - depth)}📋 Extracting links (next depth: {depth-1})")
                links = self.extract_links(response.text, clean_url)
                
                # Thread-safe addition to queue
                with self.queue_lock:
                    new_links_count = 0
                    for link in links:
                        # Check if already downloaded or in process
                        if link not in self.downloaded_urls and link not in self.active_downloads:
                            self.download_queue.append((link, depth - 1))
                            new_links_count += 1
                
                if new_links_count > 0:
                    print(f"{'  ' * (self.max_depth - depth)}🔗 Added {new_links_count} links to queue")
            else:
                print(f"{'  ' * (self.max_depth - depth)}🛑 Depth 0 reached - no more links followed")
            
            return response.text
            
        except Exception as e:
            print(f"{'  ' * (self.max_depth - depth)}❌ Error downloading {url}: {e}")
            return None
        finally:
            # Always release the lock
            self.release_url_lock(clean_url)

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
            
            # Download resources (CSS, images)
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
        # Try to acquire exclusive lock for this resource
        if not self.acquire_resource_lock(url):
            # If already being processed or already downloaded, find existing file
            if url in self.transversal_resources:
                existing_file = Path(self.transversal_resources[url])
                if existing_file.exists():
                    print(f"{'  ' * (self.max_depth - 0)}📎 Transversal resource already downloaded: {existing_file.name}")
                    return str(existing_file)
            return None
        
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
                
                # Thread-safe update
                with self.resource_lock:
                    self.downloaded_resources.add(url)
                    if self.is_transversal_resource(url):
                        self.transversal_resources[url] = str(file_path)
                
                return str(file_path)
            
            # Create a new session for thread-safety
            local_session = requests.Session()
            local_session.cookies.update(self.session.cookies)
            local_session.headers.update(self.session.headers)
            
            response = local_session.get(url, timeout=30)
            response.raise_for_status()
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            # Thread-safe state update
            with self.resource_lock:
                self.downloaded_resources.add(url)
                if self.is_transversal_resource(url):
                    self.transversal_resources[url] = str(file_path)
                    print(f"{'  ' * (self.max_depth - 0)}📎 Transversal resource saved: {filename}")
                else:
                    print(f"{'  ' * (self.max_depth - 0)}📎 Specific resource saved: {filename}")
                
            return str(file_path)
            
        except Exception as e:
            print(f"❌ Error downloading resource {url}: {e}")
            return None
        finally:
            # Always release the resource lock
            self.release_resource_lock(url)

    def download_recursive(self, start_url):
        """Recursively downloads from the initial URL using parallelism"""
        print(f"=== Starting recursive download (max depth: {self.max_depth}) ===")
        print(f"Initial URL: {start_url}")
        print(f"Space: {self.space}")
        print(f"🧵 Concurrent threads: {self.max_workers}")
        print()
        
        # Clean initial URL for consistency
        parsed = urlparse(start_url)
        clean_start_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # Only add initial URL to queue if no queue loaded and not already downloaded
        if not self.download_queue and clean_start_url not in self.downloaded_urls:
            self.download_queue.append((clean_start_url, self.max_depth))
        elif self.download_queue:
            print(f"📂 Resuming download with {len(self.download_queue)} pending pages")
        
        # Process download queue with parallelism
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while self.download_queue:
                # Take a batch of URLs to process in parallel
                current_batch = []
                batch_size = min(self.max_workers, len(self.download_queue))
                
                for _ in range(batch_size):
                    if self.download_queue:
                        current_batch.append(self.download_queue.popleft())
                
                if not current_batch:
                    break
                
                print(f"\n--- Processing batch of {len(current_batch)} pages (Remaining queue: {len(self.download_queue)}) ---")
                
                # Submit jobs to thread pool
                future_to_url = {
                    executor.submit(self.download_url_parallel, url_depth): url_depth 
                    for url_depth in current_batch
                }
                
                # Wait for all batch jobs to complete
                for future in as_completed(future_to_url):
                    url_depth = future_to_url[future]
                    try:
                        result = future.result()
                    except Exception as exc:
                        print(f"❌ Error in parallel download {url_depth[0]}: {exc}")
                
                # Small pause between batches to avoid overloading server
                if self.download_queue:
                    time.sleep(1)
        
        print(f"\n=== Download completed: {len(self.downloaded_urls)} pages ===")
        
        return len(self.downloaded_urls)

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

def main():
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
    
    # Create crawler with configuration
    crawler = WebCrawler(config)
    pages_downloaded = crawler.download_recursive(start_url)
    
    max_workers = config.get('crawling', {}).get('max_workers', 5)
    output_format = config.get('output', {}).get('format', 'markdown')
    
    print(f"\n✅ Process completed: {pages_downloaded} pages downloaded in {output_format.upper()} format")
    print(f"🧵 Threads used: {max_workers}")

if __name__ == "__main__":
    main()
