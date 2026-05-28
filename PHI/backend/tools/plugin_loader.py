"""Plugin Loader — Hot-load external tools from plugin directories without restart.

Each plugin is a Python file (or package) in the plugins/ directory that exports:
  - plugin_metadata: dict with name, version, author, description
  - get_tools(): returns list of (name, description, parameters, handler, category) tuples

Features:
  - Directory scanning with metadata validation
  - Hot-reload via polling file watcher
  - Error isolation (one broken plugin doesn't crash others)
  - Plugin enable/disable at runtime
  - Integration with ToolRegistry
"""

import os
import sys
import json
import time
import logging
import importlib
import inspect
import hashlib
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent / "plugins"
PLUGIN_DIR.mkdir(exist_ok=True)

# Ensure plugin dir is on path
PLUGIN_DIR_STR = str(PLUGIN_DIR)
if PLUGIN_DIR_STR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR_STR)

# Built-in plugin that's always enabled
BUILTIN_PLUGIN = {
    "name": "_builtin",
    "version": "1.0.0",
    "author": "J.A.R.V.I.S.",
    "description": "Built-in tools from autoregister.py",
    "enabled": True,
}


@dataclass
class PluginInfo:
    name: str
    version: str
    author: str
    description: str
    enabled: bool = True
    file_path: str = ""
    module_name: str = ""
    hash: str = ""
    error: str = ""
    tools_count: int = 0
    loaded_at: float = 0.0


_plugins: Dict[str, PluginInfo] = {}
_plugin_tools: Dict[str, List[Any]] = {}
_watcher_thread: Optional[threading.Thread] = None
_watcher_stop = threading.Event()
_lock = threading.Lock()


def _compute_hash(filepath: str) -> str:
    try:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def _validate_plugin(module) -> Optional[str]:
    """Validate that a module is a proper plugin. Returns error string or None."""
    if not hasattr(module, "get_tools"):
        return "Missing get_tools() function"
    if not callable(getattr(module, "get_tools")):
        return "get_tools is not callable"
    if not hasattr(module, "plugin_metadata"):
        return "Missing plugin_metadata dict"
    meta = getattr(module, "plugin_metadata")
    if not isinstance(meta, dict):
        return "plugin_metadata must be a dict"
    for key in ("name", "version", "author"):
        if key not in meta:
            return f"plugin_metadata missing '{key}'"
    return None


def load_plugin(filepath: str) -> Optional[PluginInfo]:
    """Load a single plugin file. Returns PluginInfo or None on failure."""
    filepath = str(filepath)
    if not filepath.endswith(".py"):
        return None
    if filepath.endswith("__init__.py"):
        return None

    module_name = os.path.splitext(os.path.basename(filepath))[0]
    file_hash = _compute_hash(filepath)

    try:
        # Import/reload the module
        if module_name in sys.modules:
            module = importlib.reload(sys.modules[module_name])
        else:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec for {filepath}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        # Validate
        error = _validate_plugin(module)
        if error:
            logger.warning(f"Plugin {module_name}: {error}")
            info = PluginInfo(
                name=module_name, version="0.0.0", author="unknown",
                description=error, enabled=False, error=error,
                file_path=filepath, module_name=module_name, hash=file_hash,
            )
            with _lock:
                _plugins[module_name] = info
            return info

        meta = module.plugin_metadata
        raw_tools = module.get_tools()
        tools = []

        # Convert raw tuples to Tool objects
        from backend.orchestrator.agent import Tool
        for t in raw_tools:
            if isinstance(t, Tool):
                tools.append(t)
            elif isinstance(t, (tuple, list)):
                name, desc, params, handler = t[:4]
                category = t[4] if len(t) > 4 else "plugin"
                tools.append(Tool(
                    name=name, description=desc, parameters=params,
                    handler=handler, category=category,
                ))

        info = PluginInfo(
            name=meta.get("name", module_name),
            version=meta.get("version", "0.0.0"),
            author=meta.get("author", "unknown"),
            description=meta.get("description", ""),
            enabled=True,
            file_path=filepath,
            module_name=module_name,
            hash=file_hash,
            tools_count=len(tools),
            loaded_at=time.time(),
        )

        with _lock:
            _plugins[module_name] = info
            _plugin_tools[module_name] = tools

        logger.info(f"Loaded plugin '{info.name}' v{info.version} — {len(tools)} tools")
        return info

    except Exception as e:
        logger.error(f"Failed to load plugin {module_name}: {e}")
        info = PluginInfo(
            name=module_name, version="0.0.0", author="unknown",
            description=str(e), enabled=False, error=str(e),
            file_path=filepath, module_name=module_name, hash=file_hash,
        )
        with _lock:
            _plugins[module_name] = info
        return info


def scan_plugins(directory: Optional[str] = None) -> Dict[str, PluginInfo]:
    """Scan a directory for plugin files and load them. Returns dict of PluginInfo."""
    directory = directory or str(PLUGIN_DIR)
    results = {}

    for fname in sorted(os.listdir(directory)):
        fpath = os.path.join(directory, fname)
        if fname.endswith(".py"):
            info = load_plugin(fpath)
            if info:
                results[info.name] = info

    return results


def get_plugin_tools(include_disabled: bool = False) -> List[Any]:
    """Get all tools from all enabled plugins."""
    tools = []
    with _lock:
        for name, info in _plugins.items():
            if info.enabled or include_disabled:
                tools.extend(_plugin_tools.get(name, []))
    return tools


def get_plugin(name: str) -> Optional[PluginInfo]:
    """Get info for a specific plugin."""
    with _lock:
        return _plugins.get(name)


def list_plugins() -> List[PluginInfo]:
    """List all registered plugins."""
    with _lock:
        return list(_plugins.values())


def enable_plugin(name: str) -> bool:
    """Enable a plugin by name."""
    with _lock:
        if name in _plugins:
            _plugins[name].enabled = True
            return True
    return False


def disable_plugin(name: str) -> bool:
    """Disable a plugin by name."""
    with _lock:
        if name in _plugins:
            _plugins[name].enabled = False
            # Remove its tools from active registry
            _plugin_tools.pop(name, None)
            return True
    return False


def reload_plugin(name: str) -> Optional[PluginInfo]:
    """Reload a single plugin by name."""
    with _lock:
        info = _plugins.get(name)
        if not info:
            return None
        filepath = info.file_path
    if filepath and os.path.exists(filepath):
        return load_plugin(filepath)
    return None


def _watcher_loop(interval: float = 5.0):
    """Background thread that watches plugin files for changes and hot-reloads."""
    file_hashes: Dict[str, str] = {}

    while not _watcher_stop.is_set():
        try:
            # Collect current hashes
            current = {}
            for fname in os.listdir(str(PLUGIN_DIR)):
                fpath = os.path.join(str(PLUGIN_DIR), fname)
                if fname.endswith(".py") and not fname.endswith("__init__.py"):
                    current[fpath] = _compute_hash(fpath)

            # Detect new/changed files
            for fpath, fhash in current.items():
                old_hash = file_hashes.get(fpath)
                if old_hash is None:
                    logger.info(f"New plugin detected: {fpath}")
                    load_plugin(fpath)
                elif old_hash != fhash:
                    logger.info(f"Plugin changed: {fpath}")
                    load_plugin(fpath)

            # Detect removed files
            for fpath in list(file_hashes.keys()):
                if fpath not in current:
                    module_name = os.path.splitext(os.path.basename(fpath))[0]
                    with _lock:
                        _plugins.pop(module_name, None)
                        _plugin_tools.pop(module_name, None)
                    logger.info(f"Plugin removed: {module_name}")

            file_hashes.update(current)

        except Exception as e:
            logger.error(f"Plugin watcher error: {e}")

        _watcher_stop.wait(interval)


def start_watcher(interval: float = 5.0):
    """Start the background plugin file watcher."""
    global _watcher_thread
    if _watcher_thread and _watcher_thread.is_alive():
        logger.warning("Plugin watcher already running")
        return
    _watcher_stop.clear()
    _watcher_thread = threading.Thread(
        target=_watcher_loop, args=(interval,), daemon=True,
        name="plugin-watcher"
    )
    _watcher_thread.start()
    logger.info(f"Plugin watcher started (poll every {interval}s)")


def stop_watcher():
    """Stop the background plugin file watcher."""
    _watcher_stop.set()
    global _watcher_thread
    if _watcher_thread:
        _watcher_thread.join(timeout=5)
        _watcher_thread = None


def register_plugin_tools(registry):
    """Register all enabled plugin tools into a ToolRegistry."""
    for info in list_plugins():
        if not info.enabled:
            continue
        tools = _plugin_tools.get(info.module_name, [])
        for tool in tools:
            registry.register(tool)
        logger.info(f"Registered {len(tools)} tools from plugin '{info.name}'")


def create_example_plugin(filepath: Optional[str] = None) -> str:
    """Create a sample plugin file to demonstrate the plugin API."""
    if filepath is None:
        filepath = str(PLUGIN_DIR / "example_plugin.py")

    content = '''"""Example J.A.R.V.I.S. Plugin — Demonstrates the plugin API."""

import json
import random
from datetime import datetime

plugin_metadata = {
    "name": "Example Plugin",
    "version": "1.0.0",
    "author": "Plugin Developer",
    "description": "Demonstrates how to create plugins for J.A.R.V.I.S.",
}


async def reverse_text(text: str) -> str:
    """Reverse any text string."""
    return json.dumps({"original": text, "reversed": text[::-1]})


async def random_number(min_val: int = 1, max_val: int = 100) -> str:
    """Generate a random number between min and max."""
    num = random.randint(min_val, max_val)
    return json.dumps({"number": num, "range": f"{min_val}-{max_val}"})


async def current_timestamp() -> str:
    """Get the current timestamp in multiple formats."""
    now = datetime.now()
    return json.dumps({
        "iso": now.isoformat(),
        "unix": now.timestamp(),
        "readable": now.strftime("%A, %B %d, %Y at %I:%M %p"),
    })


async def text_stats(text: str) -> str:
    """Get statistics about a text (word count, char count, sentence count)."""
    words = text.split()
    sentences = [s for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    return json.dumps({
        "word_count": len(words),
        "char_count": len(text),
        "sentence_count": len(sentences),
        "avg_word_length": round(sum(len(w) for w in words) / max(len(words), 1), 2),
    })


def get_tools():
    """Return list of (name, description, parameters, handler, category) tuples."""
    return [
        ("plugin_reverse_text", "Reverse any text string", {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to reverse"}},
            "required": ["text"],
        }, reverse_text, "utility"),
        ("plugin_random_number", "Generate a random number between min and max", {
            "type": "object",
            "properties": {
                "min_val": {"type": "integer", "description": "Minimum value (default 1)"},
                "max_val": {"type": "integer", "description": "Maximum value (default 100)"},
            },
            "required": [],
        }, random_number, "fun"),
        ("plugin_current_timestamp", "Get the current timestamp in multiple formats", {
            "type": "object", "properties": {}, "required": [],
        }, current_timestamp, "utility"),
        ("plugin_text_stats", "Get word/character/sentence statistics for a text", {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to analyze"}},
            "required": ["text"],
        }, text_stats, "utility"),
    ]
'''
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath
