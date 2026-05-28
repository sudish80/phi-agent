"""Computer Control — mouse, keyboard, windows, system, clipboard, processes.

Uses PyAutoGUI, PyGetWindow, psutil, and pyperclip for desktop automation.
"""

import asyncio
import logging
import json
import platform
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


async def mouse_move(x: int, y: int, duration: float = 0.5, absolute: bool = True) -> str:
    if not HAS_PYAUTOGUI:
        return "PyAutoGUI not installed"
    x, y = int(x), int(y)
    if absolute:
        pyautogui.moveTo(x, y, duration=duration)
    else:
        pyautogui.moveRel(x, y, duration=duration)
    return f"Moved mouse to ({x}, {y})"


async def mouse_click(button: str = "left", x: Optional[int] = None, y: Optional[int] = None,
                      clicks: int = 1) -> str:
    if not HAS_PYAUTOGUI:
        return "PyAutoGUI not installed"
    if x is not None and y is not None:
        pyautogui.click(int(x), int(y), button=button, clicks=int(clicks))
    else:
        pyautogui.click(button=button, clicks=int(clicks))
    return f"Mouse {button} clicked{' ' + str(clicks) + ' times' if clicks > 1 else ''}"


async def mouse_scroll(clicks: int, direction: str = "down") -> str:
    if not HAS_PYAUTOGUI:
        return "PyAutoGUI not installed"
    clicks = int(clicks)
    if direction == "up":
        pyautogui.scroll(clicks)
    else:
        pyautogui.scroll(-clicks)
    return f"Scrolled {direction} {clicks} clicks"


async def mouse_position() -> str:
    if not HAS_PYAUTOGUI:
        return "PyAutoGUI not installed"
    x, y = pyautogui.position()
    return json.dumps({"x": x, "y": y})


async def keyboard_type(text: str, interval: float = 0.05) -> str:
    if not HAS_PYAUTOGUI:
        return "PyAutoGUI not installed"
    pyautogui.write(text, interval=interval)
    return f"Typed {len(text)} characters"


async def keyboard_hotkey(*keys: str) -> str:
    if not HAS_PYAUTOGUI:
        return "PyAutoGUI not installed"
    pyautogui.hotkey(*keys)
    return f"Pressed hotkey: {'+'.join(keys)}"


async def keyboard_press(key: str, presses: int = 1) -> str:
    if not HAS_PYAUTOGUI:
        return "PyAutoGUI not installed"
    pyautogui.press(key, presses=int(presses))
    return f"Pressed key '{key}'{' ' + str(presses) + ' times' if presses > 1 else ''}"


async def window_list() -> str:
    if not HAS_PYGETWINDOW:
        return "PyGetWindow not installed"
    windows = gw.getWindowsWithTitle("")
    results = []
    for w in windows:
        if w.title:
            rect = w.box if hasattr(w, "box") else None
            results.append({
                "title": w.title,
                "visible": w.visible if hasattr(w, "visible") else True,
                "minimized": w.isMinimized if hasattr(w, "isMinimized") else False,
                "rect": {"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height} if rect else None,
            })
    return json.dumps(results[:50], indent=2)


async def window_activate(title: str) -> str:
    if not HAS_PYGETWINDOW:
        return "PyGetWindow not installed"
    try:
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            return f"No window found matching '{title}'"
        windows[0].activate()
        return f"Activated window: {title}"
    except Exception as e:
        return f"Failed to activate window: {e}"


async def window_move(title: str, x: int, y: int, width: Optional[int] = None, height: Optional[int] = None) -> str:
    if not HAS_PYGETWINDOW:
        return "PyGetWindow not installed"
    try:
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            return f"No window found matching '{title}'"
        w = windows[0]
        w.moveTo(int(x), int(y))
        if width is not None and height is not None:
            w.resizeTo(int(width), int(height))
        return f"Moved window '{title}' to ({x}, {y})" + (f" resized to {width}x{height}" if width and height else "")
    except Exception as e:
        return f"Failed to move window: {e}"


async def window_minimize(title: str) -> str:
    if not HAS_PYGETWINDOW:
        return "PyGetWindow not installed"
    try:
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            return f"No window found matching '{title}'"
        windows[0].minimize()
        return f"Minimized window: {title}"
    except Exception as e:
        return f"Failed: {e}"


async def window_close(title: str) -> str:
    if not HAS_PYGETWINDOW:
        return "PyGetWindow not installed"
    try:
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            return f"No window found matching '{title}'"
        windows[0].close()
        return f"Closed window: {title}"
    except Exception as e:
        return f"Failed: {e}"


async def screen_resolution() -> str:
    if not HAS_PYAUTOGUI:
        return "PyAutoGUI not installed"
    w, h = pyautogui.size()
    return json.dumps({"width": w, "height": h})


async def screenshot(region: Optional[str] = None) -> str:
    if not HAS_PYAUTOGUI:
        return "PyAutoGUI not installed"
    from backend.audio.audio_manager import AudioManager
    import base64
    import io
    audio_manager = AudioManager()
    await audio_manager.initialize()
    if region:
        parts = region.split(",")
        if len(parts) == 4:
            r = tuple(int(p.strip()) for p in parts)
            img = pyautogui.screenshot(region=r)
        else:
            img = pyautogui.screenshot()
    else:
        img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


async def clipboard_get() -> str:
    if not HAS_PYPERCLIP:
        return "pyperclip not installed"
    return pyperclip.paste()


async def clipboard_set(text: str) -> str:
    if not HAS_PYPERCLIP:
        return "pyperclip not installed"
    pyperclip.copy(text)
    return f"Clipboard set ({len(text)} chars)"


async def system_info() -> str:
    info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
    }
    if HAS_PSUTIL:
        info.update({
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_total_gb": round(psutil.disk_usage("/").total / (1024**3), 2),
            "disk_free_gb": round(psutil.disk_usage("/").free / (1024**3), 2),
            "disk_percent": psutil.disk_usage("/").percent,
        })
    return json.dumps(info, indent=2)


async def system_processes(sort_by: str = "cpu", limit: int = 20) -> str:
    if not HAS_PSUTIL:
        return "psutil not installed"
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if sort_by == "cpu":
        procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
    elif sort_by == "memory":
        procs.sort(key=lambda x: x.get("memory_percent", 0) or 0, reverse=True)
    return json.dumps(procs[: int(limit)], indent=2)


async def system_shutdown(delay_seconds: int = 0) -> str:
    delay = int(delay_seconds)
    if platform.system() == "Windows":
        import subprocess
        subprocess.run(["shutdown", "/s", "/t", str(delay)], capture_output=True)
    else:
        import subprocess
        subprocess.run(["shutdown", "-h", f"+{delay}" if delay else "now"], capture_output=True)
    return f"System shutdown scheduled in {delay}s"


async def system_lock() -> str:
    if platform.system() == "Windows":
        import subprocess
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True)
    else:
        import subprocess
        subprocess.run(["gnome-screensaver-command", "-l"], capture_output=True)
    return "System locked"


async def system_settings_control(setting: str, value: str) -> str:
    if platform.system() != "Windows":
        return "System settings control currently only supported on Windows"
    import subprocess
    setting = setting.lower()
    if setting == "volume":
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            val = max(0.0, min(1.0, float(value)))
            volume.SetMasterVolumeLevelScalar(val, None)
            return f"Volume set to {int(val * 100)}%"
        except Exception as e:
            return f"Failed to set volume: {e}"
    elif setting == "brightness":
        try:
            import screen_brightness_control as sbc
            val = max(0, min(100, int(value)))
            sbc.set_brightness(val)
            return f"Brightness set to {val}%"
        except ImportError:
            return "screen_brightness_control not installed. Run: pip install screen-brightness-control"
        except Exception as e:
            return f"Failed to set brightness: {e}"
    elif setting == "wifi":
        if value in ("on", "enable", "enabled", "1", "true"):
            subprocess.run(["netsh", "interface", "set", "interface", "Wi-Fi", "enabled"], capture_output=True)
            return "Wi-Fi enabled"
        else:
            subprocess.run(["netsh", "interface", "set", "interface", "Wi-Fi", "disabled"], capture_output=True)
            return "Wi-Fi disabled"
    elif setting == "bluetooth":
        if value in ("on", "enable", "enabled", "1", "true"):
            subprocess.run(["powershell", "-Command", "Enable-PSBluetooth"], capture_output=True)
            return "Bluetooth enabled"
        else:
            subprocess.run(["powershell", "-Command", "Disable-PSBluetooth"], capture_output=True)
            return "Bluetooth disabled"
    elif setting == "volume_mute":
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            mute = value.lower() in ("true", "1", "yes", "mute", "on")
            volume.SetMute(1 if mute else 0, None)
            return f"Volume {'muted' if mute else 'unmuted'}"
        except Exception as e:
            return f"Failed: {e}"
    return f"Unknown setting '{setting}'. Try: volume, brightness, wifi, bluetooth, volume_mute"


async def keyboard_shortcut_discover(query: str = "") -> str:
    shortcuts = {
        "copy": "Ctrl+C",
        "paste": "Ctrl+V",
        "cut": "Ctrl+X",
        "undo": "Ctrl+Z",
        "redo": "Ctrl+Y",
        "select all": "Ctrl+A",
        "save": "Ctrl+S",
        "find": "Ctrl+F",
        "switch window": "Alt+Tab",
        "close window": "Alt+F4",
        "task manager": "Ctrl+Shift+Esc",
        "lock": "Win+L",
        "screenshot": "Win+Shift+S",
        "run": "Win+R",
        "file explorer": "Win+E",
        "settings": "Win+I",
        "search": "Win+S",
        "virtual desktop": "Win+Ctrl+D",
        "switch desktop": "Win+Ctrl+Left/Right",
        "close desktop": "Win+Ctrl+F4",
        "minimize all": "Win+D",
        "snap left": "Win+Left",
        "snap right": "Win+Right",
        "magnifier": "Win+Plus",
        "narrator": "Win+Ctrl+Enter",
    }
    query = query.lower().strip()
    if query:
        results = {k: v for k, v in shortcuts.items() if query in k or query in v.lower()}
        if results:
            return json.dumps(results, indent=2)
        return f"No shortcuts found matching '{query}'"
    return json.dumps(shortcuts, indent=2)


async def multi_monitor_info() -> str:
    monitors = []
    try:
        import screeninfo
        for m in screeninfo.get_monitors():
            monitors.append({
                "name": m.name,
                "is_primary": m.is_primary,
                "width": m.width,
                "height": m.height,
                "x": m.x,
                "y": m.y,
            })
    except ImportError:
        if HAS_PYAUTOGUI:
            w, h = pyautogui.size()
            monitors.append({"name": "primary", "width": w, "height": h, "is_primary": True})
        else:
            return "screeninfo not installed. Run: pip install screeninfo"
    return json.dumps(monitors, indent=2)


async def startup_program_list() -> str:
    if platform.system() != "Windows":
        return "Startup management currently only supported on Windows"
    import subprocess
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location, User | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            return json.dumps([{"name": d.get("Name", ""), "command": d.get("Command", ""), "location": d.get("Location", ""), "user": d.get("User", "")} for d in data], indent=2)
        return "No startup programs found"
    except Exception as e:
        return f"Failed to list startup programs: {e}"


async def startup_program_add(name: str, path: str) -> str:
    import subprocess
    try:
        key = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        subprocess.run(["powershell", "-Command", f"Set-ItemProperty -Path '{key}' -Name '{name}' -Value '{path}'"], capture_output=True, timeout=10)
        return f"Added '{name}' to startup programs"
    except Exception as e:
        return f"Failed to add startup program: {e}"


async def startup_program_remove(name: str) -> str:
    import subprocess
    try:
        key = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        subprocess.run(["powershell", "-Command", f"Remove-ItemProperty -Path '{key}' -Name '{name}'"], capture_output=True, timeout=10)
        return f"Removed '{name}' from startup programs"
    except Exception as e:
        return f"Failed to remove startup program: {e}"


async def peripheral_list() -> str:
    if platform.system() != "Windows":
        return "Peripheral listing currently only supported on Windows"
    import subprocess
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-PnpDevice -PresentOnly | Where-Object {$_.Class -in 'Keyboard','Mouse','Monitor','Printer','USB','Bluetooth','Camera','AudioEndpoint'} | Select-Object FriendlyName, Class, Status, InstanceId | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            return json.dumps([{"name": d.get("FriendlyName", ""), "class": d.get("Class", ""), "status": d.get("Status", ""), "id": d.get("InstanceId", "")} for d in data], indent=2)
        return "No peripherals found"
    except Exception as e:
        return f"Failed to list peripherals: {e}"


async def accessibility_toggle(feature: str, enabled: bool = True) -> str:
    if platform.system() != "Windows":
        return "Accessibility features currently only supported on Windows"
    import subprocess
    feature = feature.lower()
    if feature == "narrator":
        key = "HKCU:\\Software\\Microsoft\\Narrator"
        val = "1" if enabled else "0"
        subprocess.run(["powershell", "-Command", f"Set-ItemProperty -Path '{key}' -Name 'NarratorActive' -Value '{val}'"], capture_output=True)
        if enabled:
            subprocess.run(["powershell", "-Command", "Start-Process 'C:\\Windows\\System32\\Narrator.exe'"], capture_output=True)
        else:
            subprocess.run(["powershell", "-Command", "Stop-Process -Name Narrator -Force"], capture_output=True)
        return f"Narrator {'enabled' if enabled else 'disabled'}"
    elif feature == "magnifier":
        if enabled:
            subprocess.run(["powershell", "-Command", "Start-Process 'Magnify.exe'"], capture_output=True)
        else:
            subprocess.run(["powershell", "-Command", "Stop-Process -Name Magnify -Force"], capture_output=True)
        return f"Magnifier {'enabled' if enabled else 'disabled'}"
    elif feature == "high_contrast" or feature == "highcontrast":
        key = "HKCU:\\Software\\Microsoft\\Accessibility\\HighContrast"
        val = "1" if enabled else "0"
        subprocess.run(["powershell", "-Command", f"Set-ItemProperty -Path '{key}' -Name 'HighContrastOn' -Value '{val}'"], capture_output=True)
        subprocess.run(["powershell", "-Command", "Stop-Process -Name dwm -Force"], capture_output=True)
        return f"High contrast {'enabled' if enabled else 'disabled'}"
    elif feature == "sticky_keys" or feature == "stickykeys":
        key = "HKCU:\\Control Panel\\Accessibility\\StickyKeys"
        val = "506" if enabled else "510"
        subprocess.run(["powershell", "-Command", f"Set-ItemProperty -Path '{key}' -Name 'Flags' -Value '{val}'"], capture_output=True)
        return f"Sticky keys {'enabled' if enabled else 'disabled'}"
    return f"Unknown feature '{feature}'. Try: narrator, magnifier, high_contrast, sticky_keys"


async def remote_desktop_start(host: str = "127.0.0.1", port: int = 5900, password: str = "") -> str:
    if platform.system() != "Windows":
        return "Remote desktop currently only supported on Windows"
    import subprocess
    try:
        if port == 3389:
            subprocess.run(["powershell", "-Command", "Start-Process 'mstsc'"], capture_output=True, timeout=5)
            return f"Windows Remote Desktop client launched (connects to {host}:{port})"
        result = subprocess.run(
            ["powershell", "-Command", f"Start-Process 'vncviewer' -ArgumentList '{host}::{port}'"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 or "vncviewer" in result.stderr.lower():
            return f"VNC viewer launched for {host}:{port}"
        return f"VNC viewer not found. Install a VNC client or use RDP with port 3389.\nCommand: vncviewer {host}::{port}"
    except Exception as e:
        return f"Failed to start remote desktop: {e}"


async def remote_desktop_list_sessions() -> str:
    if platform.system() != "Windows":
        return "Remote desktop session listing supported on Windows"
    import subprocess
    try:
        result = subprocess.run(
            ["qwinsta"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            sessions = []
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    sessions.append({"session": parts[0], "user": parts[1], "id": parts[2], "state": parts[3]})
            return json.dumps(sessions, indent=2) if sessions else "No active remote sessions"
        return "No remote desktop sessions"
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- Macro Recorder & Automation ---

_MACROS: Dict[str, list] = {}
_MACRO_RECORDING: Optional[list] = None
_MACRO_MAX = 50  # prevent unbounded memory growth

async def macro_record_start(name: str) -> str:
    global _MACRO_RECORDING
    _MACRO_RECORDING = []
    return json.dumps({"macro": name, "status": "recording",
                        "instructions": "Perform actions, then call macro_record_stop",
                        "supported_actions": "mouse_move, mouse_click, keyboard_type, keyboard_hotkey, keyboard_press, delay"})


async def macro_record_step(action: str, params: str) -> str:
    global _MACRO_RECORDING
    if _MACRO_RECORDING is None:
        return json.dumps({"error": "Not recording. Call macro_record_start first."})
    try:
        step = {"action": action, "params": json.loads(params) if isinstance(params, str) else params,
                "timestamp": __import__('time').time()}
        _MACRO_RECORDING.append(step)
        return json.dumps({"recorded": True, "step": len(_MACRO_RECORDING), "action": action}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def macro_record_stop(name: str) -> str:
    global _MACRO_RECORDING
    if _MACRO_RECORDING is None:
        return json.dumps({"error": "Not recording"})
    steps = _MACRO_RECORDING[:]
    if len(_MACROS) >= _MACRO_MAX:
        oldest = next(iter(_MACROS))
        del _MACROS[oldest]
    _MACROS[name] = steps
    _MACRO_RECORDING = None
    return json.dumps({"macro": name, "steps": len(steps), "status": "saved",
                        "can_run": f"Use macro_run('{name}') to execute"}, indent=2)


async def macro_run(name: str, interval_ms: int = 200) -> str:
    steps = _MACROS.get(name)
    if not steps:
        return json.dumps({"error": f"Macro '{name}' not found. Available: {list(_MACROS.keys())}"})
    executed = 0
    for step in steps:
        action = step["action"]
        params = step["params"]
        try:
            if action == "mouse_move":
                await mouse_move(**params)
            elif action == "mouse_click":
                await mouse_click(**params)
            elif action == "keyboard_type":
                await keyboard_type(**params)
            elif action == "keyboard_hotkey":
                await keyboard_hotkey(*params.get("keys", []))
            elif action == "keyboard_press":
                await keyboard_press(**params)
            elif action == "delay":
                await __import__('asyncio').sleep(float(params.get("seconds", 0.2)))
            executed += 1
        except Exception as e:
            logger.warning(f"Macro step {executed + 1} failed: {e}")
        await __import__('asyncio').sleep(interval_ms / 1000)
    return json.dumps({"macro": name, "steps_executed": executed, "total_steps": len(steps),
                        "status": "completed"})


async def macro_list() -> str:
    return json.dumps({"macros": {name: {"steps": len(steps),
                                           "actions": [s["action"] for s in steps[:5]],
                                           "has_more": len(steps) > 5}
                                   for name, steps in _MACROS.items()}}, indent=2)


async def macro_delete(name: str) -> str:
    if name in _MACROS:
        del _MACROS[name]
        return json.dumps({"deleted": True, "macro": name})
    return json.dumps({"error": f"Macro '{name}' not found"})


# --- Multi-Action Orchestration ---

async def orchestrate_sequence(actions_json: str) -> str:
    """Execute a sequence of computer control actions in order.
    Each action: {"action": "mouse_move|click|type|hotkey|press|scroll|delay|screenshot|window", "params": {...}}
    """
    try:
        actions = json.loads(actions_json) if isinstance(actions_json, str) else actions_json
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    results = []
    for i, action in enumerate(actions):
        act = action.get("action", "")
        params = action.get("params", {})
        try:
            if act == "mouse_move":
                r = await mouse_move(**params)
            elif act == "mouse_click":
                r = await mouse_click(**params)
            elif act == "keyboard_type":
                r = await keyboard_type(**params)
            elif act == "keyboard_hotkey":
                r = await keyboard_hotkey(*params.get("keys", []))
            elif act == "keyboard_press":
                r = await keyboard_press(**params)
            elif act == "mouse_scroll":
                r = await mouse_scroll(**params)
            elif act == "delay":
                await __import__('asyncio').sleep(float(params.get("seconds", 0.5)))
                r = f"Delayed {params.get('seconds', 0.5)}s"
            elif act == "screenshot":
                r = await screenshot(**params)
            elif act == "window_activate":
                r = await window_activate(**params)
            elif act == "window_minimize":
                r = await window_minimize(**params)
            else:
                r = f"Unknown action: {act}"
            results.append({"step": i + 1, "action": act, "result": r[:100]})
        except Exception as e:
            results.append({"step": i + 1, "action": act, "error": str(e)})
            break
    return json.dumps({"sequence": results, "steps_completed": len([r for r in results if "error" not in r]),
                        "total_steps": len(actions)}, indent=2)
