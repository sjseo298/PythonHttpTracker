#!/usr/bin/env python3
"""
SQLite Database Manager for Web Crawler
Handles all database operations for tracking URLs, documents, and resources
"""
import sqlite3
import threading
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
import os

class DatabaseManager:
    """Manages SQLite database operations for web crawler progress tracking"""
    
    def __init__(self, db_path: str = "crawler_data.db"):
        self.db_path = db_path
        self.db_lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database with required tables"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                # Table for discovered URLs and their processing status
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS discovered_urls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT UNIQUE NOT NULL,
                        clean_url TEXT NOT NULL,
                        depth INTEGER NOT NULL,
                        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending',
                        retry_count INTEGER DEFAULT 0,
                        error_message TEXT,
                        parent_url TEXT
                    )
                """)
                
                # Create indexes for discovered_urls
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_discovered_urls_url ON discovered_urls(url)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_discovered_urls_status ON discovered_urls(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_discovered_urls_depth ON discovered_urls(depth)")
                
                # Table for successfully downloaded documents
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS downloaded_documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT UNIQUE NOT NULL,
                        clean_url TEXT NOT NULL,
                        local_path TEXT NOT NULL,
                        file_size INTEGER,
                        download_time REAL,
                        downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        content_type TEXT,
                        last_modified TIMESTAMP,
                        depth INTEGER,
                        links_extracted INTEGER DEFAULT 0
                    )
                """)
                
                # Create indexes for downloaded_documents
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_downloaded_documents_url ON downloaded_documents(url)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_downloaded_documents_clean_url ON downloaded_documents(clean_url)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_downloaded_documents_downloaded_at ON downloaded_documents(downloaded_at)")
                
                # Table for downloaded resources (CSS, images, etc.)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS downloaded_resources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT UNIQUE NOT NULL,
                        local_path TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        file_size INTEGER,
                        download_time REAL,
                        downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        referenced_by TEXT,
                        is_transversal BOOLEAN DEFAULT FALSE
                    )
                """)
                
                # Create indexes for downloaded_resources
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_downloaded_resources_url ON downloaded_resources(url)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_downloaded_resources_type ON downloaded_resources(resource_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_downloaded_resources_referenced_by ON downloaded_resources(referenced_by)")
                
                # Table for URL mapping (clean URL to local path)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS url_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        clean_url TEXT UNIQUE NOT NULL,
                        local_path TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index for url_mappings
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_url_mappings_clean_url ON url_mappings(clean_url)")
                
                # Table for crawler statistics and metadata
                # Table for crawler statistics and metadata
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS crawler_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP,
                        total_urls_discovered INTEGER DEFAULT 0,
                        total_documents_downloaded INTEGER DEFAULT 0,
                        total_resources_downloaded INTEGER DEFAULT 0,
                        total_errors INTEGER DEFAULT 0,
                        config_snapshot TEXT
                    )
                """)
                
                # Create indexes for crawler_stats
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawler_stats_session_id ON crawler_stats(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawler_stats_start_time ON crawler_stats(start_time)")
                
                conn.commit()
                print("✅ Database initialized successfully")
                
            except Exception as e:
                print(f"❌ Error initializing database: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()
    
    def add_discovered_url(self, url: str, clean_url: str, depth: int, parent_url: str = None) -> bool:
        """Add a newly discovered URL to the database"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO discovered_urls 
                    (url, clean_url, depth, parent_url, status) 
                    VALUES (?, ?, ?, ?, 'pending')
                """, (url, clean_url, depth, parent_url))
                
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"❌ Error adding discovered URL {url}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def add_discovered_urls_batch(self, urls_data: List[Tuple[str, str, int, str]]) -> int:
        """Add multiple discovered URLs in a batch operation"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR IGNORE INTO discovered_urls 
                    (url, clean_url, depth, parent_url, status) 
                    VALUES (?, ?, ?, ?, 'pending')
                """, [(url, clean_url, depth, parent_url) for url, clean_url, depth, parent_url in urls_data])
                
                conn.commit()
                return cursor.rowcount
            except Exception as e:
                print(f"❌ Error adding discovered URLs batch: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()
    
    def get_pending_urls(self, limit: int = None) -> List[Tuple[str, int]]:
        """Get pending URLs to download"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                query = """
                    SELECT clean_url, depth FROM discovered_urls 
                    WHERE status = 'pending' 
                    ORDER BY depth DESC, discovered_at ASC
                """
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                print(f"❌ Error getting pending URLs: {e}")
                return []
            finally:
                conn.close()
    
    def mark_url_downloading(self, clean_url: str) -> bool:
        """Mark a URL as currently being downloaded"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE discovered_urls 
                    SET status = 'downloading' 
                    WHERE clean_url = ? AND status = 'pending'
                """, (clean_url,))
                
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"❌ Error marking URL as downloading {clean_url}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def mark_url_completed(self, clean_url: str, local_path: str, file_size: int = None, 
                          download_time: float = None, links_extracted: int = 0, depth: int = None) -> bool:
        """Mark a URL as successfully downloaded"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                # Update discovered_urls status
                cursor.execute("""
                    UPDATE discovered_urls 
                    SET status = 'completed' 
                    WHERE clean_url = ?
                """, (clean_url,))
                
                # Add to downloaded_documents
                cursor.execute("""
                    INSERT OR REPLACE INTO downloaded_documents 
                    (url, clean_url, local_path, file_size, download_time, depth, links_extracted) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (clean_url, clean_url, local_path, file_size, download_time, depth, links_extracted))
                
                # Add to url_mappings
                cursor.execute("""
                    INSERT OR REPLACE INTO url_mappings 
                    (clean_url, local_path) 
                    VALUES (?, ?)
                """, (clean_url, local_path))
                
                conn.commit()
                return True
            except Exception as e:
                print(f"❌ Error marking URL as completed {clean_url}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def mark_url_failed(self, clean_url: str, error_message: str = None) -> bool:
        """Mark a URL as failed to download"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE discovered_urls 
                    SET status = 'failed', error_message = ?, retry_count = retry_count + 1 
                    WHERE clean_url = ?
                """, (error_message, clean_url))
                
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"❌ Error marking URL as failed {clean_url}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def add_downloaded_resource(self, url: str, local_path: str, resource_type: str, 
                               file_size: int = None, download_time: float = None, 
                               referenced_by: str = None, is_transversal: bool = False) -> bool:
        """Add a downloaded resource to the database"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO downloaded_resources 
                    (url, local_path, resource_type, file_size, download_time, referenced_by, is_transversal) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (url, local_path, resource_type, file_size, download_time, referenced_by, is_transversal))
                
                conn.commit()
                return True
            except Exception as e:
                print(f"❌ Error adding downloaded resource {url}: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def get_downloaded_urls(self) -> Set[str]:
        """Get set of all downloaded URLs"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT clean_url FROM downloaded_documents")
                return set(row[0] for row in cursor.fetchall())
            except Exception as e:
                print(f"❌ Error getting downloaded URLs: {e}")
                return set()
            finally:
                conn.close()
    
    def get_downloaded_resources(self) -> Set[str]:
        """Get set of all downloaded resource URLs"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT url FROM downloaded_resources")
                return set(row[0] for row in cursor.fetchall())
            except Exception as e:
                print(f"❌ Error getting downloaded resources: {e}")
                return set()
            finally:
                conn.close()
    
    def get_url_to_filename_mapping(self) -> Dict[str, str]:
        """Get mapping of URLs to local filenames"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT clean_url, local_path FROM url_mappings")
                return dict(cursor.fetchall())
            except Exception as e:
                print(f"❌ Error getting URL to filename mapping: {e}")
                return {}
            finally:
                conn.close()
    
    def get_transversal_resources(self) -> Dict[str, str]:
        """Get mapping of transversal resource URLs to local paths"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT url, local_path FROM downloaded_resources 
                    WHERE is_transversal = TRUE
                """)
                return dict(cursor.fetchall())
            except Exception as e:
                print(f"❌ Error getting transversal resources: {e}")
                return {}
            finally:
                conn.close()
    
    def is_resource_downloaded(self, url: str) -> bool:
        """Check if a resource has already been downloaded"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM downloaded_resources WHERE url = ? LIMIT 1", (url,))
                return cursor.fetchone() is not None
            except Exception as e:
                print(f"❌ Error checking if resource downloaded {url}: {e}")
                return False
            finally:
                conn.close()
    
    def get_resource_path(self, url: str) -> Optional[str]:
        """Get local path for a downloaded resource"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT local_path FROM downloaded_resources WHERE url = ? LIMIT 1", (url,))
                result = cursor.fetchone()
                return result[0] if result else None
            except Exception as e:
                print(f"❌ Error getting resource path {url}: {e}")
                return None
            finally:
                conn.close()
    
    def get_stats(self) -> Dict:
        """Get crawler statistics"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                stats = {}
                
                # Count discovered URLs by status
                cursor.execute("""
                    SELECT status, COUNT(*) FROM discovered_urls GROUP BY status
                """)
                status_counts = dict(cursor.fetchall())
                stats['urls_by_status'] = status_counts
                
                # Count downloaded documents
                cursor.execute("SELECT COUNT(*) FROM downloaded_documents")
                stats['total_documents'] = cursor.fetchone()[0]
                
                # Count downloaded resources
                cursor.execute("SELECT COUNT(*) FROM downloaded_resources")
                stats['total_resources'] = cursor.fetchone()[0]
                
                # Get total file sizes
                cursor.execute("SELECT SUM(file_size) FROM downloaded_documents WHERE file_size IS NOT NULL")
                result = cursor.fetchone()[0]
                stats['total_documents_size'] = result if result else 0
                
                cursor.execute("SELECT SUM(file_size) FROM downloaded_resources WHERE file_size IS NOT NULL")
                result = cursor.fetchone()[0]
                stats['total_resources_size'] = result if result else 0
                
                return stats
            except Exception as e:
                print(f"❌ Error getting stats: {e}")
                return {}
            finally:
                conn.close()
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old crawler data"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM crawler_stats 
                    WHERE start_time < datetime('now', '-{} days')
                """.format(days))
                
                conn.commit()
                print(f"✅ Cleaned up data older than {days} days")
            except Exception as e:
                print(f"❌ Error cleaning up old data: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def export_to_json(self, output_file: str = "crawler_backup.json"):
        """Export database content to JSON for backup"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                data = {}
                
                # Export all tables
                for table in ['discovered_urls', 'downloaded_documents', 'downloaded_resources', 'url_mappings']:
                    cursor.execute(f"SELECT * FROM {table}")
                    columns = [description[0] for description in cursor.description]
                    rows = cursor.fetchall()
                    data[table] = [dict(zip(columns, row)) for row in rows]
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                
                print(f"✅ Database exported to {output_file}")
                return True
            except Exception as e:
                print(f"❌ Error exporting database: {e}")
                return False
            finally:
                conn.close()
    
    def get_total_urls_count(self) -> int:
        """Get total count of URLs in the database"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM discovered_urls")
                return cursor.fetchone()[0]
            except Exception as e:
                print(f"❌ Error getting URL count: {e}")
                return 0
            finally:
                conn.close()
    
    def reset_progress(self) -> bool:
        """Reset crawling progress while preserving file structure knowledge"""
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                # Clear all discovery and download progress
                cursor.execute("DELETE FROM discovered_urls")
                cursor.execute("DELETE FROM downloaded_documents")
                cursor.execute("DELETE FROM downloaded_resources")
                cursor.execute("DELETE FROM url_mappings")
                
                # Reset auto-increment counters
                cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('discovered_urls', 'downloaded_documents', 'downloaded_resources', 'url_mappings')")
                
                conn.commit()
                print("✅ Database progress reset successfully")
                return True
            except Exception as e:
                print(f"❌ Error resetting progress: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()

    def close(self):
        """Close database connections and cleanup"""
        # SQLite connections are automatically closed when objects are destroyed
        print("📦 Database manager closed")