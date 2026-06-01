"""Tool wrappers for Browser Automation (Playwright) with sync wrappers for async methods"""
import asyncio
import logging
from typing import Dict, Any
from backend.shared.browser_automation import browser, permission_gate

logger = logging.getLogger(__name__)


def _run_async(coro) -> Any:
    """Run an async coroutine synchronously, handling event loop issues."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def browser_navigate(url: str, user_id: int = 0) -> dict:
    return _run_async(browser.navigate(user_id, url))

def browser_click(selector: str, user_id: int = 0) -> dict:
    return _run_async(browser.click(user_id, selector))

def browser_type(selector: str, text: str, user_id: int = 0) -> dict:
    return _run_async(browser.type_text(user_id, selector, text))

def browser_fill_form(fields_json: str, user_id: int = 0) -> dict:
    import json as _json
    try:
        fields = _json.loads(fields_json)
    except Exception as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}
    return _run_async(browser.fill_form(user_id, fields))

def browser_login(url: str, username_selector: str, password_selector: str,
                  username: str, password: str, submit_selector: str = None,
                  user_id: int = 0) -> dict:
    return _run_async(browser.login(user_id, url, username_selector, password_selector,
                                      username, password, submit_selector))

def browser_screenshot(full_page: bool = True, user_id: int = 0) -> dict:
    return _run_async(browser.take_screenshot(user_id, full_page))

def browser_get_content(user_id: int = 0) -> dict:
    return _run_async(browser.get_page_content(user_id))

def browser_select(selector: str, value: str, user_id: int = 0) -> dict:
    return _run_async(browser.select_option(user_id, selector, value))

def browser_scroll(direction: str = "down", amount: int = 500, user_id: int = 0) -> dict:
    return _run_async(browser.scroll(user_id, direction, amount))

def browser_back(user_id: int = 0) -> dict:
    return _run_async(browser.go_back(user_id))

def browser_forward(user_id: int = 0) -> dict:
    return _run_async(browser.go_forward(user_id))

def browser_get_cookies(user_id: int = 0) -> dict:
    return _run_async(browser.get_cookies(user_id))

def browser_save_session(user_id: int = 0) -> dict:
    success = _run_async(browser.save_session(user_id))
    return {"status": "success" if success else "error"}

def browser_load_session(user_id: int = 0) -> dict:
    success = _run_async(browser.load_session(user_id))
    return {"status": "success" if success else "error", "session_loaded": success}

def browser_get_history(user_id: int = 0, limit: int = 50) -> dict:
    items = browser.get_action_history(user_id, limit)
    return {"actions": items, "count": len(items)}

def browser_request_approval(action_type: str, target: str, user_id: int = 0) -> dict:
    return permission_gate.request_approval(user_id, action_type, target)

def browser_approve(token: str, user_id: int = 0) -> dict:
    success = permission_gate.approve(user_id, token)
    return {"status": "approved" if success else "error", "success": success}

def browser_deny(token: str, user_id: int = 0) -> dict:
    success = permission_gate.deny(user_id, token)
    return {"status": "denied" if success else "error", "success": success}

def browser_get_pending(user_id: int = 0) -> dict:
    items = permission_gate.get_pending(user_id)
    return {"pending": items, "count": len(items)}


def browser_download_file(url: str, filename: str = None, download_dir: str = None) -> dict:
    """Download a file directly from a URL (not through the browser page context)."""
    from backend.shared.download_engine import download_engine, DOWNLOAD_DIR
    result = download_engine.queue_download(0, url, filename, download_dir or DOWNLOAD_DIR)
    return result


def get_browser_tools():
    from backend.orchestrator.agent import Tool
    return [
        Tool(name="browser_navigate", description="Navigate browser to a URL. Initializes headless Chromium on first call.", parameters={"type": "object", "properties": {"url": {"type": "string", "description": "URL to navigate to"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["url"]}, handler=browser_navigate, category="web"),
        Tool(name="browser_click", description="Click on an element by CSS selector", parameters={"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector to click"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["selector"]}, handler=browser_click, category="web"),
        Tool(name="browser_type", description="Type text into an input field by CSS selector", parameters={"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector of the input field"}, "text": {"type": "string", "description": "Text to type"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["selector", "text"]}, handler=browser_type, category="web"),
        Tool(name="browser_fill_form", description="Fill multiple form fields at once. Pass JSON object with CSS selectors as keys and values.", parameters={"type": "object", "properties": {"fields_json": {"type": "string", "description": "JSON: {\"#username\": \"myuser\", \"#password\": \"mypass\"}"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["fields_json"]}, handler=browser_fill_form, category="web"),
        Tool(name="browser_login", description="Login to a website by filling username/password fields and submitting", parameters={"type": "object", "properties": {"url": {"type": "string", "description": "Login page URL"}, "username_selector": {"type": "string", "description": "CSS selector for username field"}, "password_selector": {"type": "string", "description": "CSS selector for password field"}, "username": {"type": "string", "description": "Username to enter"}, "password": {"type": "string", "description": "Password to enter"}, "submit_selector": {"type": "string", "description": "Optional CSS selector for submit button"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["url", "username_selector", "password_selector", "username", "password"]}, handler=browser_login, category="web"),
        Tool(name="browser_screenshot", description="Take a screenshot of the current browser page", parameters={"type": "object", "properties": {"full_page": {"type": "boolean", "description": "Capture full page (default true)"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=browser_screenshot, category="web"),
        Tool(name="browser_get_content", description="Get current page content: text, links, forms, title, URL", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=browser_get_content, category="web"),
        Tool(name="browser_select", description="Select an option in a dropdown by CSS selector and value", parameters={"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector for the select element"}, "value": {"type": "string", "description": "Option value to select"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["selector", "value"]}, handler=browser_select, category="web"),
        Tool(name="browser_scroll", description="Scroll the page up or down", parameters={"type": "object", "properties": {"direction": {"type": "string", "description": "Scroll direction: down (default) or up"}, "amount": {"type": "integer", "description": "Pixels to scroll (default 500)"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=browser_scroll, category="web"),
        Tool(name="browser_back", description="Navigate back in browser history", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=browser_back, category="web"),
        Tool(name="browser_forward", description="Navigate forward in browser history", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=browser_forward, category="web"),
        Tool(name="browser_get_cookies", description="Get current browser cookies", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=browser_get_cookies, category="web"),
        Tool(name="browser_save_session", description="Save current browser session (cookies) to database for later reuse", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=browser_save_session, category="web"),
        Tool(name="browser_load_session", description="Load a saved browser session (cookies) from database", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=browser_load_session, category="web"),
        Tool(name="browser_get_history", description="Get browser action history for the current session", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}, "limit": {"type": "integer", "description": "Max entries (default 50)"}}, "required": []}, handler=browser_get_history, category="web"),
        Tool(name="browser_request_approval", description="Request user approval for a browser action", parameters={"type": "object", "properties": {"action_type": {"type": "string", "description": "Action type (navigate, click, login, etc.)"}, "target": {"type": "string", "description": "Target URL or selector"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["action_type", "target"]}, handler=browser_request_approval, category="web"),
        Tool(name="browser_approve", description="Approve a pending browser action by token", parameters={"type": "object", "properties": {"token": {"type": "string", "description": "Approval token from browser_request_approval"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["token"]}, handler=browser_approve, category="web"),
        Tool(name="browser_deny", description="Deny a pending browser action by token", parameters={"type": "object", "properties": {"token": {"type": "string", "description": "Approval token from browser_request_approval"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["token"]}, handler=browser_deny, category="web"),
        Tool(name="browser_get_pending", description="Get all pending browser approval requests", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=browser_get_pending, category="web"),
    ]
