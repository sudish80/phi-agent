"""Memory/Wiki — persistent knowledge store for agents.

Mirrors openclaw's memory-search.ts and compaction memory sync.
"""

import json
import os
import logging
import time
import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    key: str
    content: str
    source: str = "agent"
    timestamp: float = 0.0
    tags: List[str] = field(default_factory=list)
    session_id: str = ""


class MemoryStore:
    """Simple file-based memory store. Can be backed by vector DB later."""

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir is None:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..', '..')
            store_dir = os.path.join(os.path.abspath(base), 'memory_store')
        self._store_dir = store_dir
        self._entries: Dict[str, MemoryEntry] = {}
        self._dirty = False
        os.makedirs(self._store_dir, exist_ok=True)
        self._load()

    def _store_path(self) -> str:
        return os.path.join(self._store_dir, 'memory.json')

    def _load(self) -> None:
        path = self._store_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for item in data:
                    entry = MemoryEntry(**item)
                    self._entries[entry.key] = entry
                logger.info("MemoryStore: loaded %d entries", len(self._entries))
            except Exception as e:
                logger.error("MemoryStore: failed to load: %s", e)

    def _save(self) -> None:
        if not self._dirty:
            return
        path = self._store_path()
        try:
            data = [vars(e) for e in self._entries.values()]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self._dirty = False
        except Exception as e:
            logger.error("MemoryStore: failed to save: %s", e)

    def save(self, key: str, content: str, source: str = "agent",
              tags: Optional[List[str]] = None, session_id: str = "") -> None:
        self._entries[key] = MemoryEntry(
            key=key, content=content, source=source,
            timestamp=time.time(), tags=tags or [], session_id=session_id,
        )
        self._dirty = True
        self._save()

    def get(self, key: str) -> Optional[MemoryEntry]:
        return self._entries.get(key)

    def search(self, query: str) -> List[MemoryEntry]:
        """Simple substring search. Replace with vector search later."""
        results = []
        q = query.lower()
        for entry in self._entries.values():
            if q in entry.key.lower() or q in entry.content.lower():
                results.append(entry)
        return sorted(results, key=lambda e: e.timestamp, reverse=True)[:10]

    def delete(self, key: str) -> bool:
        if key in self._entries:
            del self._entries[key]
            self._dirty = True
            self._save()
            return True
        return False

    def list_all(self) -> List[MemoryEntry]:
        return sorted(self._entries.values(), key=lambda e: e.timestamp, reverse=True)

    def sync_from_transcript(self, transcript: List[Dict[str, Any]], session_id: str) -> int:
        """Extract memories from a session transcript (post-compaction sync)."""
        count = 0
        for msg in transcript:
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > 50:
                key = f"session_{session_id}_{int(time.time())}_{count}"
                self.save(key, content[:2000], source="session", session_id=session_id)
                count += 1
        if count:
            logger.info("MemoryStore: synced %d entries from session %s", count, session_id)
        return count


# Wiki support
@dataclass
class WikiPage:
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    updated_at: float = 0.0


class WikiStore:
    """Simple file-based wiki."""

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir is None:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..', '..')
            store_dir = os.path.join(os.path.abspath(base), 'memory_store', 'wiki')
        self._store_dir = store_dir
        os.makedirs(self._store_dir, exist_ok=True)

    def _path(self, title: str) -> str:
        safe = title.replace(" ", "_").replace("/", "_")
        return os.path.join(self._store_dir, f"{safe}.md")

    def save(self, title: str, content: str, tags: Optional[List[str]] = None) -> None:
        with open(self._path(title), 'w', encoding='utf-8') as f:
            if tags:
                f.write(f"<!-- tags: {','.join(tags)} -->\n")
            f.write(content)

    def get(self, title: str) -> Optional[WikiPage]:
        path = self._path(title)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        tags = []
        if content.startswith("<!-- tags:"):
            end = content.index("-->")
            tag_str = content[10:end].strip()
            tags = [t.strip() for t in tag_str.split(",") if t.strip()]
            content = content[end + 3:].strip()
        return WikiPage(title=title, content=content, tags=tags, updated_at=os.path.getmtime(path))

    def search(self, query: str) -> List[WikiPage]:
        results = []
        q = query.lower()
        for fname in os.listdir(self._store_dir):
            if fname.endswith(".md"):
                title = fname[:-3].replace("_", " ")
                page = self.get(title)
                if page and (q in title.lower() or q in page.content.lower()):
                    results.append(page)
        return results

    def list_titles(self) -> List[str]:
        return [f[:-3].replace("_", " ")
                for f in os.listdir(self._store_dir)
                if f.endswith(".md")]


# Global singletons
memory_store = MemoryStore()
wiki_store = WikiStore()
