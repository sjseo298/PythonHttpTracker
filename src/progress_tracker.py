#!/usr/bin/env python3
"""
Progress Tracker for Web Crawler
Real-time progress tracking and display using Rich library
"""
import threading
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TaskProgressColumn, TextColumn
from rich.columns import Columns
from rich.console import Group


class ProgressTracker:
    """Real-time progress tracking and display for web crawler"""
    
    def __init__(self, console=None):
        self.console = console or Console()
        self.start_time = datetime.now()
        
        # Statistics
        self.stats = {
            'urls_discovered': 0,
            'urls_downloaded': 0,
            'urls_failed': 0,
            'urls_queued': 0,
            'resources_downloaded': 0,
            'resources_failed': 0,
            'total_size': 0,
            'current_depth': 0,
            'active_threads': 0,
            'last_url': '',
            'last_error': '',
            'pages_per_second': 0.0,
            'errors_count': 0
        }
        
        # Progress bar for URLs
        self.progress = Progress(
            TextColumn("[bold blue]Downloading URLs"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TextColumn("({task.completed} of {task.total})"),
            console=self.console,
            expand=False
        )
        self.url_task = None
        
        # Threading
        self.stats_lock = threading.Lock()
        self.update_interval = 0.5  # Update every 500ms
        
    def update_stat(self, key, value=None, increment=1):
        """Thread-safe update of statistics"""
        with self.stats_lock:
            if value is not None:
                self.stats[key] = value
            else:
                self.stats[key] += increment
                
            # Calculate pages per second
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed > 0:
                self.stats['pages_per_second'] = self.stats['urls_downloaded'] / elapsed
            
            # Update progress bar if URLs were discovered or downloaded
            if key in ['urls_discovered', 'urls_downloaded'] and self.url_task is not None:
                self.update_progress_bar()
    
    def initialize_progress_bar(self, initial_total=1):
        """Initialize the progress bar with initial total"""
        with self.stats_lock:
            if self.url_task is None:
                self.url_task = self.progress.add_task("URLs", total=initial_total, completed=0)
    
    def update_progress_bar(self):
        """Update the progress bar with current stats"""
        if self.url_task is not None:
            total_urls = max(self.stats['urls_discovered'] + self.stats['urls_queued'], 1)
            completed_urls = self.stats['urls_downloaded'] + self.stats['urls_failed']
            
            # Update the task with new total and completed values
            self.progress.update(self.url_task, total=total_urls, completed=completed_urls)

    def create_stats_table(self):
        """Create the statistics table"""
        table = Table(show_header=True, header_style="bold blue", show_lines=True)
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="green", width=15)
        table.add_column("Details", style="yellow", width=40)
        
        # Calculate elapsed time
        elapsed = datetime.now() - self.start_time
        elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds
        
        # Calculate ETA (rough estimate)
        if self.stats['pages_per_second'] > 0 and self.stats['urls_queued'] > 0:
            eta_seconds = self.stats['urls_queued'] / self.stats['pages_per_second']
            eta = timedelta(seconds=int(eta_seconds))
            eta_str = str(eta)
        else:
            eta_str = "Calculating..."
        
        # Format file size
        size_mb = self.stats['total_size'] / (1024 * 1024) if self.stats['total_size'] > 0 else 0
        
        # Add rows to table
        table.add_row("🔍 URLs Discovered", str(self.stats['urls_discovered']), f"Total found: {self.stats['urls_discovered']}")
        table.add_row("✅ URLs Downloaded", str(self.stats['urls_downloaded']), f"Success rate: {self.get_success_rate():.1f}%")
        table.add_row("❌ URLs Failed", str(self.stats['urls_failed']), f"Errors: {self.stats['urls_failed']}")
        table.add_row("⏳ URLs Queued", str(self.stats['urls_queued']), f"Pending download")
        table.add_row("📎 Resources", str(self.stats['resources_downloaded']), f"CSS, images, etc.")
        table.add_row("📊 Total Size", f"{size_mb:.1f} MB", f"Downloaded content")
        table.add_row("🏃 Speed", f"{self.stats['pages_per_second']:.2f}/s", f"Pages per second")
        table.add_row("⏱️  Elapsed", elapsed_str, f"ETA: {eta_str}")
        table.add_row("📍 Current Depth", str(self.stats['current_depth']), f"Max depth crawling")
        table.add_row("🧵 Active Threads", str(self.stats['active_threads']), f"Concurrent downloads")
        
        # Show last URL but truncate if too long
        last_url_display = self.stats['last_url']
        if len(last_url_display) > 50:
            last_url_display = last_url_display[:47] + "..."
        table.add_row("🔗 Last URL", last_url_display, "Currently processing")
        
        return table
    
    def get_success_rate(self):
        """Calculate success rate percentage"""
        total = self.stats['urls_downloaded'] + self.stats['urls_failed']
        if total == 0:
            return 100.0
        return (self.stats['urls_downloaded'] / total) * 100
    
    def create_progress_panel(self):
        """Create the main progress panel with table and progress bar"""
        # Create the statistics table
        table = self.create_stats_table()
        
        # Create title with status
        if self.stats['urls_queued'] > 0:
            status = f"🔄 CRAWLING IN PROGRESS"
        elif self.stats['urls_failed'] > self.stats['urls_downloaded']:
            status = f"⚠️  CRAWLING WITH ERRORS"
        else:
            status = f"✅ CRAWLING COMPLETED"
        
        # Update progress bar
        if self.url_task is not None:
            self.update_progress_bar()
        
        # Create progress bar renderable
        progress_renderable = self.progress
        
        # Combine table and progress bar
        combined_content = Columns([table], expand=True)
        
        # Create layout with progress bar above the table
        content_group = Group(
            progress_renderable,
            "",  # Empty line for spacing
            combined_content
        )
            
        return Panel(
            content_group,
            title=f"[bold green]{status}[/bold green]",
            border_style="green",
            padding=(1, 2)
        )
