"""System tools — system info, disk usage, browser control."""

import os
import platform
import webbrowser
import logging

logger = logging.getLogger(__name__)


def open_url(url: str) -> str:
    """Open a website or URL in the user's default web browser."""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opened {url} in your default browser."
    except Exception as e:
        return f"Failed to open browser: {e}"


def system_info() -> str:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        return "\n".join([
            f"OS: {platform.system()} {platform.release()}",
            f"Hostname: {platform.node()}",
            f"Python: {platform.python_version()}",
            f"CPU: {psutil.cpu_count()} cores ({cpu}% used)",
            f"RAM: {mem.used/1024**3:.1f}GB / {mem.total/1024**3:.1f}GB ({mem.percent}%)",
            f"Processes: {len(psutil.pids())}",
        ])
    except ImportError:
        return "\n".join([
            f"OS: {platform.system()} {platform.release()}",
            f"Hostname: {platform.node()}",
            f"Python: {platform.python_version()}",
            f"Arch: {platform.machine()}",
        ])
    except Exception as e:
        return f"System info error: {e}"


def disk_usage(path: str = ".") -> str:
    try:
        if not os.path.exists(path):
            return f"Error: path not found: {path}"
        stat = os.statvfs(path) if hasattr(os, "statvfs") else None
        if stat:
            total = stat.f_frsize * stat.f_blocks
            free = stat.f_frsize * stat.f_bfree
            used = total - free
            pct = used / total * 100
        else:
            import shutil
            usage = shutil.disk_usage(path)
            total, used, free = usage.total, usage.used, usage.free
            pct = used / total * 100
        return "\n".join([
            f"Path: {os.path.abspath(path)}",
            f"Total: {total/1024**3:.1f} GB",
            f"Used: {used/1024**3:.1f} GB ({pct:.1f}%)",
            f"Free: {free/1024**3:.1f} GB",
        ])
    except Exception as e:
        return f"Disk usage error: {e}"
