#!/usr/bin/env python3
"""
Database Reporter - Generate statistics and reports from crawler database
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.database_manager import DatabaseManager
except ImportError:
    print("❌ Error: Could not import DatabaseManager. Make sure you're running from the project root.")
    sys.exit(1)

class CrawlerReporter:
    """Generates reports and statistics from crawler database"""
    
    def __init__(self, db_path: str = "crawler_data.db"):
        if not os.path.exists(db_path):
            print(f"❌ Database {db_path} not found")
            sys.exit(1)
        
        self.db = DatabaseManager(db_path)
        self.db_path = db_path
    
    def generate_summary_report(self) -> dict:
        """Generate a comprehensive summary report"""
        stats = self.db.get_stats()
        
        print("=" * 60)
        print("🚀 WEB CRAWLER DATABASE REPORT")
        print("=" * 60)
        print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💾 Database: {self.db_path}")
        print(f"📊 Size: {self._get_db_size()}")
        print()
        
        # URL Status Summary
        print("📋 URL STATUS SUMMARY")
        print("-" * 30)
        urls_by_status = stats.get('urls_by_status', {})
        total_urls = sum(urls_by_status.values())
        
        if total_urls > 0:
            for status, count in urls_by_status.items():
                percentage = (count / total_urls) * 100
                print(f"   {status.capitalize():12}: {count:6,} ({percentage:5.1f}%)")
            print(f"   {'Total':12}: {total_urls:6,}")
        else:
            print("   No URLs found in database")
        print()
        
        # Download Summary
        print("📁 DOWNLOAD SUMMARY")
        print("-" * 30)
        print(f"   Documents: {stats.get('total_documents', 0):,}")
        print(f"   Resources: {stats.get('total_resources', 0):,}")
        print()
        
        # Size Summary
        print("💾 SIZE SUMMARY")
        print("-" * 30)
        doc_size = stats.get('total_documents_size', 0)
        res_size = stats.get('total_resources_size', 0)
        total_size = doc_size + res_size
        
        print(f"   Documents: {self._format_bytes(doc_size)}")
        print(f"   Resources: {self._format_bytes(res_size)}")
        print(f"   Total:     {self._format_bytes(total_size)}")
        print()
        
        return stats
    
    def generate_detailed_report(self):
        """Generate detailed report with breakdowns"""
        print("📊 DETAILED BREAKDOWN")
        print("-" * 30)
        
        # Resource types breakdown
        self._report_resource_types()
        print()
        
        # Recent activity
        self._report_recent_activity()
        print()
        
        # Failed URLs
        self._report_failed_urls()
        print()
    
    def _report_resource_types(self):
        """Report breakdown by resource types"""
        import sqlite3
        
        with self.db.db_lock:
            conn = sqlite3.connect(self.db.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT resource_type, COUNT(*), SUM(file_size) 
                    FROM downloaded_resources 
                    GROUP BY resource_type 
                    ORDER BY COUNT(*) DESC
                """)
                
                results = cursor.fetchall()
                if results:
                    print("🎨 RESOURCE TYPES")
                    print("   Type      Count     Size")
                    print("   " + "-" * 25)
                    for resource_type, count, total_size in results:
                        size_str = self._format_bytes(total_size or 0)
                        print(f"   {resource_type:8} {count:6,} {size_str:>10}")
                else:
                    print("🎨 No resources found")
                    
            finally:
                conn.close()
    
    def _report_recent_activity(self, days: int = 7):
        """Report recent activity"""
        import sqlite3
        
        with self.db.db_lock:
            conn = sqlite3.connect(self.db.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DATE(downloaded_at) as date, COUNT(*) 
                    FROM downloaded_documents 
                    WHERE downloaded_at >= datetime('now', '-{} days')
                    GROUP BY DATE(downloaded_at) 
                    ORDER BY date DESC
                """.format(days))
                
                results = cursor.fetchall()
                if results:
                    print(f"📅 RECENT ACTIVITY (Last {days} days)")
                    print("   Date        Downloads")
                    print("   " + "-" * 20)
                    for date, count in results:
                        print(f"   {date:10} {count:6,}")
                else:
                    print(f"📅 No activity in the last {days} days")
                    
            finally:
                conn.close()
    
    def _report_failed_urls(self, limit: int = 10):
        """Report failed URLs"""
        import sqlite3
        
        with self.db.db_lock:
            conn = sqlite3.connect(self.db.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT clean_url, error_message, retry_count 
                    FROM discovered_urls 
                    WHERE status = 'failed' 
                    ORDER BY retry_count DESC, discovered_at DESC 
                    LIMIT ?
                """, (limit,))
                
                results = cursor.fetchall()
                if results:
                    print(f"❌ FAILED URLS (Top {limit})")
                    print("   Retries  URL")
                    print("   " + "-" * 50)
                    for url, error, retries in results:
                        print(f"   {retries:6}   {url[:60]}...")
                        if error:
                            print(f"            Error: {error[:50]}...")
                else:
                    print("✅ No failed URLs found")
                    
            finally:
                conn.close()
    
    def export_url_list(self, filename: str = "crawled_urls.txt", status: str = "completed"):
        """Export list of URLs with specific status"""
        import sqlite3
        
        with self.db.db_lock:
            conn = sqlite3.connect(self.db.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT clean_url FROM discovered_urls 
                    WHERE status = ? 
                    ORDER BY clean_url
                """, (status,))
                
                urls = [row[0] for row in cursor.fetchall()]
                
                if urls:
                    with open(filename, 'w', encoding='utf-8') as f:
                        for url in urls:
                            f.write(url + '\n')
                    
                    print(f"📄 Exported {len(urls)} {status} URLs to {filename}")
                    return True
                else:
                    print(f"❌ No {status} URLs found to export")
                    return False
                    
            finally:
                conn.close()
    
    def show_progress(self):
        """Show real-time progress"""
        stats = self.db.get_stats()
        urls_by_status = stats.get('urls_by_status', {})
        
        total = sum(urls_by_status.values())
        completed = urls_by_status.get('completed', 0)
        pending = urls_by_status.get('pending', 0)
        downloading = urls_by_status.get('downloading', 0)
        failed = urls_by_status.get('failed', 0)
        
        if total > 0:
            progress = (completed / total) * 100
            print(f"🚀 CRAWL PROGRESS")
            print(f"   Progress: {progress:.1f}% ({completed:,}/{total:,})")
            print(f"   Pending:  {pending:,}")
            print(f"   Active:   {downloading:,}")
            print(f"   Failed:   {failed:,}")
            
            # Progress bar
            bar_length = 40
            filled_length = int(bar_length * completed // total)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            print(f"   [{bar}] {progress:.1f}%")
        else:
            print("📭 No crawling data found")
    
    def _get_db_size(self) -> str:
        """Get database file size"""
        try:
            size = os.path.getsize(self.db_path)
            return self._format_bytes(size)
        except:
            return "Unknown"
    
    def _format_bytes(self, bytes_size: int) -> str:
        """Format bytes in human readable format"""
        if bytes_size == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        
        return f"{bytes_size:.1f} PB"

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate crawler database reports")
    parser.add_argument('--db-path', '-d', default='crawler_data.db',
                        help='Path to SQLite database (default: crawler_data.db)')
    parser.add_argument('--summary', '-s', action='store_true',
                        help='Show summary report only')
    parser.add_argument('--progress', '-p', action='store_true',
                        help='Show progress only')
    parser.add_argument('--export-urls', '-e', metavar='FILENAME',
                        help='Export completed URLs to file')
    parser.add_argument('--export-status', default='completed',
                        choices=['pending', 'downloading', 'completed', 'failed'],
                        help='Status of URLs to export (default: completed)')
    
    args = parser.parse_args()
    
    reporter = CrawlerReporter(args.db_path)
    
    if args.progress:
        reporter.show_progress()
    elif args.export_urls:
        reporter.export_url_list(args.export_urls, args.export_status)
    elif args.summary:
        reporter.generate_summary_report()
    else:
        # Full report
        reporter.generate_summary_report()
        reporter.generate_detailed_report()

if __name__ == "__main__":
    main()