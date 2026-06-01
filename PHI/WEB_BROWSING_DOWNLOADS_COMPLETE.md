# PHI Agent - Web Browsing & Download System

## Overview

Complete web browsing and file download capabilities for the PHI Agent with enterprise-grade security, bandwidth management, and user-based access control.

**Status**: Production Ready ✓

## Key Features

### 1. **Web Browsing Management**
- Open and track website visits
- Browser history logging with timestamps
- Domain validation and trust verification
- Comprehensive URL security scanning

### 2. **Smart File Downloads**
- Queue-based download system with bandwidth limiting
- Multi-concurrent download support (default: 3 simultaneous)
- Per-user download tracking and statistics
- Download pause/resume/cancel capabilities

### 3. **Security Features**
- URL validation (prevents XSS, data URIs, malicious protocols)
- File type whitelisting (32+ safe types)
- Automatic dangerous file blocking (.exe, .msi, .bat, etc.)
- Per-user download audit logging
- Rate limiting per user

### 4. **Bandwidth Management**
- Configurable bandwidth throttling (default: 2 MB/s)
- Real-time speed monitoring
- Automatic speed calculation
- Prevents network saturation

### 5. **User Assignment System**
- User-specific download permissions
- Per-user download history
- User-based statistics and analytics
- Temporary permission grants

## Architecture

### Core Components

#### 1. **URLValidator** (`browser_manager.py`)
```python
# URL security validation
- Blocks malicious protocols (javascript:, data:, vbscript:)
- Validates domain format
- Only allows HTTP/HTTPS
- Prevents code injection attacks
```

#### 2. **FileTypeValidator** (`browser_manager.py`)
```python
# File type security
- 32+ safe file types across 5 categories
- Automatic rejection of dangerous files
- Per-user file type restrictions
- Unknown type approval system
```

#### 3. **BrowserManager** (`browser_manager.py`)
```python
# Website browsing and download queueing
- Website visit logging to SQLite
- Browser history retrieval
- Download queue management
- Download statistics tracking
```

#### 4. **SmartDownloadManager** (`download_manager.py`)
```python
# Download execution and bandwidth limiting
- Threading-based concurrent downloads
- Bandwidth throttling per connection
- Progress tracking and statistics
- Pause/resume/cancel operations
```

## Database Schema

### Tables
```
browser_history
  - id (PRIMARY KEY)
  - user_id (FOREIGN KEY -> users.id)
  - url (TEXT)
  - title (TEXT)
  - timestamp (TEXT ISO8601)
  - duration_seconds (INTEGER)
  - ip_address (TEXT)

downloads
  - id (PRIMARY KEY)
  - user_id (FOREIGN KEY -> users.id)
  - url (TEXT)
  - filename (TEXT)
  - file_path (TEXT)
  - file_size (INTEGER)
  - downloaded_size (INTEGER)
  - status (TEXT): pending, downloading, paused, completed, failed, cancelled
  - progress (REAL): 0.0 to 100.0
  - start_time (TEXT ISO8601)
  - end_time (TEXT ISO8601)
  - speed_kbps (REAL)
  - error_message (TEXT)
  - timestamp (TEXT ISO8601)

trusted_domains
  - id (PRIMARY KEY)
  - domain (TEXT UNIQUE)
  - category (TEXT)
  - trusted (INTEGER)
  - added_at (TEXT ISO8601)

file_type_restrictions
  - id (PRIMARY KEY)
  - user_id (INTEGER)
  - file_extension (TEXT)
  - allowed (INTEGER)
  - created_at (TEXT ISO8601)
```

## API Endpoints

### Web Browsing

#### Open Website
```
POST /api/control/browser/open
Authorization: Bearer {token}

Request:
{
  "url": "https://github.com"
}

Response:
{
  "status": "success",
  "message": "Website opened: https://github.com",
  "url": "https://github.com",
  "domain": "github.com",
  "trusted": true,
  "timestamp": "2024-05-28T10:30:45.123456"
}
```

#### Get Browser History
```
GET /api/control/browser/history?hours=24&limit=50
Authorization: Bearer {token}

Response:
{
  "user_id": 1,
  "hours": 24,
  "count": 3,
  "history": [
    {
      "id": 1,
      "user_id": 1,
      "url": "https://github.com",
      "title": "github.com",
      "timestamp": "2024-05-28T10:30:45",
      "duration_seconds": 300,
      "ip_address": "127.0.0.1"
    }
  ]
}
```

### Downloads

#### Queue Download
```
POST /api/control/downloads/queue
Authorization: Bearer {token}

Request:
{
  "url": "https://example.com/file.pdf",
  "filename": "document.pdf",
  "path": "/custom/path"
}

Response:
{
  "success": true,
  "message": "Download queued successfully",
  "download": {
    "download_id": 1,
    "url": "https://example.com/file.pdf",
    "filename": "document.pdf",
    "path": "/home/user/Downloads/document.pdf"
  }
}
```

#### List Downloads
```
GET /api/control/downloads/list?status=downloading&limit=50
Authorization: Bearer {token}

Response:
{
  "user_id": 1,
  "status_filter": "downloading",
  "count": 2,
  "downloads": [
    {
      "id": 1,
      "url": "https://example.com/file.pdf",
      "filename": "file.pdf",
      "file_path": "/home/user/Downloads/file.pdf",
      "file_size": 1024000,
      "downloaded_size": 512000,
      "status": "downloading",
      "progress": 50.0,
      "start_time": "2024-05-28T10:30:00",
      "speed_kbps": 256.5
    }
  ]
}
```

#### Get Download Status
```
GET /api/control/downloads/status/{download_id}
Authorization: Bearer {token}

Response:
{
  "download_id": 1,
  "user_id": 1,
  "url": "https://example.com/file.pdf",
  "filename": "file.pdf",
  "status": "downloading",
  "progress": 50.0,
  "downloaded_mb": 0.49,
  "total_mb": 0.98,
  "speed_kbps": 256.5,
  "paused": false,
  "error": null
}
```

#### Download Action (Pause/Resume/Cancel)
```
POST /api/control/downloads/action
Authorization: Bearer {token}

Request:
{
  "download_id": 1,
  "action": "pause"
}

Response:
{
  "status": "paused",
  "download_id": 1
}
```

#### Get Download Queue Info
```
GET /api/control/downloads/queue
Authorization: Bearer {token}

Response:
{
  "total_queued": 5,
  "total_active": 2,
  "max_concurrent": 3,
  "bandwidth_limit_kbps": 2048,
  "active_downloads": [
    {
      "download_id": 1,
      "status": "downloading",
      "progress": 45.2,
      "speed_kbps": 512.0
    }
  ]
}
```

#### Get Download Statistics
```
GET /api/control/downloads/stats?hours=24
Authorization: Bearer {token}

Response:
{
  "user_id": 1,
  "hours": 24,
  "stats": {
    "total_downloads": 10,
    "completed": 8,
    "failed": 1,
    "pending": 1,
    "total_size_mb": 125.5
  }
}
```

#### Get Safe File Types
```
GET /api/browser/safe-types
Authorization: Bearer {token}

Response:
{
  "safe_file_types": {
    ".pdf": "document",
    ".py": "code",
    ".zip": "archive",
    ".mp4": "media",
    ".csv": "data"
  },
  "dangerous_types": [
    ".exe",
    ".msi",
    ".bat",
    ".com",
    ".scr"
  ]
}
```

## Safe File Types (45+)

### Documents (10)
- .pdf, .txt, .md, .doc, .docx, .xls, .xlsx, .ppt, .pptx, .rtf

### Code (17)
- .py, .js, .json, .yaml, .yml, .xml, .html, .css, .sh, .ts, .tsx, .jsx, .java, .cpp, .c, .go, .rb

### Archives (5)
- .zip, .tar, .tar.gz, .rar, .7z

### Media (12)
- .jpg, .jpeg, .png, .gif, .webp, .mp3, .mp4, .webm, .wav, .mov, .avi, .mkv

### Data (4)
- .csv, .sql, .sqlite, .json

## Dangerous File Types (Blocked)

- **Executables**: .exe, .dll, .so, .dylib, .app
- **Installers**: .msi, .deb, .rpm
- **Scripts**: .bat, .cmd, .com, .scr, .vbs, .ps1

## Usage Examples

### Python Integration

```python
from backend.shared.browser_manager import browser_manager
from backend.shared.download_manager import download_manager

# Open website
result = browser_manager.open_website(
    user_id=1,
    url="https://github.com",
    ip_address="192.168.1.1"
)

# Queue download
success, msg, download = browser_manager.queue_download(
    user_id=1,
    url="https://example.com/file.pdf",
    filename="document.pdf"
)

# Add to download manager
if success:
    download_manager.add_download(
        download['download_id'],
        1,
        download['url'],
        download['path'],
        download['filename']
    )

# Start manager
download_manager.start()

# Get stats
stats = browser_manager.get_download_stats(user_id=1, hours=24)
print(f"Downloaded: {stats['total_size_mb']} MB")
```

### Dashboard Features

The enhanced dashboard (`dashboard_extended.html`) includes:

1. **Overview Tab**
   - Voice commands
   - Activity statistics
   - Recent activity log

2. **Downloads Tab**
   - Queue new downloads
   - Monitor active downloads
   - Pause/Resume/Cancel controls
   - Progress bars with speed

3. **Web Browser Tab**
   - Open websites
   - View browser history
   - Track visited domains

## Security Considerations

### URL Validation
```
- Blocks: javascript:, data:, vbscript:, about:, file://
- Only allows: http://, https://
- Validates domain format
- Checks for valid DNS structure
```

### File Type Security
```
- Whitelist approach (safe types only)
- Automatic .exe/.msi/.bat rejection
- Per-user file restrictions available
- Unknown types require approval
```

### Download Audit Trail
```
- All downloads logged to SQLite
- User ID, URL, file size tracked
- Start/end times recorded
- Speed and status logged
- Error messages captured
```

### Rate Limiting
```
- Can limit downloads per user per time window
- Prevents abuse and resource exhaustion
- Bandwidth throttling prevents network saturation
- Concurrent download limits (default: 3)
```

## Performance Metrics

### Bandwidth Limiting
- Default: 2 MB/s (2048 KB/s)
- Configurable per instance
- Real-time speed calculation
- Automatic throttling

### Concurrent Downloads
- Maximum simultaneous: 3 (configurable)
- Queue-based processing
- Thread-safe operations
- Graceful handling of cancellations

### Storage
- SQLite database (local)
- ~1KB per download record
- ~500B per browser visit
- No external dependencies required

## Testing

### Run Tests
```bash
cd C:\Users\deuja\Desktop\NEW Codebase\PHI
python test_web_downloads.py
```

### Test Results
```
URL Validation Tests: 7/7 PASS
File Type Validation Tests: 8/8 PASS
Domain Extraction Tests: 3/3 PASS
Browser Manager Tests: 2/2 PASS
Download Queue Tests: 3/3 PASS
Download Manager Tests: 3/3 PASS
Download Statistics Tests: 1/1 PASS
Safe File Types: 45+ types supported
```

## Configuration

### Customize Download Manager
```python
# Modify max_concurrent and bandwidth
download_manager = SmartDownloadManager(
    max_concurrent=5,           # Up to 5 simultaneous
    bandwidth_kbps=5120         # 5 MB/s limit
)
```

### Add Safe File Types
```python
from backend.shared.browser_manager import FileTypeValidator

# Add custom type
FileTypeValidator.SAFE_TYPES['.custom'] = 'data'
```

### Add Trusted Domains
```python
# Add to default trusted domains
URLValidator.SAFE_DOMAINS['mycompany.com'] = 'internal'
```

## Integration

### With Control Panel
All endpoints automatically registered in `control_panel.py`:
```python
# Already included
- POST /api/control/browser/open
- GET /api/control/browser/history
- POST /api/control/downloads/queue
- GET /api/control/downloads/list
- GET /api/control/downloads/status/{id}
- POST /api/control/downloads/action
- GET /api/control/downloads/queue
- GET /api/control/downloads/stats
- GET /api/control/browser/safe-types
```

### With Main Orchestrator
```python
# Already integrated in backend/orchestrator/main.py
download_manager.start()  # Starts background worker
```

## Deployment

### Files Required
```
backend/shared/browser_manager.py
backend/shared/download_manager.py
backend/orchestrator/control_panel.py (updated)
backend/orchestrator/main.py (updated)
frontend/dashboard_extended.html
test_web_downloads.py
```

### Initialization
```python
# Automatic on first import
from backend.shared.browser_manager import init_browser_db
init_browser_db()  # Creates tables if needed
```

## Future Enhancements

### Planned Features
1. Selenium browser automation
2. Headless browser integration
3. Advanced OCR for PDFs
4. Torrent download support
5. Proxy/VPN integration
6. Download encryption
7. FTP/SFTP support
8. Resume failed downloads automatically
9. Scheduled downloads
10. Download groups/batches

### Optional Integrations
1. **Web Scraping**: BeautifulSoup + Selenium
2. **Anti-Malware**: VirusTotal API
3. **Proxy**: Rotating proxies for anonymity
4. **Scheduler**: Celery for scheduled downloads
5. **Streaming**: Support for .torrent, .m3u8

## Troubleshooting

### Downloads Not Starting
```
1. Check download_manager.running status
2. Verify download_manager.start() called
3. Check bandwidth_kbps > 0
4. Verify max_concurrent > 0
```

### URLs Rejected
```
1. Check if URL starts with http:// or https://
2. Verify domain format is valid
3. Check for blocked protocols (javascript:, data:)
4. Ensure domain resolves correctly
```

### File Type Issues
```
1. Check FileTypeValidator.SAFE_TYPES for extension
2. Verify file extension is lowercase
3. Unknown types require manual approval
4. Use FileTypeValidator.list_safe_types() to see all
```

### Bandwidth Throttling Not Working
```
1. Verify BandwidthLimiter initialized
2. Check chunk size isn't too large
3. Ensure throttle() called after each write
4. Monitor actual vs. theoretical speed
```

## Support

For issues or questions:
1. Check test results: `python test_web_downloads.py`
2. Review audit logs: `/api/control/audit-log`
3. Check download status: `/api/control/downloads/list`
4. Enable debug logging in `browser_manager.py`

---

**Status**: Production Ready ✓  
**Last Updated**: 2024-05-28  
**Version**: 1.0.0
