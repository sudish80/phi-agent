# Quick Start - Web Browsing & Downloads

## 5-Minute Setup

### 1. Initialize System
```python
from backend.shared.browser_manager import browser_manager, download_manager
from backend.shared.download_manager import SmartDownloadManager

# Already initialized on import
# Database tables created automatically
```

### 2. Start Server
```bash
cd C:\Users\deuja\Desktop\NEW Codebase\PHI
python backend/orchestrator/main.py
```

### 3. Access Dashboard
```
http://localhost:8000/dashboard_extended.html
```

## Common Tasks

### Open a Website
```python
result = browser_manager.open_website(
    user_id=1,
    url="https://github.com",
    ip_address="127.0.0.1"
)
print(result['status'])  # "success"
```

### Queue a File Download
```python
success, msg, download = browser_manager.queue_download(
    user_id=1,
    url="https://example.com/file.pdf",
    filename="document.pdf"
)

if success:
    print(f"Download ID: {download['download_id']}")
    print(f"File: {download['filename']}")
```

### Get Browser History
```python
history = browser_manager.get_browser_history(
    user_id=1,
    hours=24,
    limit=20
)

for visit in history:
    print(f"{visit['timestamp']}: {visit['url']}")
```

### Get Downloads
```python
downloads = browser_manager.get_downloads(
    user_id=1,
    status="downloading"
)

for dl in downloads:
    print(f"{dl['filename']}: {dl['progress']}%")
```

### Pause a Download
```python
result = download_manager.pause_download(download_id=1)
print(result['status'])  # "paused"
```

### Resume a Download
```python
result = download_manager.resume_download(download_id=1)
print(result['status'])  # "resumed"
```

### Cancel a Download
```python
result = download_manager.cancel_download(download_id=1)
print(result['status'])  # "cancelled"
```

## API Quick Reference

### Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/control/browser/open` | Open website |
| GET | `/api/control/browser/history` | Get browser history |
| POST | `/api/control/downloads/queue` | Queue download |
| GET | `/api/control/downloads/list` | List downloads |
| GET | `/api/control/downloads/status/{id}` | Get download status |
| POST | `/api/control/downloads/action` | Pause/Resume/Cancel |
| GET | `/api/control/downloads/queue` | Get queue info |
| GET | `/api/control/downloads/stats` | Get statistics |
| GET | `/api/control/browser/safe-types` | List safe types |

### cURL Examples

#### Open Website
```bash
curl -X POST http://localhost:8000/api/control/browser/open \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com"}'
```

#### Queue Download
```bash
curl -X POST http://localhost:8000/api/control/downloads/queue \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/file.pdf"}'
```

#### Get Downloads
```bash
curl -X GET http://localhost:8000/api/control/downloads/list \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Pause Download
```bash
curl -X POST http://localhost:8000/api/control/downloads/action \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"download_id": 1, "action": "pause"}'
```

## Dashboard Usage

### Downloads Tab
1. Enter URL in "Download URL" field
2. Click "Queue Download"
3. Monitor progress in "Active Downloads"
4. Use Pause/Cancel buttons to control

### Browser Tab
1. Enter URL in "Website URL" field
2. Click "Open Website"
3. View history below

### Overview Tab
1. See statistics and activity
2. Send voice commands
3. Control zoom level
4. Exit system

## Validation Rules

### URLs Must
- Start with `http://` or `https://`
- Have valid domain format
- Not contain: `javascript:`, `data:`, `vbscript:`

### Files Must
- Have safe extension (.pdf, .zip, .py, etc.)
- Not be executable (.exe, .msi, .bat)
- Not be installer (.deb, .rpm, .app)

### Downloads Limited By
- Max 3 concurrent (configurable)
- 2 MB/s bandwidth (configurable)
- Per-user rate limits (configurable)

## Database Queries

### Get Recent Downloads
```sql
SELECT * FROM downloads 
WHERE user_id = 1 
ORDER BY timestamp DESC 
LIMIT 10;
```

### Get Browser History
```sql
SELECT url, timestamp FROM browser_history 
WHERE user_id = 1 
ORDER BY timestamp DESC 
LIMIT 20;
```

### Get Download Statistics
```sql
SELECT status, COUNT(*), SUM(file_size) 
FROM downloads 
WHERE user_id = 1 
GROUP BY status;
```

## Environment Variables

### Configuration
```python
# In download_manager.py
MAX_CONCURRENT_DOWNLOADS = 3
BANDWIDTH_LIMIT_KBPS = 2048
DOWNLOAD_CHUNK_SIZE = 8192
```

### Database
```
DB_PATH = phi_audit.db (SQLite)
```

## Troubleshooting

### Problem: Downloads not starting
**Solution**: Call `download_manager.start()` after importing

### Problem: URL rejected
**Solution**: Ensure URL starts with `http://` or `https://`

### Problem: File type not allowed
**Solution**: Check `FileTypeValidator.list_safe_types()` or approve manually

### Problem: Slow downloads
**Solution**: Check bandwidth throttling (default 2 MB/s)

## Testing

### Run Full Test Suite
```bash
python test_web_downloads.py
```

### Expected Output
```
[PASS]: URL validation tests
[PASS]: File type validation
[PASS]: Domain extraction
[PASS]: Browser history
[PASS]: Download queueing
[PASS]: Download statistics
All Tests Completed Successfully!
```

## Next Steps

1. **Integration**: Add to your application
2. **Customization**: Adjust bandwidth/concurrent limits
3. **Monitoring**: Check audit logs regularly
4. **Enhancement**: Add custom file types as needed

## Support

- Dashboard: `http://localhost:8000/dashboard_extended.html`
- Docs: `WEB_BROWSING_DOWNLOADS_COMPLETE.md`
- Tests: `test_web_downloads.py`
- Logs: `phi_audit.db` (SQLite database)
