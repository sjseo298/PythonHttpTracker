#!/usr/bin/env python3
"""
Base Crawler Abstract Class
Defines the common interface and shared functionality for all crawler types
"""
import os
import re
import time
import threading
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from rich.live import Live

try:
    from progress_tracker import ProgressTracker
    from database_manager import DatabaseManager
except ImportError:
    from src.progress_tracker import ProgressTracker
    from src.database_manager import DatabaseManager


class BaseCrawler(ABC):
    """
    Abstract base class that defines the common interface
    for all types of web crawlers (HTML, Confluence API, etc.)
    """
    
    def __init__(self, config: dict, db: DatabaseManager = None, 
                 progress_tracker: ProgressTracker = None):
        """
        Initialize the base crawler with configuration
        
        Args:
            config: Configuration dictionary
            db: Database manager instance (optional, will create if None)
            progress_tracker: Progress tracker instance (optional, will create if None)
        """
        self.config = config
        
        # Initialize database if not provided
        db_path = self.config.get('files', {}).get('database_file', 'crawler_data.db')
        self.db = db if db else DatabaseManager(db_path)
        
        # Initialize progress tracker if not provided
        self.progress_tracker = progress_tracker if progress_tracker else ProgressTracker()
        
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
        
        # Output configuration
        self.output_format = self.config.get('output', {}).get('format', 'markdown').lower()
        self.output_dir = self.config.get('output', {}).get('output_dir', 'downloaded_content')
        
        # Internal state
        self.download_queue = deque()
        self.downloaded_urls = self.db.get_downloaded_urls()
        self.active_downloads = set()
        
        # Threading locks
        self.download_lock = threading.Lock()
        self.queue_lock = threading.Lock()
        
        # Statistics
        self.start_time = None
        self.end_time = None
        
    @abstractmethod
    def fetch_page(self, url: str, depth: int) -> dict:
        """
        Fetch a page from the given URL
        
        Args:
            url: The URL to fetch
            depth: Current depth of crawling
            
        Returns:
            dict with keys:
                - 'content': The main content (HTML, JSON response, etc.)
                - 'metadata': Dictionary with page metadata
                - 'links': List of discovered links to follow
                - 'success': Boolean indicating success
                - 'error': Error message if success=False
        """
        pass
    
    @abstractmethod
    def save_page(self, url: str, content: dict, local_path: str) -> bool:
        """
        Save the page content to disk
        
        Args:
            url: The original URL
            content: The content dict returned from fetch_page()
            local_path: Where to save the content
            
        Returns:
            True if saved successfully, False otherwise
        """
        pass
    
    def should_download(self, url: str, depth: int) -> bool:
        """
        Determine if a URL should be downloaded based on filters and depth
        
        Args:
            url: The URL to check
            depth: The depth at which this URL was discovered
            
        Returns:
            True if the URL should be downloaded
        """
        # Check depth limit
        if depth > self.max_depth:
            return False
        
        # Check if already downloaded
        if url in self.downloaded_urls:
            return False
        
        # Check if currently being downloaded
        with self.download_lock:
            if url in self.active_downloads:
                return False
        
        # Check domain
        parsed_url = urlparse(url)
        if self.base_domain and self.base_domain not in parsed_url.netloc:
            return False
        
        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if re.search(pattern, url):
                return False
        
        # Check valid patterns (if specified)
        if self.valid_url_patterns:
            matches_pattern = False
            for pattern in self.valid_url_patterns:
                if re.search(pattern, url):
                    matches_pattern = True
                    break
            if not matches_pattern:
                return False
        
        return True
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize a URL by removing fragments and standardizing format
        
        Args:
            url: The URL to normalize
            
        Returns:
            Normalized URL
        """
        parsed = urlparse(url)
        # Remove fragment
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized
    
    def generate_local_path(self, url: str, depth: int) -> Path:
        """
        Generate a local file path for storing a downloaded page
        
        Args:
            url: The URL being downloaded
            depth: The depth at which this URL was found
            
        Returns:
            Path object for the local file
        """
        parsed_url = urlparse(url)
        path_parts = [p for p in parsed_url.path.split('/') if p]
        
        # Create base directory structure
        base_path = Path(self.output_dir) / "spaces" / self.space / "pages"
        
        # Try to extract a page ID or use a sanitized path
        page_id = self._extract_page_identifier(url)
        
        if page_id:
            page_dir = base_path / page_id
        else:
            # Use the last part of the path or generate a hash
            if path_parts:
                page_dir = base_path / path_parts[-1]
            else:
                # Use a hash of the URL
                import hashlib
                url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
                page_dir = base_path / f"page_{url_hash}"
        
        page_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine file extension
        extension = '.md' if self.output_format == 'markdown' else '.html'
        
        return page_dir / f"index{extension}"
    
    def _extract_page_identifier(self, url: str) -> str:
        """
        Extract a page identifier from the URL (e.g., page ID)
        
        Args:
            url: The URL to extract from
            
        Returns:
            Page identifier or empty string if not found
        """
        # Try to find numeric IDs in the URL
        # This works for patterns like /pages/123456/ or ?pageId=123456
        patterns = [
            r'/pages/(\d+)',
            r'pageId=(\d+)',
            r'/(\d{6,})',  # Any 6+ digit number in path
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return ''
    
    def crawl(self):
        """
        Main crawling method that processes URLs from the queue
        This method is shared by all crawler implementations
        """
        self.start_time = datetime.now()
        print(f"\n🚀 Starting crawl from: {self.start_url}")
        print(f"📊 Max depth: {self.max_depth}")
        print(f"🧵 Max workers: {self.max_workers}")
        print(f"💾 Output directory: {self.output_dir}")
        print(f"📁 Output format: {self.output_format}")
        print()
        
        # Initialize progress tracker
        self.progress_tracker.initialize_progress_bar(initial_total=1)
        
        # Load pending URLs from database (for resume capability)
        pending_urls = self.db.get_pending_urls()
        if pending_urls:
            print(f"🔄 Found {len(pending_urls)} pending URLs from previous session")
            
            # Load stats from database
            total_discovered = self.db.get_total_discovered_urls()
            total_downloaded = self.db.get_total_downloaded_documents()
            total_failed = self.db.get_total_failed_urls()
            
            print(f"📊 Database progress: {total_downloaded} downloaded, {total_failed} failed, {len(pending_urls)} pending")
            
            # Update progress tracker with existing stats
            self.progress_tracker.update_stat('urls_discovered', value=total_discovered)
            self.progress_tracker.update_stat('urls_downloaded', value=total_downloaded)
            self.progress_tracker.update_stat('urls_failed', value=total_failed)
            
            # Add pending URLs to queue
            for url, depth in pending_urls:
                self.download_queue.append((url, depth))
            self.progress_tracker.update_stat('urls_queued', value=len(pending_urls))
            
            # Force progress bar update with correct totals
            self.progress_tracker.update_progress_bar()
        else:
            # Add start URL to queue only if no pending URLs
            self.download_queue.append((self.start_url, 0))
            self.progress_tracker.update_stat('urls_queued', value=1)
            
            # Add to discovered URLs in database
            normalized_start = self.normalize_url(self.start_url)
            self.db.add_discovered_url(self.start_url, normalized_start, 0)
            self.progress_tracker.update_stat('urls_discovered')
        
        # Process queue with thread pool and live progress display
        with Live(self.progress_tracker.create_progress_panel(), refresh_per_second=2) as live:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                
                while True:
                    # Submit new jobs while queue has items and we're not at max capacity
                    while self.download_queue and len(futures) < self.max_workers:
                        with self.queue_lock:
                            if self.download_queue:
                                url, depth = self.download_queue.popleft()
                                self.progress_tracker.update_stat('urls_queued', increment=-1)
                            else:
                                break
                    
                        # Check if should download
                        if not self.should_download(url, depth):
                            continue
                    
                        # Mark as active
                        with self.download_lock:
                            self.active_downloads.add(url)
                    
                        # Submit download task
                        future = executor.submit(self._process_url, url, depth)
                        futures[future] = (url, depth, time.time())
                        self.progress_tracker.update_stat('active_threads', value=len(futures))
                        live.update(self.progress_tracker.create_progress_panel())
                
                    # Check for completed futures
                    completed = []
                    for future in list(futures.keys()):
                        if future.done():
                            completed.append(future)
                
                    # Process completed futures
                    for future in completed:
                        url, depth, start_time = futures.pop(future)
                    
                        try:
                            result = future.result(timeout=1)
                        
                            # Update progress
                            with self.download_lock:
                                self.active_downloads.discard(url)
                        
                            if result['success']:
                                # Only count as downloaded if not a space index
                                is_space_index = result.get('is_space_index', False)
                                if not is_space_index:
                                    self.progress_tracker.update_stat('urls_downloaded')
                            
                                # Add discovered links to queue
                                # For space index, always add links regardless of depth
                                # For regular pages, respect max_depth
                                should_add_links = is_space_index or (result.get('links') and depth < self.max_depth)
                                
                                if should_add_links and result.get('links'):
                                    new_links = 0
                                    # For space index, start at depth 0, otherwise depth + 1
                                    next_depth = 0 if is_space_index else depth + 1
                                    
                                    for link in result['links']:
                                        normalized_link = self.normalize_url(link)
                                        if normalized_link not in self.downloaded_urls:
                                            with self.queue_lock:
                                                self.download_queue.append((link, next_depth))
                                            self.progress_tracker.update_stat('urls_queued', increment=1)
                                        
                                            # Add to discovered URLs
                                            self.db.add_discovered_url(link, normalized_link, next_depth, parent_url=url)
                                            self.progress_tracker.update_stat('urls_discovered')
                                            new_links += 1
                                
                                # Update live display after processing links
                                live.update(self.progress_tracker.create_progress_panel())
                            else:
                                self.progress_tracker.update_stat('urls_failed')
                                # Update live display after failure
                                live.update(self.progress_tracker.create_progress_panel())
                    
                        except Exception as e:
                            self.progress_tracker.update_stat('urls_failed')
                            self.progress_tracker.update_stat('last_error', value=str(e))
                            with self.download_lock:
                                self.active_downloads.discard(url)
                            # Update live display after error
                            live.update(self.progress_tracker.create_progress_panel())
                    
                        self.progress_tracker.update_stat('active_threads', value=len(futures))
                        # Update live display after active threads change
                        live.update(self.progress_tracker.create_progress_panel())
                
                    # Exit condition: no more futures and queue is empty
                    if not futures and not self.download_queue:
                        break
                
                    # Small delay to avoid busy waiting
                    time.sleep(0.1)
        
        self.end_time = datetime.now()
        self._print_final_summary()
    
    def _process_url(self, url: str, depth: int) -> dict:
        """
        Process a single URL (fetch and save)
        
        Args:
            url: The URL to process
            depth: Current depth
            
        Returns:
            Result dictionary with success status and links
        """
        self.progress_tracker.update_stat('last_url', value=url)
        self.progress_tracker.update_stat('current_depth', value=depth)
        
        try:
            # Fetch the page
            content = self.fetch_page(url, depth)
            
            if not content.get('success', False):
                return {
                    'success': False,
                    'error': content.get('error', 'Unknown error'),
                    'links': []
                }
            
            # Generate local path
            local_path = self.generate_local_path(url, depth)
            
            # Save the page
            save_success = self.save_page(url, content, str(local_path))
            
            if save_success:
                # Don't mark as downloaded if this is a space index (just for link discovery)
                is_space_index = content.get('is_space_index', False)
                
                if not is_space_index:
                    # Mark as downloaded
                    self.downloaded_urls.add(self.normalize_url(url))
                    
                    # Update database
                    self.db.mark_url_completed(
                        clean_url=self.normalize_url(url),
                        local_path=str(local_path),
                        file_size=local_path.stat().st_size if local_path.exists() else 0
                    )
                
                return {
                    'success': True,
                    'is_space_index': content.get('is_space_index', False),  # Propagate the flag
                    'links': content.get('links', []),
                    'local_path': str(local_path)
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to save page',
                    'links': []
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'links': []
            }
    
    def _print_final_summary(self):
        """Print final crawling summary"""
        duration = (self.end_time - self.start_time).total_seconds()
        
        print("\n" + "="*70)
        print("📊 CRAWLING COMPLETED")
        print("="*70)
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"✅ URLs Downloaded: {self.progress_tracker.stats['urls_downloaded']}")
        print(f"❌ URLs Failed: {self.progress_tracker.stats['urls_failed']}")
        print(f"📎 Resources Downloaded: {self.progress_tracker.stats['resources_downloaded']}")
        print(f"🏃 Average Speed: {self.progress_tracker.stats['pages_per_second']:.2f} pages/second")
        print(f"📊 Success Rate: {self.progress_tracker.get_success_rate():.1f}%")
        print(f"💾 Output Directory: {self.output_dir}")
        print("="*70 + "\n")
