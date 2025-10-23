#!/usr/bin/env python3
"""
Confluence Metadata Manager
Handles generation of YAML metadata files and derived statistics
"""
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    from database_manager import DatabaseManager
except ImportError:
    from src.database_manager import DatabaseManager


class ConfluenceMetadata:
    """
    Manages Confluence page metadata:
    - Generates structured YAML files
    - Calculates derived statistics
    - Saves metadata to database
    """
    
    def __init__(self, db: DatabaseManager):
        """
        Initialize metadata manager
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
    
    def generate_yaml(self, metadata: dict, attachments: list, paths: dict) -> str:
        """
        Generate YAML content with structured metadata
        Similar to the format from confluence_api.sh bash script
        
        Args:
            metadata: Page metadata dictionary
            attachments: List of attachment dictionaries
            paths: Dictionary with file paths (html, json, markdown, etc.)
            
        Returns:
            YAML string
        """
        # Calculate derived statistics
        derived_stats = self._calculate_derived_stats(metadata, attachments)
        
        # Build the YAML structure
        yaml_data = {
            'source': {
                'endpoint': metadata.get('endpoint', ''),
                'query': metadata.get('query', ''),
                'request_url': metadata.get('request_url', ''),
                'rest': metadata.get('links', {}).get('rest', ''),
                'web': metadata.get('links', {}).get('web', ''),
                'tiny': metadata.get('links', {}).get('tiny', '')
            },
            'content': {
                'id': metadata.get('id', ''),
                'ari': metadata.get('ari', ''),
                'type': metadata.get('type', ''),
                'status': metadata.get('status', ''),
                'space_key': metadata.get('space_key', ''),
                'space_name': metadata.get('space_name', ''),
                'title': metadata.get('title', '')
            },
            'history': {
                'created': {
                    'when': metadata.get('history', {}).get('created', {}).get('when'),
                    'by': metadata.get('history', {}).get('created', {}).get('by'),
                    'by_email': metadata.get('history', {}).get('created', {}).get('by_email'),
                    'by_account': metadata.get('history', {}).get('created', {}).get('by_account')
                },
                'updated': {
                    'when': metadata.get('history', {}).get('updated', {}).get('when'),
                    'by': metadata.get('history', {}).get('updated', {}).get('by'),
                    'by_email': metadata.get('history', {}).get('updated', {}).get('by_email'),
                    'by_account': metadata.get('history', {}).get('updated', {}).get('by_account')
                }
            },
            'version': {
                'number': metadata.get('version', {}).get('number'),
                'minor': metadata.get('version', {}).get('minor_edit', False),
                'by': metadata.get('version', {}).get('by'),
                'by_email': metadata.get('version', {}).get('by_email'),
                'by_account': metadata.get('version', {}).get('by_account'),
                'when': metadata.get('version', {}).get('when'),
                'comment': metadata.get('version', {}).get('message')
            },
            'derived': derived_stats,
            'paths': paths,
            'attachments': {
                'count': len(attachments),
                'items': attachments if attachments else []
            }
        }
        
        # Convert to YAML with nice formatting
        return yaml.dump(
            yaml_data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            indent=2
        )
    
    def _calculate_derived_stats(self, metadata: dict, attachments: list) -> dict:
        """
        Calculate derived statistics from metadata
        
        Args:
            metadata: Page metadata
            attachments: List of attachments
            
        Returns:
            Dictionary with derived stats
        """
        stats = {
            'has_attachments': len(attachments) > 0,
            'attachment_count': len(attachments),
            'days_since_update': None,
            'content_char_count': metadata.get('content_char_count', 0),
            'has_tables': metadata.get('has_tables', False)
        }
        
        # Calculate days since last update
        updated_when = metadata.get('history', {}).get('updated', {}).get('when')
        if updated_when:
            try:
                # Handle ISO format timestamps
                if isinstance(updated_when, str):
                    # Remove 'Z' and add UTC timezone
                    updated_when = updated_when.replace('Z', '+00:00')
                    updated_date = datetime.fromisoformat(updated_when)
                else:
                    updated_date = updated_when
                
                now = datetime.now(timezone.utc)
                delta = now - updated_date
                stats['days_since_update'] = delta.days
            except Exception as e:
                print(f"⚠️  Could not calculate days_since_update: {e}")
        
        return stats
    
    def save_to_database(self, url: str, metadata: dict, attachments: list) -> bool:
        """
        Save metadata and attachments to database
        
        Args:
            url: Page URL
            metadata: Page metadata dictionary
            attachments: List of attachment dictionaries
            
        Returns:
            True if saved successfully
        """
        # Add derived stats to metadata before saving
        derived_stats = self._calculate_derived_stats(metadata, attachments)
        metadata['days_since_update'] = derived_stats['days_since_update']
        metadata['has_attachments'] = derived_stats['has_attachments']
        metadata['attachment_count'] = derived_stats['attachment_count']
        
        # Save metadata
        success = self.db.save_confluence_metadata(url, metadata)
        
        # Save attachments
        if attachments and success:
            page_id = metadata.get('id', '')
            success = self.db.save_confluence_attachments(url, page_id, attachments)
        
        return success
    
    def save_yaml_file(self, yaml_content: str, file_path: Path) -> bool:
        """
        Save YAML content to file
        
        Args:
            yaml_content: YAML string to save
            file_path: Path where to save the file
            
        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write YAML file
            file_path.write_text(yaml_content, encoding='utf-8')
            
            return True
        except Exception as e:
            print(f"❌ Error saving YAML file {file_path}: {e}")
            return False
    
    def format_attachment_for_yaml(self, attachment: dict) -> dict:
        """
        Format attachment data for YAML output
        
        Args:
            attachment: Raw attachment dictionary
            
        Returns:
            Formatted attachment dictionary
        """
        return {
            'id': attachment.get('id', ''),
            'title': attachment.get('title', ''),
            'media_type': attachment.get('media_type', ''),
            'version': attachment.get('version', 1),
            'file_size_api': attachment.get('file_size', 0),
            'file_size_local': attachment.get('file_size_local', 0),
            'created': attachment.get('created', ''),
            'created_by': attachment.get('created_by', ''),
            'comment': attachment.get('comment', ''),
            'source_download': attachment.get('download_url', ''),
            'local_path': attachment.get('local_path', '')
        }
    
    def extract_content_stats(self, html_content: str) -> dict:
        """
        Extract statistics from HTML content
        
        Args:
            html_content: HTML content string
            
        Returns:
            Dictionary with content statistics
        """
        stats = {
            'content_char_count': len(html_content),
            'has_tables': '<table' in html_content.lower()
        }
        
        return stats
    
    @staticmethod
    def create_relative_paths(base_dir: Path, files: dict) -> dict:
        """
        Create relative paths for file references in YAML
        
        Args:
            base_dir: Base directory for relative paths
            files: Dictionary with file paths (html, json, markdown, etc.)
            
        Returns:
            Dictionary with relative paths
        """
        relative = {}
        
        for key, file_path in files.items():
            if file_path and Path(file_path).exists():
                try:
                    relative[key] = str(Path(file_path).relative_to(base_dir))
                except ValueError:
                    # If paths are not relative, use absolute
                    relative[key] = str(file_path)
            else:
                relative[key] = None
        
        return relative


# Standalone function for quick YAML generation
def generate_metadata_yaml(
    url: str,
    page_data: dict,
    attachments: list,
    file_paths: dict,
    output_path: Path
) -> bool:
    """
    Convenience function to generate and save YAML metadata
    
    Args:
        url: Page URL
        page_data: Page metadata from API
        attachments: List of attachments
        file_paths: Dictionary with file paths
        output_path: Where to save the YAML file
        
    Returns:
        True if successful
    """
    try:
        # Create a dummy database manager (won't actually save to DB)
        from database_manager import DatabaseManager
        db = DatabaseManager(':memory:')  # In-memory database
        
        metadata_manager = ConfluenceMetadata(db)
        
        # Generate YAML
        yaml_content = metadata_manager.generate_yaml(page_data, attachments, file_paths)
        
        # Save to file
        return metadata_manager.save_yaml_file(yaml_content, output_path)
    
    except Exception as e:
        print(f"❌ Error generating metadata YAML: {e}")
        return False


if __name__ == "__main__":
    # Test metadata generation
    print("Testing Confluence Metadata Generator\n")
    
    # Sample metadata
    sample_metadata = {
        'id': '556040223',
        'ari': 'ari:cloud:confluence::page/556040223',
        'type': 'page',
        'status': 'current',
        'title': 'Sample Confluence Page',
        'space_key': 'AR',
        'space_name': 'Architecture',
        'version': {
            'number': 5,
            'when': '2025-10-20T10:30:00.000Z',
            'by': 'John Doe',
            'by_email': 'john@example.com',
            'by_account': 'account123',
            'message': 'Updated diagrams',
            'minor_edit': False
        },
        'history': {
            'created': {
                'when': '2025-01-15T08:00:00.000Z',
                'by': 'Jane Smith',
                'by_email': 'jane@example.com',
                'by_account': 'account456'
            },
            'updated': {
                'when': '2025-10-20T10:30:00.000Z',
                'by': 'John Doe',
                'by_email': 'john@example.com',
                'by_account': 'account123'
            }
        },
        'links': {
            'web': '/wiki/spaces/AR/pages/556040223',
            'rest': '/rest/api/content/556040223',
            'tiny': '/x/123abc'
        }
    }
    
    sample_attachments = [
        {
            'id': '123456',
            'title': 'diagram.png',
            'media_type': 'image/png',
            'file_size': 45678,
            'file_size_local': 45678,
            'version': 2,
            'created': '2025-01-20T09:00:00.000Z',
            'created_by': 'John Doe',
            'comment': 'Updated diagram',
            'download_url': '/download/attachments/556040223/diagram.png',
            'local_path': 'attachments/123456_diagram.png'
        }
    ]
    
    sample_paths = {
        'html': 'index.html',
        'markdown': 'index.md',
        'json': 'index.json',
        'metadata': 'index.yml',
        'attachments_dir': 'attachments'
    }
    
    # Create metadata manager
    from database_manager import DatabaseManager
    db = DatabaseManager(':memory:')
    metadata_manager = ConfluenceMetadata(db)
    
    # Generate YAML
    yaml_content = metadata_manager.generate_yaml(
        sample_metadata,
        sample_attachments,
        sample_paths
    )
    
    print("Generated YAML:\n")
    print("=" * 70)
    print(yaml_content)
    print("=" * 70)
    print("\n✅ Metadata generation test completed")
