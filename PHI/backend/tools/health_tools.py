"""Server health tool — returns J.A.R.V.I.S. server status via HTTP health endpoint."""

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

HEALTH_URL = "http://127.0.0.1:8000/health"


def server_health() -> str:
    try:
        req = urllib.request.Request(HEALTH_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            lines = [
                f"Status: {data.get('status', 'unknown')}",
                f"Uptime: {data.get('uptime_seconds', 0):.0f}s",
                f"Active sessions: {data.get('active_sessions', 0)}",
                f"Memory: {data.get('memory_status', 'unknown')}",
            ]
            usage = data.get('token_usage', {})
            if isinstance(usage, dict):
                for k, v in usage.items():
                    lines.append(f"  {k}: {v}")
            return "\n".join(lines)
    except urllib.error.URLError as e:
        return f"Server unreachable: {e.reason}"
    except Exception as e:
        return f"Health check error: {e}"
