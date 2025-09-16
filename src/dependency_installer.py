#!/usr/bin/env python3
"""
Automatic dependency installer for Web Crawler
Handles installation of required packages without user intervention
"""
import sys
import subprocess
import importlib
import os
from pathlib import Path

class DependencyInstaller:
    """Manages automatic installation of Python dependencies"""
    
    REQUIRED_PACKAGES = {
        'requests': 'requests>=2.25.0',
        'bs4': 'beautifulsoup4>=4.9.0',
        'markdownify': 'markdownify>=0.11.0',
        'yaml': 'PyYAML>=6.0'
    }
    
    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.installed_packages = []
        self.failed_packages = []
    
    def check_package(self, package_name: str) -> bool:
        """Check if a package is already installed"""
        try:
            importlib.import_module(package_name)
            return True
        except ImportError:
            return False
    
    def install_package(self, package_spec: str) -> bool:
        """Install a single package using pip"""
        try:
            if not self.quiet:
                print(f"📦 Installing {package_spec}...")
            
            # Use subprocess to install via pip
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', package_spec
            ], capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                if not self.quiet:
                    print(f"✅ Successfully installed {package_spec}")
                return True
            else:
                if not self.quiet:
                    print(f"❌ Failed to install {package_spec}: {result.stderr}")
                return False
                
        except Exception as e:
            if not self.quiet:
                print(f"❌ Error installing {package_spec}: {e}")
            return False
    
    def upgrade_pip(self) -> bool:
        """Upgrade pip to latest version"""
        try:
            if not self.quiet:
                print("🔄 Upgrading pip...")
            
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'
            ], capture_output=True, text=True, check=False)
            
            return result.returncode == 0
        except Exception:
            return False
    
    def install_all_dependencies(self, upgrade_pip: bool = True) -> bool:
        """Install all required dependencies"""
        if not self.quiet:
            print("🚀 Checking and installing dependencies...")
        
        # Upgrade pip first
        if upgrade_pip:
            self.upgrade_pip()
        
        all_installed = True
        
        for package_name, package_spec in self.REQUIRED_PACKAGES.items():
            if self.check_package(package_name):
                if not self.quiet:
                    print(f"✓ {package_name} is already installed")
                continue
            
            if self.install_package(package_spec):
                self.installed_packages.append(package_spec)
                
                # Verify installation
                if self.check_package(package_name):
                    if not self.quiet:
                        print(f"✓ {package_name} verified")
                else:
                    if not self.quiet:
                        print(f"⚠️ {package_name} installed but verification failed")
                    all_installed = False
            else:
                self.failed_packages.append(package_spec)
                all_installed = False
        
        return all_installed
    
    def create_requirements_file(self, filename: str = "requirements.txt"):
        """Create a requirements.txt file with all dependencies"""
        try:
            with open(filename, 'w') as f:
                f.write("# Python Web Crawler Dependencies\n")
                f.write("# Auto-generated requirements file\n\n")
                for package_spec in self.REQUIRED_PACKAGES.values():
                    f.write(f"{package_spec}\n")
            
            if not self.quiet:
                print(f"📄 Created {filename}")
            return True
        except Exception as e:
            if not self.quiet:
                print(f"❌ Error creating {filename}: {e}")
            return False
    
    def install_from_requirements(self, filename: str = "requirements.txt") -> bool:
        """Install dependencies from requirements.txt file"""
        if not Path(filename).exists():
            if not self.quiet:
                print(f"❌ Requirements file {filename} not found")
            return False
        
        try:
            if not self.quiet:
                print(f"📦 Installing from {filename}...")
            
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', '-r', filename
            ], capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                if not self.quiet:
                    print(f"✅ Successfully installed from {filename}")
                return True
            else:
                if not self.quiet:
                    print(f"❌ Failed to install from {filename}: {result.stderr}")
                return False
                
        except Exception as e:
            if not self.quiet:
                print(f"❌ Error installing from {filename}: {e}")
            return False
    
    def get_summary(self) -> dict:
        """Get installation summary"""
        return {
            'installed_packages': self.installed_packages,
            'failed_packages': self.failed_packages,
            'total_required': len(self.REQUIRED_PACKAGES),
            'successfully_installed': len(self.installed_packages),
            'failed_installs': len(self.failed_packages)
        }

def auto_install_dependencies(quiet: bool = False) -> bool:
    """Main function to automatically install all dependencies"""
    installer = DependencyInstaller(quiet=quiet)
    
    try:
        success = installer.install_all_dependencies()
        
        if not quiet:
            summary = installer.get_summary()
            print(f"\n📊 Installation Summary:")
            print(f"   Required packages: {summary['total_required']}")
            print(f"   Successfully installed: {summary['successfully_installed']}")
            print(f"   Failed installs: {summary['failed_installs']}")
            
            if summary['installed_packages']:
                print(f"   New packages: {', '.join(summary['installed_packages'])}")
            
            if summary['failed_packages']:
                print(f"   ❌ Failed packages: {', '.join(summary['failed_packages'])}")
        
        return success
        
    except Exception as e:
        if not quiet:
            print(f"❌ Error during dependency installation: {e}")
        return False

def check_dependencies_only() -> tuple:
    """Check which dependencies are missing without installing"""
    installer = DependencyInstaller(quiet=True)
    missing = []
    installed = []
    
    for package_name, package_spec in installer.REQUIRED_PACKAGES.items():
        if installer.check_package(package_name):
            installed.append(package_name)
        else:
            missing.append(package_spec)
    
    return installed, missing

if __name__ == "__main__":
    # Command line interface
    import argparse
    
    parser = argparse.ArgumentParser(description="Web Crawler Dependency Installer")
    parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode')
    parser.add_argument('--check-only', '-c', action='store_true', help='Only check dependencies')
    parser.add_argument('--create-requirements', '-r', action='store_true', help='Create requirements.txt')
    
    args = parser.parse_args()
    
    if args.check_only:
        installed, missing = check_dependencies_only()
        print(f"Installed: {installed}")
        print(f"Missing: {missing}")
        sys.exit(0 if not missing else 1)
    
    if args.create_requirements:
        installer = DependencyInstaller(quiet=args.quiet)
        installer.create_requirements_file()
        sys.exit(0)
    
    # Default: install all dependencies
    success = auto_install_dependencies(quiet=args.quiet)
    sys.exit(0 if success else 1)