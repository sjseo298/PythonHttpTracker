#!/usr/bin/env python3
"""
Confluence Authentication Manager
Handles loading and managing Confluence API credentials
"""
import os
from pathlib import Path
from typing import Optional, Dict


class ConfluenceAuth:
    """
    Manages authentication and configuration for Confluence API
    Supports loading from .env file and confluence_token.txt
    """
    
    def __init__(self, auth_config: Optional[Dict] = None):
        """
        Initialize Confluence authentication
        
        Args:
            auth_config: Optional dict with 'email', 'token', and 'base_url'
                        If None, will attempt to load from files
        """
        self.email = None
        self.token = None
        self.base_url = None
        self.is_configured = False
        
        if auth_config:
            self.email = auth_config.get('email')
            self.token = auth_config.get('token')
            self.base_url = auth_config.get('base_url')
            self.is_configured = bool(self.email and self.token and self.base_url)
        else:
            self._load_from_files()
    
    def _load_from_files(self):
        """
        Load credentials from files in this priority order:
        1. config/.env (highest priority)
        2. .env (root directory)
        3. confluence_token.txt (fallback)
        """
        # Try .env files first
        if self._load_from_env():
            self.is_configured = bool(self.email and self.token and self.base_url)
            return
        
        # Fallback to confluence_token.txt
        if self._load_from_token_file():
            self.is_configured = bool(self.email and self.token and self.base_url)
            return
        
        # No credentials found
        self.is_configured = False
    
    def _load_from_env(self) -> bool:
        """
        Load credentials from .env file
        
        Returns:
            True if credentials were loaded successfully
        """
        # Check both possible .env locations
        env_paths = [
            Path('config/.env'),
            Path('.env')
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                try:
                    with open(env_path, 'r', encoding='utf-8') as f:
                        env_vars = {}
                        for line in f:
                            line = line.strip()
                            # Skip comments and empty lines
                            if line and not line.startswith('#'):
                                if '=' in line:
                                    key, value = line.split('=', 1)
                                    key = key.strip()
                                    value = value.strip()
                                    # Remove quotes if present
                                    if value.startswith('"') and value.endswith('"'):
                                        value = value[1:-1]
                                    elif value.startswith("'") and value.endswith("'"):
                                        value = value[1:-1]
                                    env_vars[key] = value
                        
                        # Extract Confluence credentials
                        self.token = env_vars.get('CONFLUENCE_TOKEN', '')
                        self.email = env_vars.get('CONFLUENCE_EMAIL', '')
                        self.base_url = env_vars.get('CONFLUENCE_BASE_URL', '')
                        
                        if self.token and self.email and self.base_url:
                            print(f"✅ Loaded Confluence credentials from {env_path}")
                            return True
                
                except Exception as e:
                    print(f"⚠️  Error reading {env_path}: {e}")
                    continue
        
        return False
    
    def _load_from_token_file(self) -> bool:
        """
        Load token from confluence_token.txt (legacy method)
        
        Returns:
            True if token was loaded successfully
        """
        token_file = Path('confluence_token.txt')
        
        if token_file.exists():
            try:
                self.token = token_file.read_text().strip()
                
                if self.token:
                    print(f"✅ Loaded Confluence token from {token_file}")
                    print("⚠️  Note: confluence_token.txt found. Consider migrating to .env")
                    print("   Email and base_url must be set in config.yml or .env")
                    
                    # Try to get email and base_url from config.yml
                    self._load_email_and_base_from_config()
                    
                    return bool(self.token and self.email and self.base_url)
            
            except Exception as e:
                print(f"⚠️  Error reading {token_file}: {e}")
        
        return False
    
    def _load_email_and_base_from_config(self):
        """
        Try to load email and base_url from config.yml when using token file
        """
        try:
            import yaml
            config_path = Path('config/config.yml')
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    
                    if config:
                        # Get base_url from website configuration
                        self.base_url = config.get('website', {}).get('base_url', '')
                        
                        # Check for confluence-specific config
                        confluence_config = config.get('confluence', {})
                        if confluence_config:
                            self.email = confluence_config.get('email', '')
                            if not self.base_url:
                                self.base_url = confluence_config.get('base_url', '')
                        
                        if self.email and self.base_url:
                            print(f"✅ Loaded email and base_url from config.yml")
        
        except Exception as e:
            print(f"⚠️  Could not load email/base_url from config.yml: {e}")
    
    def get_api_base_url(self) -> str:
        """
        Get the base URL for Confluence REST API
        
        Returns:
            API base URL (e.g., https://domain.com/wiki/rest/api)
        """
        if not self.base_url:
            return ''
        
        base = self.base_url.rstrip('/')
        
        # Add /wiki/rest/api if not present
        if '/rest/api' not in base:
            if '/wiki' in base:
                # Already has /wiki, just add /rest/api
                base = base.rstrip('/') + '/rest/api'
            else:
                # Add both /wiki and /rest/api
                base = base + '/wiki/rest/api'
        
        return base
    
    def get_auth_tuple(self) -> tuple:
        """
        Get authentication tuple for requests library
        
        Returns:
            Tuple of (email, token) for HTTP Basic Auth
        """
        return (self.email, self.token)
    
    def is_valid(self) -> bool:
        """
        Check if authentication is properly configured
        
        Returns:
            True if email, token, and base_url are all set
        """
        return self.is_configured and bool(self.email and self.token and self.base_url)
    
    def get_headers(self) -> dict:
        """
        Get HTTP headers for API requests
        
        Returns:
            Dictionary of headers
        """
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    @staticmethod
    def create_env_template(target_path: Optional[Path] = None):
        """
        Create a template .env file
        
        Args:
            target_path: Where to create the template (default: config/.env.template)
        """
        if target_path is None:
            target_path = Path('config/.env.template')
        
        env_template = """# Confluence API Configuration
# Copy this file to .env and fill in your credentials
# DO NOT commit .env to version control!

# Your Confluence instance base URL
CONFLUENCE_BASE_URL=https://your-domain.atlassian.net

# Your Atlassian account email
CONFLUENCE_EMAIL=your-email@example.com

# Your Confluence API token
# Create one at: https://id.atlassian.com/manage-profile/security/api-tokens
CONFLUENCE_TOKEN=your-api-token-here

# Optional: Override crawling settings
# MAX_DEPTH=3
# MAX_WORKERS=8
"""
        
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(env_template, encoding='utf-8')
            print(f"✅ Created .env template at {target_path}")
            print(f"   Copy it to .env and fill in your credentials")
        except Exception as e:
            print(f"❌ Error creating .env template: {e}")
    
    @staticmethod
    def migrate_from_token_file():
        """
        Interactive migration from confluence_token.txt to .env
        """
        token_file = Path('confluence_token.txt')
        
        if not token_file.exists():
            print("⚠️  No confluence_token.txt file found")
            return False
        
        try:
            token = token_file.read_text().strip()
            
            print("\n📦 Migrating from confluence_token.txt to .env")
            print("=" * 60)
            
            email = input("Confluence email: ").strip()
            base_url = input("Base URL (e.g., https://your-domain.atlassian.net): ").strip()
            
            if not email or not base_url:
                print("❌ Email and base URL are required")
                return False
            
            # Create .env file
            env_content = f"""# Confluence API Configuration
CONFLUENCE_BASE_URL={base_url}
CONFLUENCE_EMAIL={email}
CONFLUENCE_TOKEN={token}
"""
            
            env_path = Path('config/.env')
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(env_content, encoding='utf-8')
            
            print(f"\n✅ Created {env_path}")
            print("   Your credentials are now stored securely in .env")
            print("   You can safely delete confluence_token.txt if desired")
            
            return True
        
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            return False
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        if self.is_valid():
            return f"ConfluenceAuth(email={self.email}, base_url={self.base_url}, configured=True)"
        else:
            return "ConfluenceAuth(configured=False)"


if __name__ == "__main__":
    # Test authentication loading
    print("Testing Confluence Authentication\n")
    
    auth = ConfluenceAuth()
    
    if auth.is_valid():
        print(f"\n✅ Authentication configured successfully")
        print(f"   Email: {auth.email}")
        print(f"   Base URL: {auth.base_url}")
        print(f"   API Base: {auth.get_api_base_url()}")
        print(f"   Token: {auth.token[:10]}..." if auth.token else "   Token: None")
    else:
        print(f"\n❌ Authentication not configured")
        print("\nTo configure Confluence API access:")
        print("1. Create a .env file in the config/ directory")
        print("2. Add your credentials:")
        print("   CONFLUENCE_BASE_URL=https://your-domain.atlassian.net")
        print("   CONFLUENCE_EMAIL=your-email@example.com")
        print("   CONFLUENCE_TOKEN=your-api-token")
        print("\nOr run: python -c 'from src.confluence_auth import ConfluenceAuth; ConfluenceAuth.create_env_template()'")
