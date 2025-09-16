#!/usr/bin/env python3
"""
Installation script for Python Web Crawler
Handles environment setup and dependency installation
"""
import os
import sys
import subprocess
import platform
from pathlib import Path

def run_command(cmd, capture_output=True, text=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=text)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python {version.major}.{version.minor} is not supported. Please use Python 3.8 or higher.")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def detect_environment():
    """Detect if we're in a special environment"""
    is_dev_container = os.environ.get('REMOTE_CONTAINERS') == 'true'
    is_codespace = os.environ.get('CODESPACES') == 'true'
    is_colab = 'google.colab' in sys.modules
    is_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    print(f"🔍 Environment detection:")
    print(f"   - Dev Container: {is_dev_container}")
    print(f"   - GitHub Codespace: {is_codespace}")
    print(f"   - Google Colab: {is_colab}")
    print(f"   - Virtual Environment: {is_venv}")
    print(f"   - Platform: {platform.system()} {platform.release()}")
    
    return {
        'dev_container': is_dev_container,
        'codespace': is_codespace,
        'colab': is_colab,
        'venv': is_venv,
        'platform': platform.system()
    }

def setup_virtual_environment():
    """Set up virtual environment if needed"""
    env = detect_environment()
    
    # Skip virtual environment in special environments
    if env['dev_container'] or env['codespace'] or env['colab']:
        print("🏗️ Special environment detected, skipping virtual environment creation")
        return True
    
    if env['venv']:
        print("✅ Already in a virtual environment")
        return True
    
    venv_path = Path('.venv')
    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True
    
    print("🏗️ Creating virtual environment...")
    success, stdout, stderr = run_command(f"{sys.executable} -m venv .venv")
    
    if not success:
        print(f"❌ Failed to create virtual environment: {stderr}")
        return False
    
    print("✅ Virtual environment created successfully")
    return True

def get_pip_command():
    """Get the appropriate pip command for the current environment"""
    env = detect_environment()
    
    # In virtual environment
    if Path('.venv/bin/python').exists():
        return '.venv/bin/python -m pip'
    elif Path('.venv/Scripts/python.exe').exists():  # Windows
        return '.venv/Scripts/python.exe -m pip'
    
    # Use system Python pip
    return f"{sys.executable} -m pip"

def install_dependencies():
    """Install required dependencies"""
    print("📦 Installing dependencies...")
    
    # Get pip command
    pip_cmd = get_pip_command()
    print(f"📍 Using pip command: {pip_cmd}")
    
    # Check if externally managed environment
    success, stdout, stderr = run_command(f"{pip_cmd} --version")
    if not success:
        print(f"❌ Pip not available: {stderr}")
        return False
    
    # Upgrade pip first
    print("🔄 Upgrading pip...")
    upgrade_cmd = f"{pip_cmd} install --upgrade pip"
    
    # Try with --break-system-packages for externally managed environments
    env = detect_environment()
    if env['dev_container'] or env['codespace']:
        upgrade_cmd += " --break-system-packages"
    
    success, stdout, stderr = run_command(upgrade_cmd)
    if not success and "externally-managed-environment" in stderr:
        print("⚠️ Externally managed environment detected, using --break-system-packages")
        upgrade_cmd += " --break-system-packages"
        success, stdout, stderr = run_command(upgrade_cmd)
    
    if success:
        print("✅ Pip upgraded successfully")
    else:
        print(f"⚠️ Pip upgrade failed, continuing anyway: {stderr}")
    
    # Install from requirements.txt
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    install_cmd = f"{pip_cmd} install -r requirements.txt"
    
    # Add --break-system-packages if needed
    if env['dev_container'] or env['codespace']:
        install_cmd += " --break-system-packages"
    
    print(f"📥 Installing packages from requirements.txt...")
    success, stdout, stderr = run_command(install_cmd)
    
    if not success and "externally-managed-environment" in stderr:
        print("⚠️ Retrying with --break-system-packages...")
        install_cmd += " --break-system-packages"
        success, stdout, stderr = run_command(install_cmd)
    
    if success:
        print("✅ All dependencies installed successfully")
        return True
    else:
        print(f"❌ Failed to install dependencies: {stderr}")
        return False

def verify_installation():
    """Verify that all dependencies are properly installed"""
    print("🔍 Verifying installation...")
    
    dependencies = [
        ('requests', 'requests'),
        ('bs4', 'beautifulsoup4'),
        ('markdownify', 'markdownify'),
        ('yaml', 'PyYAML'),
        ('rich', 'rich')
    ]
    
    python_cmd = sys.executable
    if Path('.venv/bin/python').exists():
        python_cmd = '.venv/bin/python'
    elif Path('.venv/Scripts/python.exe').exists():
        python_cmd = '.venv/Scripts/python.exe'
    
    all_ok = True
    for import_name, package_name in dependencies:
        success, stdout, stderr = run_command(f"{python_cmd} -c \"import {import_name}; print('OK')\"")
        if success:
            print(f"   ✅ {package_name}")
        else:
            print(f"   ❌ {package_name} - {stderr}")
            all_ok = False
    
    return all_ok

def main():
    """Main installation process"""
    print("🚀 Python Web Crawler Installation")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Detect environment
    env = detect_environment()
    
    # Setup virtual environment (if needed)
    if not setup_virtual_environment():
        print("❌ Failed to setup virtual environment")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    # Verify installation
    if not verify_installation():
        print("❌ Installation verification failed")
        sys.exit(1)
    
    print("\n🎉 Installation completed successfully!")
    print("\n📋 Next steps:")
    
    if not env['venv'] and not env['dev_container'] and not env['codespace']:
        print("1. Activate the virtual environment:")
        if env['platform'] == 'Windows':
            print("   .venv\\Scripts\\activate")
        else:
            print("   source .venv/bin/activate")
    
    print("2. Configure the crawler:")
    print("   cp config/config.yml.example config/config.yml")
    print("   # Edit config/config.yml with your settings")
    
    print("3. Run the crawler:")
    if Path('.venv/bin/python').exists():
        print("   .venv/bin/python src/web_crawler.py")
    elif Path('.venv/Scripts/python.exe').exists():
        print("   .venv\\Scripts\\python.exe src\\web_crawler.py")
    else:
        print("   python src/web_crawler.py")

if __name__ == "__main__":
    main()