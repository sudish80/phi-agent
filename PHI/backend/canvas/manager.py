"""Thread & Canvas managers — orchestration layer with event hooks."""

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set

from backend.canvas.models import (
    BlockType,
    Canvas,
    CanvasBlock,
    CanvasType,
    Thread,
    ThreadMessage,
    ThreadStatus,
)
from backend.canvas.thread_store import thread_store as _thread_store
from backend.canvas.canvas_store import canvas_store as _canvas_store

logger = logging.getLogger(__name__)

EventHook = Callable[[str, Dict[str, Any]], None]


class ThreadManager:
    """Manages thread lifecycle — creation, forking, merging, archiving."""

    def __init__(self, store=None):
        self._store = store or _thread_store
        self._hooks: Dict[str, List[EventHook]] = {
            "on_new_message": [],
            "on_thread_created": [],
            "on_thread_archived": [],
            "on_thread_forked": [],
        }
        self._ttl: float = 86400 * 7  # 7 days default
        self._archive_task: Optional[asyncio.Task] = None

    def on(self, event: str, hook: EventHook) -> None:
        if event in self._hooks:
            self._hooks[event].append(hook)

    def _emit(self, event: str, thread_id: str, data: Dict[str, Any]) -> None:
        for hook in self._hooks.get(event, []):
            try:
                hook(thread_id, data)
            except Exception as e:
                logger.warning("Hook %s failed for %s: %s", event, thread_id, e)

    async def create_thread(
        self,
        title: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_thread_id: Optional[str] = None,
    ) -> Thread:
        now = time.time()
        thread = Thread(
            id=str(uuid.uuid4()),
            title=title,
            created_at=now,
            updated_at=now,
            status=ThreadStatus.active,
            tags=tags or [],
            metadata=metadata or {},
            parent_thread_id=parent_thread_id,
        )
        await self._store.create_thread(thread)
        self._emit("on_thread_created", thread.id, {"title": title, "tags": tags})
        logger.info("Thread created: %s (%s)", thread.id, title)
        return thread

    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        return await self._store.get_thread(thread_id)

    async def list_threads(
        self,
        status: Optional[ThreadStatus] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Thread]:
        return await self._store.list_threads(
            status=status, tags=tags, limit=limit, offset=offset
        )

    async def update_thread(self, thread: Thread) -> Optional[Thread]:
        thread.updated_at = time.time()
        return await self._store.update_thread(thread)

    async def archive_thread(self, thread_id: str) -> bool:
        result = await self._store.archive_thread(thread_id)
        if result:
            self._emit("on_thread_archived", thread_id, {})
        return result

    async def delete_thread(self, thread_id: str) -> bool:
        return await self._store.delete_thread(thread_id)

    async def fork_thread(
        self, thread_id: str, new_title: str
    ) -> Optional[Thread]:
        parent = await self._store.get_thread(thread_id)
        if not parent:
            return None
        now = time.time()
        child = Thread(
            id=str(uuid.uuid4()),
            title=new_title,
            created_at=now,
            updated_at=now,
            status=ThreadStatus.active,
            tags=parent.tags.copy(),
            metadata={**parent.metadata, "forked_from": thread_id},
            parent_thread_id=thread_id,
        )
        await self._store.create_thread(child)
        self._emit("on_thread_forked", child.id, {"parent_id": thread_id})
        return child

    async def merge_threads(
        self, source_id: str, target_id: str
    ) -> Optional[Thread]:
        target = await self._store.get_thread(target_id)
        if not target:
            return None
        messages = await self._store.get_messages(source_id, limit=10000)
        for msg in messages:
            msg.thread_id = target_id
            await self._store.add_message(msg)
        await self._store.archive_thread(source_id)
        return await self._store.get_thread(target_id)

    # ── Messages ──────────────────────────────────────────────

    async def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        parent_id: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[ThreadMessage]:
        thread = await self._store.get_thread(thread_id)
        if not thread:
            return None
        msg = ThreadMessage(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            role=role,
            content=content,
            timestamp=time.time(),
            parent_id=parent_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            attachments=attachments,
        )
        await self._store.add_message(msg)
        self._emit("on_new_message", thread_id, {"role": role, "msg_id": msg.id})
        return msg

    async def get_messages(
        self,
        thread_id: str,
        limit: int = 100,
        offset: int = 0,
        before: Optional[float] = None,
    ) -> List[ThreadMessage]:
        return await self._store.get_messages(
            thread_id, limit=limit, offset=offset, before=before
        )

    async def delete_message(self, msg_id: str) -> bool:
        return await self._store.delete_message(msg_id)

    async def search_messages(self, text: str, limit: int = 50):
        return await self._store.search_messages(text, limit=limit)

    async def get_thread_summary(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return await self._store.get_thread_summary(thread_id)

    # ── Auto-archive ──────────────────────────────────────────

    def set_ttl(self, seconds: float) -> None:
        self._ttl = seconds

    async def start_auto_archive(self, interval: float = 3600) -> None:
        async def _loop():
            while True:
                try:
                    await self._auto_archive_pass()
                except Exception as e:
                    logger.warning("Auto-archive pass failed: %s", e)
                await asyncio.sleep(interval)
        self._archive_task = asyncio.create_task(_loop())
        logger.info("Auto-archive started (TTL=%ds, interval=%ds)", self._ttl, interval)

    async def stop_auto_archive(self) -> None:
        if self._archive_task:
            self._archive_task.cancel()
            self._archive_task = None

    async def _auto_archive_pass(self) -> None:
        cutoff = time.time() - self._ttl
        threads = await self._store.list_threads(status=ThreadStatus.active, limit=500)
        for t in threads:
            if t.updated_at < cutoff:
                await self.archive_thread(t.id)
                logger.info("Auto-archived thread %s (inactive since %s)", t.id, t.updated_at)


class CanvasManager:
    """Manages canvas lifecycle — creation, versioning, templates."""

    TEMPLATES = {
        "code": {"type": CanvasType.code, "content": "# Write your code here"},
        "doc": {"type": CanvasType.text, "content": "# Document\n\nStart writing..."},
        "mermaid": {
            "type": CanvasType.mermaid,
            "content": "graph TD\n    A[Start] --> B[End]",
        },
        "drawing": {"type": CanvasType.drawing, "content": "{}"},
    }

    def __init__(self, store=None):
        self._store = store or _canvas_store
        self._hooks: Dict[str, List[EventHook]] = {
            "on_canvas_update": [],
            "on_canvas_created": [],
            "on_block_locked": [],
            "on_block_unlocked": [],
        }

    def on(self, event: str, hook: EventHook) -> None:
        if event in self._hooks:
            self._hooks[event].append(hook)

    def _emit(self, event: str, canvas_id: str, data: Dict[str, Any]) -> None:
        for hook in self._hooks.get(event, []):
            try:
                hook(canvas_id, data)
            except Exception as e:
                logger.warning("Hook %s failed for %s: %s", event, canvas_id, e)

    async def create_canvas(
        self,
        thread_id: str,
        template: Optional[str] = None,
        canvas_type: Optional[CanvasType] = None,
        position: Optional[Dict[str, float]] = None,
        size: Optional[Dict[str, float]] = None,
    ) -> Canvas:
        now = time.time()
        if template and template in self.TEMPLATES:
            tpl = self.TEMPLATES[template]
            resolved_type = canvas_type or tpl["type"]
            content = tpl["content"]
        else:
            resolved_type = canvas_type or CanvasType.text
            content = ""

        canvas = Canvas(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            type=resolved_type,
            content=content,
            position=position or {"x": 0, "y": 0},
            size=size or {"width": 800, "height": 600},
            z_index=0,
            created_at=now,
            updated_at=now,
            version=1,
        )
        await self._store.create_canvas(canvas)
        await self._store.save_version(canvas.id)
        self._emit("on_canvas_created", canvas.id, {"thread_id": thread_id, "type": resolved_type.value})
        return canvas

    async def get_canvas(self, canvas_id: str) -> Optional[Canvas]:
        return await self._store.get_canvas(canvas_id)

    async def list_canvases(
        self, thread_id: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> List[Canvas]:
        return await self._store.list_canvases(
            thread_id=thread_id, limit=limit, offset=offset
        )

    async def update_canvas(self, canvas: Canvas) -> Optional[Canvas]:
        result = await self._store.update_canvas(canvas)
        if result:
            await self._store.save_version(canvas.id)
            self._emit("on_canvas_update", canvas.id, {"version": canvas.version})
        return result

    async def delete_canvas(self, canvas_id: str) -> bool:
        return await self._store.delete_canvas(canvas_id)

    # ── Blocks ────────────────────────────────────────────────

    async def create_block(
        self,
        canvas_id: str,
        block_type: BlockType = BlockType.text,
        content: str = "",
        language: Optional[str] = None,
        position: Optional[Dict[str, float]] = None,
        size: Optional[Dict[str, float]] = None,
    ) -> Optional[CanvasBlock]:
        canvas = await self._store.get_canvas(canvas_id)
        if not canvas:
            return None
        block = CanvasBlock(
            id=str(uuid.uuid4()),
            canvas_id=canvas_id,
            type=block_type,
            content=content,
            language=language,
            position=position or {"x": 0, "y": 0},
            size=size or {"width": 400, "height": 300},
            locked_by=None,
            collaborators=[],
            metadata={},
        )
        await self._store.create_block(block)
        return block

    async def list_blocks(self, canvas_id: str) -> List[CanvasBlock]:
        return await self._store.list_blocks(canvas_id)

    async def update_block(self, block: CanvasBlock) -> Optional[CanvasBlock]:
        return await self._store.update_block(block)

    async def delete_block(self, block_id: str) -> bool:
        return await self._store.delete_block(block_id)

    async def update_block_content(self, block_id: str, content: str) -> Optional[CanvasBlock]:
        result = await self._store.update_block_content(block_id, content)
        if result:
            block = await self._store.get_block(block_id)
            if block:
                self._emit("on_canvas_update", block.canvas_id, {"block_id": block_id})
        return result

    async def lock_block(self, block_id: str, user: str) -> bool:
        result = await self._store.lock_block(block_id, user)
        if result:
            block = await self._store.get_block(block_id)
            if block:
                self._emit("on_block_locked", block.canvas_id, {"block_id": block_id, "user": user})
        return result

    async def unlock_block(self, block_id: str, user: Optional[str] = None) -> bool:
        block = await self._store.get_block(block_id)
        result = await self._store.unlock_block(block_id, user)
        if result and block:
            self._emit("on_block_unlocked", block.canvas_id, {"block_id": block_id, "user": user})
        return result

    # ── Versioning ────────────────────────────────────────────

    async def save_version(self, canvas_id: str) -> int:
        return await self._store.save_version(canvas_id)

    async def get_versions(self, canvas_id: str) -> List[Dict[str, Any]]:
        return await self._store.get_versions(canvas_id)

    async def restore_version(self, canvas_id: str, version: int) -> Optional[Canvas]:
        canvas = await self._store.restore_version(canvas_id, version)
        if canvas:
            self._emit("on_canvas_update", canvas_id, {"restored_version": version})
        return canvas

    async def diff_versions(
        self, canvas_id: str, v1: int, v2: int
    ) -> Optional[Dict[str, Any]]:
        return await self._store.diff_versions(canvas_id, v1, v2)


thread_manager = ThreadManager()
canvas_manager = CanvasManager()
