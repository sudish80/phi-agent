"""Webhook tools — register, trigger, list, delete webhooks."""

import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any

logger = logging.getLogger(__name__)

_webhooks: Dict[str, Dict[str, Any]] = {}


def webhook_register(name: str, url: str, secret: str = "", events: str = "") -> str:
    if not name or not url:
        return "Error: name and url are required"
    if not url.startswith("http"):
        return "Error: url must start with http:// or https://"
    _webhooks[name] = {
        "url": url,
        "secret": secret,
        "events": [e.strip() for e in events.split(",") if e.strip()],
        "created": __import__("time").time(),
    }
    return f"Webhook '{name}' registered -> {url}"


def webhook_trigger(name: str, payload_json: str = "{}") -> str:
    if name not in _webhooks:
        existing = ", ".join(_webhooks.keys()) or "none"
        return f"Error: webhook '{name}' not found. Registered: {existing}"
    try:
        data = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
        wh = _webhooks[name]
        req = urllib.request.Request(
            wh["url"],
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:500]
            return f"Triggered '{name}' -> {wh['url']} (HTTP {resp.status})\nResponse: {body}"
    except urllib.error.HTTPError as e:
        return f"HTTP error: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return f"URL error: {e.reason}"
    except Exception as e:
        return f"Webhook trigger error: {e}"


def webhook_list() -> str:
    if not _webhooks:
        return "No webhooks registered"
    lines = [f"Registered webhooks ({len(_webhooks)}):"]
    for name, wh in _webhooks.items():
        lines.append(f"  {name} -> {wh['url']} [{', '.join(wh['events']) or 'all events'}]")
    return "\n".join(lines)


def webhook_delete(name: str) -> str:
    if name not in _webhooks:
        return f"Error: webhook '{name}' not found"
    del _webhooks[name]
    return f"Webhook '{name}' deleted"
