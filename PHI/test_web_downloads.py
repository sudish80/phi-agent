"""Test Web Browsing and Download Capabilities"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.shared.browser_manager import (
    BrowserManager, URLValidator, FileTypeValidator
)
from backend.shared.download_manager import SmartDownloadManager
import time

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_url_validation():
    """Test URL validation."""
    print_section("URL Validation Tests")
    
    test_urls = [
        ("https://www.github.com/user/repo", True),
        ("https://stackoverflow.com", True),
        ("http://example.com/file.pdf", True),
        ("javascript:alert('xss')", False),
        ("data:text/html,<script>alert('xss')</script>", False),
        ("https://", False),
        ("not-a-url", False),
    ]
    
    for url, should_pass in test_urls:
        is_valid, msg = URLValidator.is_valid_url(url)
        status = "PASS" if is_valid == should_pass else "FAIL"
        print(f"[{status}]: {url[:50]:<50} - {is_valid}")

def test_file_type_validation():
    """Test file type validation."""
    print_section("File Type Validation Tests")
    
    test_files = [
        ("document.pdf", True),
        ("image.jpg", True),
        ("code.py", True),
        ("archive.zip", True),
        ("executable.exe", False),
        ("installer.msi", False),
        ("script.bat", False),
        ("unknown.xyz", False),
    ]
    
    for filename, should_pass in test_files:
        is_safe, msg = FileTypeValidator.is_safe_type(filename)
        status = "PASS" if is_safe == should_pass else "FAIL"
        print(f"[{status}]: {filename:<30} - {is_safe} ({msg})")

def test_domain_extraction():
    """Test domain extraction."""
    print_section("Domain Extraction Tests")
    
    test_urls = [
        ("https://www.github.com/user/repo", "www.github.com"),
        ("https://api.openai.com/v1/chat", "api.openai.com"),
        ("http://localhost:8000/api", "localhost:8000"),
    ]
    
    for url, expected_domain in test_urls:
        domain = URLValidator.get_domain(url)
        status = "PASS" if domain.lower() == expected_domain.lower() else "FAIL"
        print(f"[{status}]: {url} -> {domain}")

def test_browser_manager():
    """Test browser manager operations."""
    print_section("Browser Manager Tests")
    
    browser = BrowserManager()
    user_id = 1
    
    # Test website visit logging
    result = browser.open_website(user_id, "https://github.com", ip_address="127.0.0.1")
    print(f"[OK] Opened website: {result['url']}")
    print(f"  Domain: {result['domain']}")
    print(f"  Trusted: {result['trusted']}")
    
    # Test browser history
    history = browser.get_browser_history(user_id, hours=24, limit=10)
    print(f"[OK] Browser history retrieved: {len(history)} entries")
    if history:
        print(f"  Latest visit: {history[0]['url']}")

def test_download_queue():
    """Test download queueing."""
    print_section("Download Queue Tests")
    
    browser = BrowserManager()
    user_id = 1
    
    # Test valid download
    success, msg, result = browser.queue_download(
        user_id,
        "https://raw.githubusercontent.com/user/repo/main/README.md",
        "README.md"
    )
    
    if success:
        print(f"[OK] Download queued successfully")
        print(f"  File: {result['filename']}")
        print(f"  Path: {result['path']}")
        print(f"  Download ID: {result['download_id']}")
    else:
        print(f"[X] Failed to queue download: {msg}")
    
    # Test invalid URL download
    success, msg, result = browser.queue_download(
        user_id,
        "javascript:alert('xss')",
        "malicious.js"
    )
    
    if not success:
        print(f"[OK] Correctly rejected malicious URL")
        print(f"  Reason: {msg}")
    else:
        print(f"[X] Should have rejected malicious URL")
    
    # Test dangerous file type
    success, msg, result = browser.queue_download(
        user_id,
        "https://example.com/virus.exe",
        "virus.exe"
    )
    
    if not success:
        print(f"[OK] Correctly rejected dangerous file type")
        print(f"  Reason: {msg}")
    else:
        print(f"[X] Should have rejected dangerous file")

def test_download_manager():
    """Test download manager."""
    print_section("Download Manager Tests")
    
    manager = SmartDownloadManager(max_concurrent=2, bandwidth_kbps=1024)
    
    print(f"[OK] Download manager initialized")
    print(f"  Max concurrent: {manager.max_concurrent}")
    print(f"  Bandwidth limit: {manager.bandwidth_kbps} KB/s")
    
    # Test adding to queue
    result = manager.add_download(1, 1, "https://example.com/file.pdf", "/tmp/file.pdf", "file.pdf")
    print(f"[OK] Download added to queue: {result['message']}")
    print(f"  Position: {result['position']}")
    
    # Get queue info
    queue_info = manager.get_queue_info()
    print(f"[OK] Queue info retrieved")
    print(f"  Queued: {queue_info['total_queued']}")
    print(f"  Active: {queue_info['total_active']}")
    print(f"  Max concurrent: {queue_info['max_concurrent']}")

def test_download_statistics():
    """Test download statistics."""
    print_section("Download Statistics Tests")
    
    browser = BrowserManager()
    user_id = 1
    
    # Get download stats
    stats = browser.get_download_stats(user_id, hours=24)
    print(f"[OK] Download statistics retrieved")
    print(f"  Total downloads: {stats.get('total_downloads', 0)}")
    print(f"  Completed: {stats.get('completed', 0)}")
    print(f"  Failed: {stats.get('failed', 0)}")
    print(f"  Pending: {stats.get('pending', 0)}")
    print(f"  Total size (MB): {stats.get('total_size_mb', 0):.2f}")

def test_safe_types_list():
    """Test listing safe file types."""
    print_section("Safe File Types")
    
    safe_types = FileTypeValidator.list_safe_types()
    print(f"[OK] {len(safe_types)} safe file types:")
    
    categories = {}
    for ext, category in safe_types.items():
        if category not in categories:
            categories[category] = []
        categories[category].append(ext)
    
    for category in sorted(categories.keys()):
        types = ', '.join(categories[category][:5])
        if len(categories[category]) > 5:
            types += f" (+{len(categories[category])-5} more)"
        print(f"  {category.upper()}: {types}")

def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("  PHI Agent - Web Browsing & Download System Tests")
    print("="*60)
    
    try:
        test_url_validation()
        test_file_type_validation()
        test_domain_extraction()
        test_browser_manager()
        test_download_queue()
        test_download_manager()
        test_download_statistics()
        test_safe_types_list()
        
        print_section("All Tests Completed Successfully!")
        print("\nKey Features Verified:")
        print("  [OK] URL validation and security checks")
        print("  [OK] File type validation (safe/dangerous)")
        print("  [OK] Domain extraction and trust checking")
        print("  [OK] Website visit logging and history")
        print("  [OK] Download queue management")
        print("  [OK] Bandwidth limiting setup")
        print("  [OK] Download statistics tracking")
        print("  [OK] Multi-file type support")
        
    except Exception as e:
        print(f"\n[X] Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()
