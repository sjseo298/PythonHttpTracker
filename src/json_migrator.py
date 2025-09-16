#!/usr/bin/env python3
"""
JSON to SQLite Migration Utility
Converts existing JSON progress files to SQLite database format
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add src to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.database_manager import DatabaseManager
except ImportError:
    print("❌ Error: Could not import DatabaseManager. Make sure you're running from the project root.")
    sys.exit(1)

class JSONMigrator:
    """Handles migration from JSON progress files to SQLite database"""
    
    def __init__(self, db_path: str = "crawler_data.db"):
        self.db = DatabaseManager(db_path)
        self.migration_stats = {
            'urls_migrated': 0,
            'resources_migrated': 0,
            'mappings_migrated': 0,
            'queue_items_migrated': 0
        }
    
    def migrate_from_json(self, json_file: str = "download_progress.json") -> bool:
        """Migrate data from JSON file to SQLite database"""
        if not os.path.exists(json_file):
            print(f"❌ JSON file {json_file} not found")
            return False
        
        try:
            print(f"🔄 Starting migration from {json_file} to SQLite...")
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Migrate downloaded URLs
            downloaded_urls = data.get('downloaded_urls', [])
            url_to_filename = data.get('url_to_filename', {})
            
            print(f"📄 Migrating {len(downloaded_urls)} downloaded URLs...")
            for url in downloaded_urls:
                clean_url = self._clean_url(url)
                local_path = url_to_filename.get(url, "")
                
                if local_path and os.path.exists(local_path):
                    file_size = os.path.getsize(local_path)
                else:
                    file_size = None
                
                # Add to downloaded documents
                if self.db.mark_url_completed(clean_url, local_path, file_size, None, 0, 0):
                    self.migration_stats['urls_migrated'] += 1
            
            # Migrate downloaded resources
            downloaded_resources = data.get('downloaded_resources', [])
            transversal_resources = data.get('transversal_resources', {})
            
            print(f"📎 Migrating {len(downloaded_resources)} downloaded resources...")
            for resource_url in downloaded_resources:
                local_path = transversal_resources.get(resource_url, "")
                is_transversal = resource_url in transversal_resources
                
                # Determine resource type from URL
                resource_type = self._determine_resource_type(resource_url)
                
                if local_path and os.path.exists(local_path):
                    file_size = os.path.getsize(local_path)
                else:
                    file_size = None
                
                if self.db.add_downloaded_resource(
                    resource_url, local_path, resource_type, 
                    file_size, None, None, is_transversal
                ):
                    self.migration_stats['resources_migrated'] += 1
            
            # Migrate URL mappings
            print(f"🔗 Migrating {len(url_to_filename)} URL mappings...")
            for url, local_path in url_to_filename.items():
                clean_url = self._clean_url(url)
                # URL mappings are automatically created when marking URLs as completed
                self.migration_stats['mappings_migrated'] += 1
            
            # Migrate download queue
            download_queue = data.get('download_queue', [])
            print(f"📋 Migrating {len(download_queue)} queued URLs...")
            
            urls_data = []
            for item in download_queue:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    url, depth = item[0], item[1]
                    clean_url = self._clean_url(url)
                    urls_data.append((url, clean_url, depth, None))
            
            if urls_data:
                migrated_count = self.db.add_discovered_urls_batch(urls_data)
                self.migration_stats['queue_items_migrated'] = migrated_count
            
            # Backup original JSON file
            backup_file = f"{json_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(json_file, backup_file)
            print(f"📦 Original JSON file backed up as {backup_file}")
            
            self._print_migration_summary()
            return True
            
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            return False
    
    def _clean_url(self, url: str) -> str:
        """Clean URL to match the format used by WebCrawler"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def _determine_resource_type(self, url: str) -> str:
        """Determine resource type from URL"""
        url_lower = url.lower()
        
        if any(ext in url_lower for ext in ['.css']):
            return 'css'
        elif any(ext in url_lower for ext in ['.js', '.javascript']):
            return 'js'
        elif any(ext in url_lower for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico']):
            return 'image'
        elif any(ext in url_lower for ext in ['.woff', '.woff2', '.ttf', '.eot']):
            return 'font'
        else:
            return 'other'
    
    def _print_migration_summary(self):
        """Print migration summary"""
        print(f"\n✅ Migration completed successfully!")
        print(f"📊 Migration Summary:")
        print(f"   URLs migrated: {self.migration_stats['urls_migrated']}")
        print(f"   Resources migrated: {self.migration_stats['resources_migrated']}")
        print(f"   Mappings migrated: {self.migration_stats['mappings_migrated']}")
        print(f"   Queue items migrated: {self.migration_stats['queue_items_migrated']}")
        
        # Get database stats
        db_stats = self.db.get_stats()
        print(f"\n📈 Database Status:")
        print(f"   Total documents: {db_stats.get('total_documents', 0)}")
        print(f"   Total resources: {db_stats.get('total_resources', 0)}")
        print(f"   URLs by status: {db_stats.get('urls_by_status', {})}")

def auto_migrate_if_needed(db_path: str = "crawler_data.db", json_file: str = "download_progress.json") -> bool:
    """Automatically migrate if JSON exists but database doesn't"""
    if os.path.exists(json_file) and not os.path.exists(db_path):
        print(f"🔄 Found existing JSON progress file. Migrating to SQLite...")
        migrator = JSONMigrator(db_path)
        return migrator.migrate_from_json(json_file)
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate JSON progress to SQLite database")
    parser.add_argument('--json-file', '-j', default='download_progress.json',
                        help='JSON file to migrate from (default: download_progress.json)')
    parser.add_argument('--db-path', '-d', default='crawler_data.db',
                        help='SQLite database path (default: crawler_data.db)')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Force migration even if database exists')
    
    args = parser.parse_args()
    
    # Check if migration is needed
    if os.path.exists(args.db_path) and not args.force:
        print(f"❌ Database {args.db_path} already exists. Use --force to overwrite.")
        sys.exit(1)
    
    # Perform migration
    migrator = JSONMigrator(args.db_path)
    success = migrator.migrate_from_json(args.json_file)
    
    if success:
        print("🎉 Migration completed successfully!")
        sys.exit(0)
    else:
        print("❌ Migration failed!")
        sys.exit(1)