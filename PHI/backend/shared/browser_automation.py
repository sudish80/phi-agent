"""
Browser Automation System with Playwright
- Full browser control: navigate, fill forms, click, login, screenshot
- Session/cookie management for login persistence
- User permission approval for every action
- Real file download interception
- Audit logging of all browser actions
"""

import asyncio
import sqlite3
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')


class PlaywrightManager:
    """Manages Playwright browser instances and sessions"""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._sessions = {}  # user_id -> session data
        self._pending_actions = {}  # user_id -> pending approvals
        self._downloads = {}
        self._current_url = None
        self._initialized = False

    async def _ensure(self):
        """Ensure Playwright is initialized"""
        if self._initialized:
            return
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            self._context = await self._browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self._context.set_default_timeout(30000)
            self._page = await self._context.new_page()

            # Intercept downloads
            self._page.on('download', self._on_download)

            # Listen for page close/reset
            self._page.on('close', lambda: None)

            self._initialized = True
            logger.info("Playwright browser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise

    async def _on_download(self, download):
        """Intercept file downloads from browser and save to disk."""
        from backend.shared.download_engine import DOWNLOAD_DIR
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        try:
            filename = download.suggested_filename or f"download_{int(time.time())}"
            dest = os.path.join(DOWNLOAD_DIR, filename)
            await download.save_as(dest)
            info = {
                'url': download.url,
                'suggested_filename': filename,
                'filepath': dest,
                'status': 'completed',
                'start_time': time.time(),
                'size_bytes': os.path.getsize(dest) if os.path.exists(dest) else 0,
            }
            dl_id = len(self._downloads) + 1
            self._downloads[dl_id] = info
            logger.info(f"Download saved: {filename} -> {dest}")
            return dl_id
        except Exception as e:
            logger.error(f"Download interception error: {e}")
            return None

    async def navigate(self, user_id: int, url: str, 
                      wait_until: str = 'domcontentloaded') -> Dict:
        """Navigate to a URL"""
        await self._ensure()
        try:
            response = await self._page.goto(url, wait_until=wait_until)
            self._current_url = self._page.url

            title = await self._page.title()
            content_snippet = await self._get_content_snippet()

            self._log_action(user_id, 'navigate', url, {'title': title})

            return {
                'status': 'success',
                'url': self._page.url,
                'title': title,
                'status_code': response.status if response else None,
                'content_snippet': content_snippet
            }
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return {'status': 'error', 'message': str(e)}

    async def click(self, user_id: int, selector: str) -> Dict:
        """Click on an element by selector"""
        await self._ensure()
        try:
            await self._page.click(selector)
            await self._page.wait_for_load_state('domcontentloaded')
            self._current_url = self._page.url
            title = await self._page.title()

            self._log_action(user_id, 'click', selector, {'title': title})

            return {
                'status': 'success',
                'url': self._page.url,
                'title': title
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def type_text(self, user_id: int, selector: str, text: str) -> Dict:
        """Type text into an input field"""
        await self._ensure()
        try:
            await self._page.fill(selector, text)
            self._log_action(user_id, 'type', selector, {'field_length': len(text)})
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def fill_form(self, user_id: int, fields: Dict[str, str]) -> Dict:
        """Fill multiple form fields at once: fields = {selector: value}"""
        await self._ensure()
        results = []
        for selector, value in fields.items():
            try:
                await self._page.fill(selector, value)
                results.append({'selector': selector, 'status': 'filled'})
            except Exception as e:
                results.append({'selector': selector, 'status': 'error', 'message': str(e)})

        self._log_action(user_id, 'fill_form', json.dumps(list(fields.keys())),
                        {'fields_filled': sum(1 for r in results if r['status'] == 'filled')})

        return {'status': 'success', 'results': results}

    async def login(self, user_id: int, url: str, 
                   username_selector: str, password_selector: str,
                   username: str, password: str,
                   submit_selector: str = None,
                   save_session: bool = True) -> Dict:
        """Login to a website"""
        await self._ensure()
        try:
            await self._page.goto(url, wait_until='domcontentloaded')
            await self._page.fill(username_selector, username)
            await self._page.fill(password_selector, password)

            if submit_selector:
                await self._page.click(submit_selector)
            else:
                await self._page.keyboard.press('Enter')

            await self._page.wait_for_load_state('domcontentloaded')
            time.sleep(2)

            title = await self._page.title()
            current_url = self._page.url

            login_success = current_url != url and 'login' not in current_url.lower()

            self._log_action(user_id, 'login', url, {
                'success': login_success,
                'current_url': current_url,
                'title': title
            })

            # Save session cookies if login successful
            if login_success and save_session:
                await self.save_session(user_id)

            return {
                'status': 'success' if login_success else 'login_failed',
                'current_url': current_url,
                'title': title,
                'message': 'Login successful' if login_success else 'Login may have failed'
            }
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {'status': 'error', 'message': str(e)}

    async def save_session(self, user_id: int) -> bool:
        """Save browser session cookies to database"""
        try:
            cookies = await self._context.cookies()
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("CREATE TABLE IF NOT EXISTS browser_sessions (user_id INTEGER PRIMARY KEY, cookies TEXT, saved_at TIMESTAMP)")
            conn.execute("INSERT OR REPLACE INTO browser_sessions (user_id, cookies, saved_at) VALUES (?, ?, ?)",
                        (user_id, json.dumps(cookies), datetime.utcnow().isoformat()))
            conn.commit()
            conn.close()
            self._sessions[user_id] = cookies
            return True
        except Exception as e:
            logger.error(f"Save session error: {e}")
            return False

    async def load_session(self, user_id: int) -> bool:
        """Load saved session cookies into browser"""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.execute("SELECT cookies FROM browser_sessions WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                cookies = json.loads(row[0])
                await self._context.add_cookies(cookies)
                self._sessions[user_id] = cookies
                return True
            return False
        except Exception as e:
            logger.error(f"Load session error: {e}")
            return False

    async def take_screenshot(self, user_id: int, full_page: bool = True) -> Dict:
        """Take a screenshot of current page"""
        await self._ensure()
        try:
            screenshot_dir = os.path.join(os.path.dirname(DB_PATH), 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)

            filename = f"screenshot_{user_id}_{int(time.time())}.png"
            filepath = os.path.join(screenshot_dir, filename)

            await self._page.screenshot(path=filepath, full_page=full_page)

            self._log_action(user_id, 'screenshot', self._current_url or 'unknown', {'file': filename})

            return {
                'status': 'success',
                'filepath': filepath,
                'filename': filename,
                'url': self._current_url
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def get_page_content(self, user_id: int) -> Dict:
        """Get current page content"""
        await self._ensure()
        try:
            content = await self._page.content()
            text = await self._page.evaluate('() => document.body.innerText')
            title = await self._page.title()
            url = self._page.url

            # Extract links
            links = await self._page.evaluate('''() => 
                Array.from(document.querySelectorAll('a[href]')).slice(0,20).map(a => ({
                    text: a.innerText.trim().substring(0,100),
                    href: a.href
                }))
            ''')

            # Extract forms
            forms = await self._page.evaluate('''() =>
                Array.from(document.forms).slice(0,10).map(f => ({
                    id: f.id,
                    name: f.name,
                    action: f.action,
                    fields: Array.from(f.elements).map(e => ({
                        name: e.name,
                        type: e.type,
                        id: e.id,
                        placeholder: e.placeholder
                    }))
                }))
            ''')

            self._log_action(user_id, 'get_content', url, {'content_length': len(content)})

            return {
                'status': 'success',
                'url': url,
                'title': title,
                'text': text[:5000],
                'links': links,
                'forms': forms
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def select_option(self, user_id: int, selector: str, value: str) -> Dict:
        """Select an option in a dropdown"""
        await self._ensure()
        try:
            await self._page.select_option(selector, value)
            self._log_action(user_id, 'select', selector, {'value': value})
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def scroll(self, user_id: int, direction: str = 'down', amount: int = 500) -> Dict:
        """Scroll the page"""
        await self._ensure()
        try:
            delta = amount if direction == 'down' else -amount
            await self._page.evaluate(f'window.scrollBy(0, {delta})')
            await self._page.wait_for_timeout(300)
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def go_back(self, user_id: int) -> Dict:
        """Navigate back"""
        await self._ensure()
        try:
            await self._page.go_back()
            await self._page.wait_for_load_state('domcontentloaded')
            self._current_url = self._page.url
            title = await self._page.title()
            self._log_action(user_id, 'go_back', 'back', {'url': self._current_url})
            return {'status': 'success', 'url': self._current_url, 'title': title}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def go_forward(self, user_id: int) -> Dict:
        """Navigate forward"""
        await self._ensure()
        try:
            await self._page.go_forward()
            await self._page.wait_for_load_state('domcontentloaded')
            self._current_url = self._page.url
            title = await self._page.title()
            self._log_action(user_id, 'go_forward', 'forward', {'url': self._current_url})
            return {'status': 'success', 'url': self._current_url, 'title': title}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def invoke_rpc(self, user_id: int, rpc_name: str, params: Dict = None) -> Dict:
        """Invoke a JavaScript RPC method (for APIs)"""
        await self._ensure()
        try:
            result = await self._page.evaluate(f'typeof {rpc_name} === "function"', params)
            if result:
                data = await self._page.evaluate(f'{rpc_name}({json.dumps(params or {})})')
                return {'status': 'success', 'data': data}
            return {'status': 'error', 'message': f'Function {rpc_name} not found'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def get_cookies(self, user_id: int) -> Dict:
        """Get current page cookies"""
        try:
            cookies = await self._context.cookies()
            return {'status': 'success', 'cookies': cookies}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def close(self):
        """Close browser and clean up"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        logger.info("Playwright browser closed")

    async def _get_content_snippet(self) -> str:
        """Get a short content snippet from current page"""
        try:
            text = await self._page.evaluate('() => document.body?.innerText?.substring(0, 300) || ""')
            return text.strip()
        except:
            return ""

    def _log_action(self, user_id: int, action: str, target: str, details: Dict = None):
        """Log browser action to audit database"""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS browser_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "INSERT INTO browser_actions (user_id, action, target, details) VALUES (?, ?, ?, ?)",
                (user_id, action, target, json.dumps(details or {}))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Log action error: {e}")

    def get_action_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get browser action history for user"""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM browser_actions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            )
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Get history error: {e}")
            return []

    def check_pending_approval(self, user_id: int, action_id: str) -> Optional[Dict]:
        """Check if an action has been approved by user"""
        return self._pending_actions.get((user_id, action_id))


class PermissionGate:
    """Approval workflow — user must OK each browser action"""

    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()
        self._pending = {}

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("CREATE TABLE IF NOT EXISTS browser_permissions ("
                     "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                     "user_id INTEGER NOT NULL,"
                     "action_type TEXT NOT NULL,"
                     "target TEXT,"
                     "status TEXT DEFAULT 'pending',"
                     "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
                     "responded_at TIMESTAMP)")
        conn.commit()
        conn.close()

    def request_approval(self, user_id: int, action_type: str, target: str,
                        details: Dict = None) -> Dict:
        """Request user approval for an action. Returns approval token."""
        import uuid
        token = str(uuid.uuid4())[:8]

        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute(
            "INSERT INTO browser_permissions (user_id, action_type, target) VALUES (?, ?, ?)",
            (user_id, action_type, target)
        )
        conn.commit()
        conn.close()

        self._pending[(user_id, token)] = {
            'action_type': action_type,
            'target': target,
            'details': details or {},
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat()
        }

        return {
            'token': token,
            'action_type': action_type,
            'target': target,
            'details': details or {},
            'message': f'Approval required: {action_type} {target}'
        }

    def approve(self, user_id: int, token: str) -> bool:
        """Approve a pending action"""
        key = (user_id, token)
        if key in self._pending and self._pending[key]['status'] == 'pending':
            self._pending[key]['status'] = 'approved'
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute(
                "UPDATE browser_permissions SET status='approved', responded_at=CURRENT_TIMESTAMP "
                "WHERE user_id=? AND id=(SELECT MAX(id) FROM browser_permissions WHERE user_id=? AND status='pending')",
                (user_id, user_id)
            )
            conn.commit()
            conn.close()
            return True
        return False

    def deny(self, user_id: int, token: str) -> bool:
        """Deny a pending action"""
        key = (user_id, token)
        if key in self._pending and self._pending[key]['status'] == 'pending':
            self._pending[key]['status'] = 'denied'
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute(
                "UPDATE browser_permissions SET status='denied', responded_at=CURRENT_TIMESTAMP "
                "WHERE user_id=? AND id=(SELECT MAX(id) FROM browser_permissions WHERE user_id=? AND status='pending')",
                (user_id, user_id)
            )
            conn.commit()
            conn.close()
            return True
        return False

    def wait_for_approval(self, user_id: int, token: str, timeout: int = 60) -> bool:
        """Wait for user to approve/deny (poll)"""
        start = time.time()
        while time.time() - start < timeout:
            key = (user_id, token)
            if key in self._pending:
                status = self._pending[key]['status']
                if status == 'approved':
                    return True
                elif status == 'denied':
                    return False
            time.sleep(0.5)
        return False

    def get_pending(self, user_id: int) -> List[Dict]:
        """Get all pending approvals for user"""
        return [
            {'token': k[1], **v}
            for k, v in self._pending.items()
            if k[0] == user_id and v['status'] == 'pending'
        ]


# Global instances
browser = PlaywrightManager()
permission_gate = PermissionGate()
