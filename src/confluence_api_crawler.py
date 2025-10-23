#!/usr/bin/env python3
"""
Confluence API Crawler
Downloads Confluence pages using the REST API with full metadata extraction
"""
import os
import re
import time
import json
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse, unquote

try:
    import requests
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
except ImportError:
    print("❌ Missing required dependencies. Install with:")
    print("   pip install requests beautifulsoup4 markdownify")
    raise

try:
    from base_crawler import BaseCrawler
    from confluence_auth import ConfluenceAuth
    from confluence_metadata import ConfluenceMetadata
    from database_manager import DatabaseManager
    from progress_tracker import ProgressTracker
except ImportError:
    from src.base_crawler import BaseCrawler
    from src.confluence_auth import ConfluenceAuth
    from src.confluence_metadata import ConfluenceMetadata
    from src.database_manager import DatabaseManager
    from src.progress_tracker import ProgressTracker


class ConfluenceAPICrawler(BaseCrawler):
    """
    Crawler specialized for Confluence that uses the REST API
    to fetch content with complete metadata
    """
    
    def __init__(self, config: dict, auth: ConfluenceAuth, 
                 db: DatabaseManager = None, 
                 progress_tracker: ProgressTracker = None):
        """
        Initialize Confluence API crawler
        
        Args:
            config: Configuration dictionary
            auth: ConfluenceAuth instance with credentials
            db: Database manager (optional)
            progress_tracker: Progress tracker (optional)
        """
        super().__init__(config, db, progress_tracker)
        
        self.auth = auth
        if not self.auth.is_valid():
            raise ValueError("❌ Confluence authentication is not properly configured")
        
        self.api_base = self.auth.get_api_base_url()
        self.metadata_handler = ConfluenceMetadata(self.db)
        
        # Confluence-specific settings
        self.save_json = self.config.get('output', {}).get('confluence_output', {}).get('save_api_response', True)
        self.save_yaml = self.config.get('output', {}).get('confluence_output', {}).get('save_metadata_yml', True)
        self.download_attachments = self.config.get('output', {}).get('confluence_output', {}).get('save_attachments', True)
        
        print(f"✅ Confluence API Crawler initialized")
        print(f"   API Base: {self.api_base}")
        print(f"   Email: {self.auth.email}")
        print(f"   Save JSON: {self.save_json}")
        print(f"   Save YAML: {self.save_yaml}")
        print(f"   Download Attachments: {self.download_attachments}")
    
    def fetch_page(self, url: str, depth: int) -> dict:
        """
        Fetch a Confluence page using the REST API
        
        Args:
            url: The page URL
            depth: Current crawling depth
            
        Returns:
            Dictionary with content, metadata, links, and success status
        """
        try:
            # Check if this is a space overview URL - if so, return all space pages as links
            if '/spaces/' in url and ('/overview' in url or url.endswith(self.space)):
                return self._fetch_space_pages(url)
            
            # Extract page ID from URL
            page_id = self._extract_page_id(url)
            
            if not page_id:
                return {
                    'success': False,
                    'error': f'Could not extract page ID from URL: {url}',
                    'links': []
                }
            
            # Call Confluence API
            api_url = f"{self.api_base}/content/{page_id}"
            params = {
                'expand': 'history.lastUpdated,version,body.view,body.storage,space,ancestors,children.page,metadata.labels'
            }
            
            start_time = time.time()
            
            response = requests.get(
                api_url,
                auth=self.auth.get_auth_tuple(),
                params=params,
                headers=self.auth.get_headers(),
                timeout=(5, 15)
            )
            
            download_time = time.time() - start_time
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'API request failed with status {response.status_code}: {response.text[:200]}',
                    'links': []
                }
            
            data = response.json()
            
            # Extract metadata
            metadata = self._extract_metadata(data, url)
            metadata['download_time'] = download_time
            
            # Get HTML content
            html_content = data.get('body', {}).get('view', {}).get('value', '')
            
            # Extract content statistics
            content_stats = self.metadata_handler.extract_content_stats(html_content)
            metadata.update(content_stats)
            
            # Download attachments if enabled
            attachments = []
            if self.download_attachments:
                attachments = self._fetch_attachments(page_id)
                self.progress_tracker.update_stat('resources_downloaded', increment=len(attachments))
            
            # Extract links for further crawling
            links = self._extract_links_from_api_response(data, html_content)
            
            return {
                'success': True,
                'content': html_content,
                'storage': data.get('body', {}).get('storage', {}).get('value', ''),
                'metadata': metadata,
                'attachments': attachments,
                'links': links,
                'raw_json': data,
                'page_id': page_id
            }
        
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
                'links': []
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Request error: {str(e)}',
                'links': []
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'links': []
            }
    
    def _fetch_space_pages(self, url: str) -> dict:
        """
        Fetch all pages from a Confluence space using CQL search
        
        Args:
            url: Space URL (e.g., /wiki/spaces/AR/overview)
            
        Returns:
            Dictionary with space info and all page links
        """
        try:
            # Extract space key from URL
            space_match = re.search(r'/spaces/([^/]+)', url)
            if not space_match:
                return {
                    'success': False,
                    'error': 'Could not extract space key from URL',
                    'links': []
                }
            
            space_key = space_match.group(1)
            print(f"\n🔍 Fetching all pages from space: {space_key}")
            
            # Use CQL to search for all pages in the space
            search_url = f"{self.api_base}/content/search"
            all_links = []
            start = 0
            limit = 100  # Max per request
            
            while True:
                params = {
                    'cql': f'type=page AND space={space_key}',
                    'limit': limit,
                    'start': start,
                    'expand': '_links.webui'
                }
                
                response = requests.get(
                    search_url,
                    auth=self.auth.get_auth_tuple(),
                    params=params,
                    headers=self.auth.get_headers(),
                    timeout=(5, 30)
                )
                
                if response.status_code != 200:
                    print(f"⚠️  Failed to fetch space pages: HTTP {response.status_code}")
                    break
                
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    break
                
                # Extract page URLs
                base_url = self.auth.base_url.rstrip('/')
                for page in results:
                    page_id = page.get('id')
                    webui_link = page.get('_links', {}).get('webui', '')
                    
                    if webui_link:
                        if webui_link.startswith('http'):
                            page_url = webui_link
                        else:
                            # Ensure /wiki prefix is included
                            if webui_link.startswith('/wiki'):
                                page_url = base_url + webui_link
                            else:
                                page_url = base_url + '/wiki' + webui_link
                        all_links.append(page_url)
                
                # Check if there are more pages
                total = data.get('totalSize', 0)
                start += limit
                
                if start >= total:
                    break
                
                print(f"   📄 Fetched {len(all_links)} pages so far...")
            
            print(f"✅ Found {len(all_links)} pages in space {space_key}")
            
            # Return a synthetic response with all page links
            return {
                'success': True,
                'is_space_index': True,  # Special flag to skip saving
                'content': f'<h1>Space: {space_key}</h1><p>This space contains {len(all_links)} pages.</p>',
                'storage': '',
                'metadata': {
                    'id': f'space-{space_key}',
                    'type': 'space',
                    'title': f'Space: {space_key}',
                    'space_key': space_key,
                    'space_name': space_key,
                    'url': url,
                    'page_count': len(all_links)
                },
                'attachments': [],
                'links': all_links,
                'raw_json': {},
                'page_id': f'space-{space_key}'
            }
            
        except Exception as e:
            print(f"❌ Error fetching space pages: {e}")
            return {
                'success': False,
                'error': f'Error fetching space pages: {str(e)}',
                'links': []
            }
    
    def _extract_page_id(self, url: str) -> Optional[str]:
        """
        Extract page ID from various Confluence URL formats
        
        Supported formats:
        - /pages/123456/title
        - /pages/viewpage.action?pageId=123456
        - /display/SPACE/title?pageId=123456
        - /content/123456
        
        Args:
            url: The Confluence URL
            
        Returns:
            Page ID string or None if not found
        """
        patterns = [
            r'/pages/(\d+)',
            r'pageId=(\d+)',
            r'/content/(\d+)',
            r'/(\d{6,})',  # Any 6+ digit number in path
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # If no ID found, try to resolve via API search
        return self._resolve_page_id_via_title(url)
    
    def _resolve_page_id_via_title(self, url: str) -> Optional[str]:
        """
        Attempt to resolve page ID by searching via title in URL
        
        Args:
            url: The page URL
            
        Returns:
            Page ID or None
        """
        try:
            # Extract potential title from URL
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            
            if len(path_parts) > 0:
                potential_title = unquote(path_parts[-1])
                
                # Try CQL search
                search_url = f"{self.api_base}/content/search"
                params = {
                    'cql': f'title~"{potential_title}" AND type=page',
                    'limit': 1
                }
                
                response = requests.get(
                    search_url,
                    auth=self.auth.get_auth_tuple(),
                    params=params,
                    headers=self.auth.get_headers(),
                    timeout=(5, 10)
                )
                
                if response.status_code == 200:
                    results = response.json().get('results', [])
                    if results:
                        return results[0].get('id')
        
        except Exception as e:
            print(f"⚠️  Could not resolve page ID for {url}: {e}")
        
        return None
    
    def _fetch_attachments(self, page_id: str) -> List[dict]:
        """
        Fetch all attachments for a page with pagination
        
        Args:
            page_id: The page ID
            
        Returns:
            List of attachment dictionaries
        """
        attachments = []
        next_url = f"{self.api_base}/content/{page_id}/child/attachment?limit=200&expand=version,metadata,extensions"
        
        while next_url:
            try:
                response = requests.get(
                    next_url,
                    auth=self.auth.get_auth_tuple(),
                    headers=self.auth.get_headers(),
                    timeout=(5, 30)
                )
                
                if response.status_code != 200:
                    print(f"⚠️  Failed to fetch attachments: {response.status_code}")
                    break
                
                data = response.json()
                
                for attachment in data.get('results', []):
                    attachment_dict = self._process_attachment(attachment, page_id)
                    if attachment_dict:
                        attachments.append(attachment_dict)
                
                # Handle pagination
                next_link = data.get('_links', {}).get('next')
                if next_link:
                    # Check if it's a relative or absolute URL
                    if next_link.startswith('http'):
                        next_url = next_link
                    else:
                        next_url = self.auth.base_url.rstrip('/') + next_link
                else:
                    next_url = None
            
            except Exception as e:
                print(f"⚠️  Error fetching attachments: {e}")
                break
        
        return attachments
    
    def _process_attachment(self, attachment: dict, page_id: str) -> Optional[dict]:
        """
        Process and download a single attachment
        
        Args:
            attachment: Attachment data from API
            page_id: Parent page ID
            
        Returns:
            Attachment dictionary with local path
        """
        try:
            attachment_id = attachment.get('id', '')
            title = attachment.get('title', 'unknown')
            
            # Build download URL
            download_path = attachment.get('_links', {}).get('download', '')
            if not download_path:
                return None
            
            if download_path.startswith('http'):
                download_url = download_path
            else:
                # Ensure /wiki prefix is included for relative URLs
                if download_path.startswith('/wiki'):
                    download_url = self.auth.base_url.rstrip('/') + download_path
                else:
                    download_url = self.auth.base_url.rstrip('/') + '/wiki' + download_path
            
            # Generate safe filename
            safe_title = self._sanitize_filename(title)
            local_filename = f"{attachment_id}_{safe_title}"
            
            # Create attachments directory
            attachments_dir = Path(self.output_dir) / "spaces" / self.space / "pages" / page_id / "attachments"
            attachments_dir.mkdir(parents=True, exist_ok=True)
            
            local_path = attachments_dir / local_filename
            
            # Download the attachment (follow redirects for CDN-hosted files)
            response = requests.get(
                download_url,
                auth=self.auth.get_auth_tuple(),
                headers=self.auth.get_headers(),
                timeout=(5, 60),
                stream=True,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size_local = local_path.stat().st_size
                
                return {
                    'id': attachment_id,
                    'title': title,
                    'media_type': attachment.get('metadata', {}).get('mediaType', '') or 
                                  attachment.get('extensions', {}).get('mediaType', ''),
                    'file_size': attachment.get('extensions', {}).get('fileSize', 0),
                    'file_size_local': file_size_local,
                    'version': attachment.get('version', {}).get('number', 1),
                    'created': attachment.get('created', '') or 
                               attachment.get('metadata', {}).get('created', ''),
                    'created_by': attachment.get('creator', {}).get('displayName', '') or
                                  attachment.get('metadata', {}).get('creator', {}).get('displayName', ''),
                    'comment': attachment.get('metadata', {}).get('comment', '') or
                               attachment.get('extensions', {}).get('comment', ''),
                    'download_url': download_url,
                    'local_path': str(local_path.relative_to(Path(self.output_dir)))
                }
            else:
                # Provide more context for the error
                if response.status_code == 404:
                    # 404 is common for deleted or moved attachments - not critical
                    pass  # Silent fail for 404s - attachment may have been deleted
                elif response.status_code == 403:
                    print(f"⚠️  No permission to download attachment {title}")
                elif response.status_code == 401:
                    print(f"⚠️  Authentication failed for attachment {title}")
                else:
                    print(f"⚠️  Failed to download attachment {title}: HTTP {response.status_code}")
                return None
        
        except Exception as e:
            print(f"⚠️  Error processing attachment {attachment.get('title', 'unknown')}: {e}")
            return None
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to be filesystem-safe
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Replace spaces with underscores
        filename = filename.replace(' ', '_')
        
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Limit length
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:190] + ext
        
        return filename or 'attachment'
    
    def _extract_links_from_api_response(self, data: dict, html_content: str) -> List[str]:
        """
        Extract links from API response for further crawling
        
        Sources:
        1. Links in HTML content (body.view)
        2. Child pages
        3. Ancestor pages
        
        Args:
            data: API response data
            html_content: HTML content from body.view
            
        Returns:
            List of URLs to crawl
        """
        links = []
        base_url = self.auth.base_url.rstrip('/')
        
        # Extract links from HTML content
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    full_url = base_url + href
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                
                # Check if it's a Confluence page URL
                if self._is_confluence_page_url(full_url):
                    links.append(full_url)
        
        # Extract child pages
        children = data.get('children', {}).get('page', {}).get('results', [])
        for child in children:
            child_link = child.get('_links', {}).get('webui', '')
            if child_link:
                if child_link.startswith('http'):
                    links.append(child_link)
                else:
                    links.append(base_url + child_link)
        
        # Remove duplicates and filter
        links = list(set(links))
        links = [link for link in links if self._is_valid_link(link)]
        
        return links
    
    def _is_confluence_page_url(self, url: str) -> bool:
        """Check if URL is a Confluence page"""
        confluence_patterns = [
            r'/pages/',
            r'/display/',
            r'/viewpage\.action',
            r'/content/'
        ]
        return any(re.search(pattern, url) for pattern in confluence_patterns)
    
    def _is_valid_link(self, url: str) -> bool:
        """Check if link should be followed"""
        # Must be from same domain
        if self.base_domain and self.base_domain not in url:
            return False
        
        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if re.search(pattern, url):
                return False
        
        return True
    
    def _extract_metadata(self, api_response: dict, url: str) -> dict:
        """
        Extract all metadata from API response
        
        Args:
            api_response: JSON response from Confluence API
            url: Original page URL
            
        Returns:
            Dictionary with structured metadata
        """
        return {
            'id': api_response.get('id', ''),
            'ari': api_response.get('_expandable', {}).get('ari', '') or api_response.get('ari', ''),
            'type': api_response.get('type', ''),
            'status': api_response.get('status', ''),
            'title': api_response.get('title', ''),
            'space_key': api_response.get('space', {}).get('key', ''),
            'space_name': api_response.get('space', {}).get('name', ''),
            'version': {
                'number': api_response.get('version', {}).get('number'),
                'when': api_response.get('version', {}).get('when'),
                'by': api_response.get('version', {}).get('by', {}).get('displayName'),
                'by_email': api_response.get('version', {}).get('by', {}).get('email'),
                'by_account': api_response.get('version', {}).get('by', {}).get('accountId'),
                'message': api_response.get('version', {}).get('message'),
                'minor_edit': api_response.get('version', {}).get('minorEdit', False)
            },
            'history': {
                'created': {
                    'when': api_response.get('history', {}).get('createdDate'),
                    'by': api_response.get('history', {}).get('createdBy', {}).get('displayName'),
                    'by_email': api_response.get('history', {}).get('createdBy', {}).get('email'),
                    'by_account': api_response.get('history', {}).get('createdBy', {}).get('accountId')
                },
                'updated': {
                    'when': api_response.get('history', {}).get('lastUpdated', {}).get('when'),
                    'by': api_response.get('history', {}).get('lastUpdated', {}).get('by', {}).get('displayName'),
                    'by_email': api_response.get('history', {}).get('lastUpdated', {}).get('by', {}).get('email'),
                    'by_account': api_response.get('history', {}).get('lastUpdated', {}).get('by', {}).get('accountId')
                }
            },
            'links': {
                'web': api_response.get('_links', {}).get('webui', ''),
                'rest': api_response.get('_links', {}).get('self', ''),
                'tiny': api_response.get('_links', {}).get('tinyui', '')
            },
            'request_url': url,
            'endpoint': f"/content/{api_response.get('id', '')}",
            'query': 'expand=history.lastUpdated,version,body.view,body.storage,space,ancestors,children.page,metadata.labels'
        }
    
    def save_page(self, url: str, content: dict, local_path: str) -> bool:
        """
        Save page with multiple formats: HTML, Markdown, JSON, YAML
        
        Args:
            url: Original URL
            content: Content dictionary from fetch_page()
            local_path: Base local path
            
        Returns:
            True if saved successfully
        """
        try:
            # Skip saving if this is a space index (just for link discovery)
            if content.get('is_space_index', False):
                return True
            
            base_path = Path(local_path).parent
            base_name = Path(local_path).stem
            
            # Ensure directory exists
            base_path.mkdir(parents=True, exist_ok=True)
            
            html_content = content['content']
            attachments = content.get('attachments', [])
            metadata = content.get('metadata', {})
            
            # Rewrite attachment URLs to local paths
            html_content = self._rewrite_attachment_urls(html_content, attachments)
            
            # 1. Save HTML
            html_path = base_path / f"{base_name}.html"
            html_path.write_text(html_content, encoding='utf-8')
            
            # 2. Save Markdown (if configured)
            md_path = None
            if self.output_format == 'markdown':
                md_path = base_path / f"{base_name}.md"
                markdown_content = self._convert_to_markdown(html_content, metadata)
                md_path.write_text(markdown_content, encoding='utf-8')
            
            # 3. Save JSON (if configured)
            json_path = None
            if self.save_json:
                json_path = base_path / f"{base_name}.json"
                json_path.write_text(
                    json.dumps(content['raw_json'], indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )
            
            # 4. Save YAML metadata (if configured)
            yml_path = None
            if self.save_yaml:
                yml_path = base_path / f"{base_name}.yml"
                
                # Prepare paths for YAML
                file_paths = {
                    'base': str(base_path),
                    'html': str(html_path.relative_to(base_path.parent)),
                    'markdown': str(md_path.relative_to(base_path.parent)) if md_path else None,
                    'json': str(json_path.relative_to(base_path.parent)) if json_path else None,
                    'metadata': str(yml_path.relative_to(base_path.parent)),
                    'attachments_dir': 'attachments' if attachments else None
                }
                
                # Format attachments for YAML
                formatted_attachments = [
                    self.metadata_handler.format_attachment_for_yaml(att)
                    for att in attachments
                ]
                
                # Generate and save YAML
                yaml_content = self.metadata_handler.generate_yaml(
                    metadata,
                    formatted_attachments,
                    file_paths
                )
                yml_path.write_text(yaml_content, encoding='utf-8')
            
            # 5. Save metadata to database
            self.metadata_handler.save_to_database(url, metadata, attachments)
            
            # Update statistics
            total_size = html_path.stat().st_size
            if md_path and md_path.exists():
                total_size += md_path.stat().st_size
            if json_path and json_path.exists():
                total_size += json_path.stat().st_size
            
            self.progress_tracker.update_stat('total_size', increment=total_size)
            
            return True
        
        except Exception as e:
            print(f"❌ Error saving page {url}: {e}")
            return False
    
    def _rewrite_attachment_urls(self, html_content: str, attachments: List[dict]) -> str:
        """
        Rewrite attachment URLs in HTML to point to local files
        Replicates the behavior of the bash script's rewrite_html_sources() function
        
        Args:
            html_content: HTML content string
            attachments: List of attachment dictionaries
            
        Returns:
            HTML with rewritten URLs
        """
        if not attachments:
            return html_content
        
        # Process each attachment
        for attachment in attachments:
            download_url = attachment.get('download_url', '')
            local_path = attachment.get('local_path', '')
            
            if not download_url or not local_path:
                continue
            
            # Get just the filename from the local path
            local_filename = Path(local_path).name
            local_ref = f'attachments/{local_filename}'
            
            # Parse the download URL to extract the path
            from urllib.parse import urlparse, unquote
            parsed_url = urlparse(download_url)
            download_path = parsed_url.path
            
            # Remove query string from path if present
            clean_path = download_path.split('?')[0] if '?' in download_path else download_path
            
            # Generate variations of the URL (like the bash script does)
            # 1. Absolute URL (with base URL)
            absolute_url = download_url.split('?')[0] if '?' in download_url else download_url
            
            # 2. Path with /wiki prefix
            wiki_path = clean_path if clean_path.startswith('/wiki') else f'/wiki{clean_path}'
            
            # 3. Path without /wiki prefix
            plain_path = clean_path[5:] if clean_path.startswith('/wiki') else clean_path
            if not plain_path.startswith('/'):
                plain_path = '/' + plain_path
            
            # 4. Path without leading slash
            plain_no_slash = plain_path.lstrip('/')
            
            # 5. Just the filename
            file_name = clean_path.split('/')[-1]
            
            # Replace all variations using regex to handle query strings
            # This replicates the Perl regex replacements from the bash script
            import re
            
            # Escape special regex characters in URLs
            def escape_for_regex(s):
                return re.escape(s)
            
            # Pattern to match URL with optional query string: url(?:\?[^"']*)?
            patterns_to_replace = [
                # 1. Absolute URL (full with base)
                (escape_for_regex(absolute_url) + r'(?:\?[^"\'\s>]*)?', local_ref),
                # 2. Wiki path
                (escape_for_regex(wiki_path) + r'(?:\?[^"\'\s>]*)?', local_ref),
                # 3. Plain path
                (escape_for_regex(plain_path) + r'(?:\?[^"\'\s>]*)?', local_ref),
                # 4. Plain path without leading slash
                (escape_for_regex(plain_no_slash) + r'(?:\?[^"\'\s>]*)?', local_ref),
                # 5. Thumbnail URLs (common in Confluence)
                (r'https?://[^"\'\s]+/wiki/download/thumbnails/[^"\'\s]*/' + escape_for_regex(file_name) + r'(?:\?[^"\'\s>]*)?', local_ref),
                (r'/wiki/download/thumbnails/[^"\'\s]*/' + escape_for_regex(file_name) + r'(?:\?[^"\'\s>]*)?', local_ref),
            ]
            
            # Apply each replacement pattern
            for pattern, replacement in patterns_to_replace:
                html_content = re.sub(pattern, replacement, html_content)
        
        return html_content
    
    def _convert_to_markdown(self, html_content: str, metadata: dict) -> str:
        """
        Convert HTML to Markdown with metadata header
        
        Args:
            html_content: HTML content
            metadata: Page metadata
            
        Returns:
            Markdown string
        """
        # Add metadata header
        header = f"# {metadata.get('title', 'Confluence Page')}\n\n"
        header += f"**Space:** {metadata.get('space_key', 'N/A')} - {metadata.get('space_name', 'N/A')}\n\n"
        header += f"**Page ID:** {metadata.get('id', 'N/A')}\n\n"
        header += f"**Last Updated:** {metadata.get('history', {}).get('updated', {}).get('when', 'N/A')}\n\n"
        header += "---\n\n"
        
        # Convert HTML to Markdown
        try:
            markdown_body = md(
                html_content,
                heading_style="ATX",
                bullets="-",
                convert=['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                        'ul', 'ol', 'li', 'a', 'strong', 'em', 'code', 'pre',
                        'blockquote', 'img', 'table', 'tr', 'td', 'th']
            )
        except Exception as e:
            print(f"⚠️  Error converting to Markdown: {e}")
            markdown_body = html_content
        
        return header + markdown_body


if __name__ == "__main__":
    print("Confluence API Crawler")
    print("=" * 70)
    print("\nThis module requires proper authentication configuration.")
    print("Please ensure you have either:")
    print("  1. A .env file with CONFLUENCE_TOKEN, CONFLUENCE_EMAIL, CONFLUENCE_BASE_URL")
    print("  2. A confluence_token.txt file with your API token")
    print("\nFor usage, import this class in your main crawler script.")
