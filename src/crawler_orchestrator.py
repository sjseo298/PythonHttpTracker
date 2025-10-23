#!/usr/bin/env python3
"""
Crawler Orchestrator
Detects site type and selects the appropriate crawler (Confluence API or HTML)
"""
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

try:
    from confluence_auth import ConfluenceAuth
    from confluence_api_crawler import ConfluenceAPICrawler
    from database_manager import DatabaseManager
    from progress_tracker import ProgressTracker
except ImportError:
    from src.confluence_auth import ConfluenceAuth
    from src.confluence_api_crawler import ConfluenceAPICrawler
    from src.database_manager import DatabaseManager
    from src.progress_tracker import ProgressTracker


class CrawlerOrchestrator:
    """
    Coordinates the selection and execution of the appropriate crawler
    based on site type and credential availability
    """
    
    def __init__(self, config: dict):
        """
        Initialize the orchestrator
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.start_url = config.get('website', {}).get('start_url', '')
        self.base_url = config.get('website', {}).get('base_url', '')
        
        # Try to load Confluence authentication
        self.auth = self._load_confluence_auth()
        
        # Initialize shared components
        db_path = config.get('files', {}).get('database_file', 'crawler_data.db')
        self.db = DatabaseManager(db_path)
        self.progress_tracker = ProgressTracker()
    
    def _load_confluence_auth(self) -> Optional[ConfluenceAuth]:
        """
        Attempt to load Confluence authentication credentials
        
        Returns:
            ConfluenceAuth instance if credentials found, None otherwise
        """
        try:
            auth = ConfluenceAuth()
            if auth.is_valid():
                return auth
            else:
                return None
        except Exception as e:
            print(f"⚠️  Could not load Confluence credentials: {e}")
            return None
    
    def detect_site_type(self) -> str:
        """
        Detect if the target site is Confluence or generic HTML
        
        Returns:
            'confluence' if Confluence detected, 'html' otherwise
        """
        # Check configuration override
        confluence_config = self.config.get('website', {}).get('confluence', {})
        is_confluence_override = confluence_config.get('is_confluence', 'auto')
        
        if is_confluence_override == True or is_confluence_override == 'true':
            return 'confluence'
        elif is_confluence_override == False or is_confluence_override == 'false':
            return 'html'
        
        # Auto-detect based on URL patterns
        if self._is_confluence_url(self.start_url) or self._is_confluence_url(self.base_url):
            return 'confluence'
        
        return 'html'
    
    def _is_confluence_url(self, url: str) -> bool:
        """
        Check if URL matches Confluence patterns
        
        Args:
            url: URL to check
            
        Returns:
            True if Confluence URL detected
        """
        if not url:
            return False
        
        confluence_patterns = [
            r'\.atlassian\.net',
            r'/wiki/',
            r'/confluence/',
            r'/display/',
            r'/pages/',
            r'/rest/api/content/'
        ]
        
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in confluence_patterns)
    
    def should_use_api_crawler(self) -> bool:
        """
        Determine if Confluence API crawler should be used
        
        Returns:
            True if API crawler should be used
        """
        # Check if site is Confluence
        if self.detect_site_type() != 'confluence':
            return False
        
        # Check configuration
        confluence_config = self.config.get('website', {}).get('confluence', {})
        use_api = confluence_config.get('use_api', 'auto')
        
        # Explicit configuration
        if use_api == 'true' or use_api == True:
            if not self.auth or not self.auth.is_valid():
                raise ValueError(
                    "❌ Confluence API mode is required but credentials are not configured.\n"
                    "   Please create a .env file or confluence_token.txt with your credentials."
                )
            return True
        elif use_api == 'false' or use_api == False:
            return False
        
        # Auto mode: use API if credentials available
        return self.auth is not None and self.auth.is_valid()
    
    def create_crawler(self):
        """
        Create and return the appropriate crawler instance
        
        Returns:
            Crawler instance (ConfluenceAPICrawler or WebCrawler)
        """
        if self.should_use_api_crawler():
            print("\n🚀 Using Confluence API Crawler")
            print("   Mode: REST API with full metadata")
            print(f"   Base URL: {self.auth.base_url}")
            print(f"   API Base: {self.auth.get_api_base_url()}")
            print()
            
            return ConfluenceAPICrawler(
                config=self.config,
                auth=self.auth,
                db=self.db,
                progress_tracker=self.progress_tracker
            )
        else:
            print("\n🚀 Using HTML Crawler")
            print("   Mode: HTTP requests with HTML parsing")
            
            # Check if it's Confluence without API access
            if self.detect_site_type() == 'confluence':
                print("   ⚠️  Confluence detected but no API credentials found")
                print("   Falling back to HTML mode (limited metadata)")
                print("   To use API mode, create .env with credentials")
            
            print()
            
            # Import and use the existing WebCrawler
            try:
                from web_crawler import WebCrawler
            except ImportError:
                from src.web_crawler import WebCrawler
            
            # WebCrawler already has its own db and progress tracker
            # So we create it without passing our instances
            return WebCrawler(config=self.config)
    
    def run(self):
        """
        Execute the selected crawler
        """
        print("="*70)
        print("🕷️  WEB CRAWLER - Starting")
        print("="*70)
        
        # Detect and report site type
        site_type = self.detect_site_type()
        print(f"\n🔍 Site Type Detected: {site_type.upper()}")
        
        if site_type == 'confluence':
            if self.auth and self.auth.is_valid():
                print("✅ Confluence API credentials found")
                print(f"   Email: {self.auth.email}")
            else:
                print("⚠️  No Confluence API credentials (using HTML mode)")
        
        # Create the appropriate crawler
        crawler = self.create_crawler()
        
        # Run the crawler
        try:
            crawler.crawl()
            print("\n✅ Crawling completed successfully!")
        except KeyboardInterrupt:
            print("\n\n⚠️  Crawling interrupted by user")
            print("   Progress has been saved to the database")
        except Exception as e:
            print(f"\n\n❌ Crawling failed with error: {e}")
            raise
        finally:
            if hasattr(crawler, 'db'):
                crawler.db.close()
    
    @staticmethod
    def print_configuration_help():
        """
        Print help information about configuration options
        """
        help_text = """
╔══════════════════════════════════════════════════════════════════════╗
║                 CONFLUENCE API CONFIGURATION HELP                     ║
╚══════════════════════════════════════════════════════════════════════╝

The crawler can automatically detect Confluence sites and use the API
if credentials are available.

📁 CREDENTIAL CONFIGURATION
──────────────────────────────────────────────────────────────────────

Option 1: .env file (Recommended)
  Location: config/.env or .env
  Contents:
    CONFLUENCE_BASE_URL=https://your-domain.atlassian.net
    CONFLUENCE_EMAIL=your-email@example.com
    CONFLUENCE_TOKEN=your-api-token-here

Option 2: confluence_token.txt (Legacy)
  Location: confluence_token.txt
  Contents: Just your API token
  Note: Email and base_url must be in config.yml

🔧 CRAWLER MODE SELECTION
──────────────────────────────────────────────────────────────────────

The crawler selects the mode automatically:

1. Confluence + API credentials → ConfluenceAPICrawler
   - Full metadata (versions, authors, dates)
   - Attachment downloads
   - YAML metadata files
   - JSON API responses

2. Confluence without credentials → HTMLCrawler
   - Basic HTML download
   - Limited metadata
   - No attachments

3. Non-Confluence site → HTMLCrawler
   - Standard web crawling
   - HTML/Markdown output

⚙️  CONFIGURATION OVERRIDE
──────────────────────────────────────────────────────────────────────

In config.yml, you can force a specific mode:

website:
  confluence:
    is_confluence: auto  # auto | true | false
    use_api: auto        # auto | true | false

Examples:
  - is_confluence: true, use_api: true
    → Forces API mode (fails if no credentials)
  
  - is_confluence: true, use_api: false
    → Forces HTML mode even with credentials
  
  - is_confluence: auto, use_api: auto
    → Automatic detection (recommended)

🔑 GETTING AN API TOKEN
──────────────────────────────────────────────────────────────────────

1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a name (e.g., "Web Crawler")
4. Copy the token
5. Add to .env file

📚 MORE INFORMATION
──────────────────────────────────────────────────────────────────────

See: docs/DESIGN_CONFLUENCE_API_INTEGRATION.md

╚══════════════════════════════════════════════════════════════════════╝
"""
        print(help_text)


if __name__ == "__main__":
    print("Crawler Orchestrator")
    print("=" * 70)
    print()
    print("This module coordinates crawler selection based on site type")
    print("and credential availability.")
    print()
    
    CrawlerOrchestrator.print_configuration_help()
