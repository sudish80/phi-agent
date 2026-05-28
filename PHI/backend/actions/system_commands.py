"""System commands: open apps, take screenshots, file operations."""

import asyncio
import logging
import os
import subprocess
import platform
from typing import Optional
from datetime import datetime

from backend.shared.config import settings

logger = logging.getLogger(__name__)


async def open_application(app_name: str) -> bool:
    """Open a desktop application."""
    system = platform.system()
    try:
        if system == "Windows":
            app_map = {
                "browser": "start chrome",
                "chrome": "start chrome",
                "firefox": "start firefox",
                "terminal": "start cmd",
                "vs code": "code",
                "vscode": "code",
                "notepad": "notepad",
                "calculator": "calc",
                "explorer": "explorer",
                "spotify": "start spotify",
                "slack": "start slack",
                "discord": "start discord",
                "outlook": "start outlook",
            }
            cmd = app_map.get(app_name.lower(), f"start {app_name}")
            subprocess.Popen(cmd, shell=True)

        elif system == "Darwin":
            app_map = {
                "browser": "open -a Safari",
                "chrome": "open -a 'Google Chrome'",
                "firefox": "open -a Firefox",
                "terminal": "open -a Terminal",
                "vs code": "open -a 'Visual Studio Code'",
                "vscode": "open -a 'Visual Studio Code'",
                "finder": "open -a Finder",
            }
            cmd = app_map.get(app_name.lower(), f"open -a '{app_name}'")
            subprocess.Popen(cmd, shell=True)

        else:
            app_map = {
                "browser": "xdg-open https://google.com",
                "chrome": "google-chrome",
                "firefox": "firefox",
                "terminal": "gnome-terminal",
                "vs code": "code",
                "vscode": "code",
            }
            cmd = app_map.get(app_name.lower(), app_name)
            subprocess.Popen(cmd.split(), shell=False)

        logger.info(f"Opened application: {app_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to open {app_name}: {e}")
        return False


async def take_screenshot() -> Optional[str]:
    """Take a screenshot and return the file path."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(os.path.expanduser("~"), "Pictures", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        system = platform.system()
        if system == "Windows":
            import pyautogui
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
        elif system == "Darwin":
            subprocess.run(["screencapture", filepath], check=True)
        else:
            subprocess.run(["import", filepath], check=True)

        logger.info(f"Screenshot saved: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return None


async def get_system_info() -> dict:
    """Get system information."""
    import psutil
    try:
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "hostname": platform.node(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "disk_percent": psutil.disk_usage("/").percent,
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
        }
    except Exception as e:
        logger.error(f"System info error: {e}")
        return {"error": str(e)}
