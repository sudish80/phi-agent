"""FastAPI routes for the Canvas/Thread system."""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from backend.canvas.manager import thread_manager, canvas_manager
from backend.canvas.models import (
    BlockType, CanvasType, ThreadStatus,
    Thread, ThreadMessage, Canvas, CanvasBlock,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ── WebSocket room state ─────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, thread_id: str, client_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms.setdefault(thread_id, {})[client_id] = ws
        canvases = await canvas_manager.list_canvases(thread_id=thread_id)
        canvas_data = []
        for c in canvases:
            blocks = await canvas_manager.list_blocks(c.id)
            canvas_data.append({
                "canvas": {
                    "id": c.id,
                    "type": c.type.value,
                    "content": c.content,
                    "position": c.position,
                    "size": c.size,
                    "z_index": c.z_index,
                    "version": c.version,
                },
                "blocks": [
                    {
                        "id": b.id,
                        "type": b.type.value,
                        "content": b.content,
                        "language": b.language,
                        "locked_by": b.locked_by,
                        "position": b.position,
                        "size": b.size,
                    }
                    for b in blocks
                ],
            })
        await ws.send_json({"type": "state", "canvases": canvas_data})

    def disconnect(self, thread_id: str, client_id: str) -> None:
        room = self._rooms.get(thread_id, {})
        room.pop(client_id, None)
        if not room:
            self._rooms.pop(thread_id, None)

    async def broadcast(self, thread_id: str, data: dict, exclude: Optional[str] = None) -> None:
        room = self._rooms.get(thread_id, {})
        for cid, ws in room.items():
            if cid != exclude:
                try:
                    await ws.send_json(data)
                except Exception:
                    pass

    def get_room_clients(self, thread_id: str) -> List[str]:
        return list(self._rooms.get(thread_id, {}).keys())

    async def unlock_all_blocks(self, thread_id: str, client_id: str) -> None:
        canvases = await canvas_manager.list_canvases(thread_id=thread_id)
        for c in canvases:
            blocks = await canvas_manager.list_blocks(c.id)
            for b in blocks:
                if b.locked_by == client_id:
                    await canvas_manager.unlock_block(b.id, client_id)


ws_manager = ConnectionManager()


# ================================================================
# Thread Routes
# ================================================================

@router.post("/api/threads")
async def create_thread(
    title: str,
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    parent_thread_id: Optional[str] = None,
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    thread = await thread_manager.create_thread(
        title=title,
        tags=tag_list,
        parent_thread_id=parent_thread_id,
    )
    return {"thread": _thread_to_dict(thread)}


@router.get("/api/threads")
async def list_threads(
    status: Optional[str] = None,
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    limit: int = 50,
    offset: int = 0,
):
    status_enum = ThreadStatus(status) if status else None
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    threads = await thread_manager.list_threads(
        status=status_enum, tags=tag_list, limit=limit, offset=offset
    )
    return {"threads": [_thread_to_dict(t) for t in threads], "total": len(threads)}


@router.get("/api/threads/search")
async def search_threads(q: str = Query(..., min_length=1), limit: int = 50):
    results = await thread_manager.search_messages(q, limit=limit)
    return {
        "results": [
            {"msg_id": r[0], "thread_id": r[1], "content": r[2], "timestamp": r[3]}
            for r in results
        ],
        "total": len(results),
    }


@router.get("/api/threads/{thread_id}")
async def get_thread(thread_id: str):
    thread = await thread_manager.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    summary = await thread_manager.get_thread_summary(thread_id)
    return {"thread": _thread_to_dict(thread), "summary": summary}


@router.put("/api/threads/{thread_id}")
async def update_thread(thread_id: str, title: Optional[str] = None,
                         tags: Optional[str] = None, status: Optional[str] = None):
    thread = await thread_manager.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if title is not None:
        thread.title = title
    if tags is not None:
        thread.tags = [t.strip() for t in tags.split(",") if t.strip()]
    if status is not None:
        thread.status = ThreadStatus(status)
    updated = await thread_manager.update_thread(thread)
    return {"thread": _thread_to_dict(updated)}


@router.delete("/api/threads/{thread_id}")
async def delete_thread(thread_id: str):
    ok = await thread_manager.delete_thread(thread_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"status": "deleted", "thread_id": thread_id}


@router.post("/api/threads/{thread_id}/archive")
async def archive_thread(thread_id: str):
    ok = await thread_manager.archive_thread(thread_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found or already archived")
    return {"status": "archived", "thread_id": thread_id}


@router.post("/api/threads/{thread_id}/fork")
async def fork_thread(thread_id: str, title: str):
    child = await thread_manager.fork_thread(thread_id, title)
    if not child:
        raise HTTPException(status_code=404, detail="Source thread not found")
    return {"thread": _thread_to_dict(child)}


@router.post("/api/threads/{source_id}/merge")
async def merge_threads(source_id: str, target_id: str):
    target = await thread_manager.merge_threads(source_id, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target thread not found")
    return {"thread": _thread_to_dict(target)}


# ================================================================
# Message Routes
# ================================================================

@router.get("/api/threads/{thread_id}/messages")
async def get_messages(
    thread_id: str,
    limit: int = 100,
    offset: int = 0,
    before: Optional[float] = None,
):
    thread = await thread_manager.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    messages = await thread_manager.get_messages(
        thread_id, limit=limit, offset=offset, before=before
    )
    return {"messages": [_msg_to_dict(m) for m in messages], "total": len(messages)}


@router.post("/api/threads/{thread_id}/messages")
async def add_message(
    thread_id: str,
    role: str,
    content: str,
    parent_id: Optional[str] = None,
):
    msg = await thread_manager.add_message(
        thread_id=thread_id,
        role=role,
        content=content,
        parent_id=parent_id,
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Thread not found")
    await ws_manager.broadcast(thread_id, {
        "type": "new_message",
        "message": _msg_to_dict(msg),
    })
    return {"message": _msg_to_dict(msg)}


@router.delete("/api/threads/{thread_id}/messages/{msg_id}")
async def delete_message(thread_id: str, msg_id: str):
    ok = await thread_manager.delete_message(msg_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found")
    await ws_manager.broadcast(thread_id, {
        "type": "message_deleted",
        "msg_id": msg_id,
    })
    return {"status": "deleted", "msg_id": msg_id}


# ================================================================
# Canvas Routes
# ================================================================

@router.post("/api/canvases")
async def create_canvas(
    thread_id: str,
    template: Optional[str] = None,
    canvas_type: Optional[str] = None,
    position: Optional[Dict[str, float]] = None,
    size: Optional[Dict[str, float]] = None,
):
    type_enum = CanvasType(canvas_type) if canvas_type else None
    canvas = await canvas_manager.create_canvas(
        thread_id=thread_id,
        template=template,
        canvas_type=type_enum,
        position=position,
        size=size,
    )
    return {"canvas": _canvas_to_dict(canvas)}


@router.get("/api/canvases")
async def list_canvases(
    thread_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    canvases = await canvas_manager.list_canvases(
        thread_id=thread_id, limit=limit, offset=offset
    )
    return {"canvases": [_canvas_to_dict(c) for c in canvases], "total": len(canvases)}


@router.get("/api/canvases/{canvas_id}")
async def get_canvas(canvas_id: str):
    canvas = await canvas_manager.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    blocks = await canvas_manager.list_blocks(canvas_id)
    return {
        "canvas": _canvas_to_dict(canvas),
        "blocks": [_block_to_dict(b) for b in blocks],
    }


@router.put("/api/canvases/{canvas_id}")
async def update_canvas(canvas_id: str, content: Optional[str] = None,
                         position: Optional[Dict[str, float]] = None,
                         size: Optional[Dict[str, float]] = None,
                         z_index: Optional[int] = None):
    canvas = await canvas_manager.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    if content is not None:
        canvas.content = content
    if position is not None:
        canvas.position = position
    if size is not None:
        canvas.size = size
    if z_index is not None:
        canvas.z_index = z_index
    updated = await canvas_manager.update_canvas(canvas)
    await ws_manager.broadcast(canvas.thread_id, {
        "type": "canvas_updated",
        "canvas": _canvas_to_dict(updated),
    })
    return {"canvas": _canvas_to_dict(updated)}


@router.delete("/api/canvases/{canvas_id}")
async def delete_canvas(canvas_id: str):
    canvas = await canvas_manager.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    await canvas_manager.delete_canvas(canvas_id)
    await ws_manager.broadcast(canvas.thread_id, {
        "type": "canvas_deleted",
        "canvas_id": canvas_id,
    })
    return {"status": "deleted", "canvas_id": canvas_id}


# ================================================================
# Canvas Block Routes
# ================================================================

@router.get("/api/canvases/{canvas_id}/blocks")
async def list_blocks(canvas_id: str):
    canvas = await canvas_manager.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    blocks = await canvas_manager.list_blocks(canvas_id)
    return {"blocks": [_block_to_dict(b) for b in blocks], "total": len(blocks)}


@router.post("/api/canvases/{canvas_id}/blocks")
async def create_block(
    canvas_id: str,
    block_type: str = "text",
    content: str = "",
    language: Optional[str] = None,
    position: Optional[Dict[str, float]] = None,
    size: Optional[Dict[str, float]] = None,
):
    canvas = await canvas_manager.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    block = await canvas_manager.create_block(
        canvas_id=canvas_id,
        block_type=BlockType(block_type),
        content=content,
        language=language,
        position=position,
        size=size,
    )
    await ws_manager.broadcast(canvas.thread_id, {
        "type": "block_created",
        "canvas_id": canvas_id,
        "block": _block_to_dict(block),
    })
    return {"block": _block_to_dict(block)}


@router.put("/api/canvases/{canvas_id}/blocks/{block_id}")
async def update_block(
    canvas_id: str,
    block_id: str,
    content: Optional[str] = None,
    language: Optional[str] = None,
    position: Optional[Dict[str, float]] = None,
    size: Optional[Dict[str, float]] = None,
):
    canvas = await canvas_manager.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    block = await canvas_manager.list_blocks(canvas_id)
    block = next((b for b in block if b.id == block_id), None)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    if content is not None:
        block.content = content
    if language is not None:
        block.language = language
    if position is not None:
        block.position = position
    if size is not None:
        block.size = size
    updated = await canvas_manager.update_block(block)
    await ws_manager.broadcast(canvas.thread_id, {
        "type": "block_updated",
        "canvas_id": canvas_id,
        "block": _block_to_dict(updated),
    })
    return {"block": _block_to_dict(updated)}


@router.delete("/api/canvases/{canvas_id}/blocks/{block_id}")
async def delete_block(canvas_id: str, block_id: str):
    canvas = await canvas_manager.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    ok = await canvas_manager.delete_block(block_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Block not found")
    await ws_manager.broadcast(canvas.thread_id, {
        "type": "block_deleted",
        "canvas_id": canvas_id,
        "block_id": block_id,
    })
    return {"status": "deleted", "block_id": block_id}


# ================================================================
# Block Lock Routes
# ================================================================

@router.post("/api/canvases/{canvas_id}/blocks/{block_id}/lock")
async def lock_block(canvas_id: str, block_id: str, user: str):
    ok = await canvas_manager.lock_block(block_id, user)
    if not ok:
        raise HTTPException(status_code=409, detail="Block already locked")
    await ws_manager.broadcast(
        (await canvas_manager.get_canvas(canvas_id)).thread_id,
        {"type": "block_locked", "canvas_id": canvas_id, "block_id": block_id, "user": user},
    )
    return {"status": "locked", "block_id": block_id, "user": user}


@router.post("/api/canvases/{canvas_id}/blocks/{block_id}/unlock")
async def unlock_block(canvas_id: str, block_id: str, user: Optional[str] = None):
    ok = await canvas_manager.unlock_block(block_id, user)
    if not ok:
        raise HTTPException(status_code=404, detail="Block not found or not locked by this user")
    return {"status": "unlocked", "block_id": block_id}


# ================================================================
# Canvas Version Routes
# ================================================================

@router.get("/api/canvases/{canvas_id}/versions")
async def get_versions(canvas_id: str):
    canvas = await canvas_manager.get_canvas(canvas_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    versions = await canvas_manager.get_versions(canvas_id)
    return {"versions": versions, "total": len(versions)}


@router.post("/api/canvases/{canvas_id}/restore/{version}")
async def restore_version(canvas_id: str, version: int):
    canvas = await canvas_manager.restore_version(canvas_id, version)
    if not canvas:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"canvas": _canvas_to_dict(canvas), "restored_version": version}


@router.get("/api/canvases/{canvas_id}/diff")
async def diff_versions(canvas_id: str, v1: int, v2: int):
    result = await canvas_manager.diff_versions(canvas_id, v1, v2)
    if not result:
        raise HTTPException(status_code=404, detail="Versions not found")
    return result


# ================================================================
# WebSocket Endpoint
# ================================================================

@router.websocket("/ws/thread/{thread_id}")
async def thread_websocket(ws: WebSocket, thread_id: str, client_id: Optional[str] = None):
    if not client_id:
        client_id = f"anon-{int(time.time() * 1000)}"
    await ws_manager.connect(thread_id, client_id, ws)
    logger.info("WS connected: client=%s thread=%s", client_id, thread_id)
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")

            if msg_type == "cursor_move":
                await ws_manager.broadcast(thread_id, {
                    "type": "cursor_move",
                    "client_id": client_id,
                    "data": data.get("data"),
                }, exclude=client_id)

            elif msg_type == "block_edit":
                block_id = data.get("block_id")
                content = data.get("content")
                if block_id and content is not None:
                    await canvas_manager.update_block_content(block_id, content)
                await ws_manager.broadcast(thread_id, {
                    "type": "block_edit",
                    "client_id": client_id,
                    "block_id": block_id,
                    "content": content,
                }, exclude=client_id)

            elif msg_type == "block_update":
                block_id = data.get("block_id")
                payload = data.get("data", {})
                block = await canvas_manager.list_blocks(
                    (await canvas_manager.get_canvas(data.get("canvas_id"))).id
                    if data.get("canvas_id") else None
                )
                if block_id:
                    found = next((b for b in (block or []) if b.id == block_id), None)
                    if found:
                        for key, val in payload.items():
                            if hasattr(found, key):
                                setattr(found, key, val)
                        await canvas_manager.update_block(found)
                await ws_manager.broadcast(thread_id, {
                    "type": "block_update",
                    "client_id": client_id,
                    "block_id": block_id,
                    "data": payload,
                }, exclude=client_id)

            elif msg_type == "new_message":
                role = data.get("role", "user")
                content = data.get("content", "")
                msg = await thread_manager.add_message(
                    thread_id=thread_id, role=role, content=content
                )
                if msg:
                    await ws_manager.broadcast(thread_id, {
                        "type": "new_message",
                        "message": _msg_to_dict(msg),
                    })

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WS disconnected: client=%s thread=%s", client_id, thread_id)
    except Exception as e:
        logger.warning("WS error on %s: %s", thread_id, e)
    finally:
        await ws_manager.unlock_all_blocks(thread_id, client_id)
        ws_manager.disconnect(thread_id, client_id)
        await ws_manager.broadcast(thread_id, {
            "type": "peer_left",
            "client_id": client_id,
        })


# ================================================================
# Serialization helpers
# ================================================================

def _thread_to_dict(t: Thread) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "status": t.status.value,
        "tags": t.tags,
        "metadata": t.metadata,
        "parent_thread_id": t.parent_thread_id,
    }


def _msg_to_dict(m: ThreadMessage) -> dict:
    return {
        "id": m.id,
        "thread_id": m.thread_id,
        "role": m.role,
        "content": m.content,
        "timestamp": m.timestamp,
        "parent_id": m.parent_id,
        "tool_calls": m.tool_calls,
        "tool_results": m.tool_results,
        "attachments": m.attachments,
    }


def _canvas_to_dict(c: Canvas) -> dict:
    return {
        "id": c.id,
        "thread_id": c.thread_id,
        "type": c.type.value,
        "content": c.content,
        "position": c.position,
        "size": c.size,
        "z_index": c.z_index,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
        "version": c.version,
    }


def _block_to_dict(b: CanvasBlock) -> dict:
    return {
        "id": b.id,
        "canvas_id": b.canvas_id,
        "type": b.type.value,
        "content": b.content,
        "language": b.language,
        "locked_by": b.locked_by,
        "collaborators": b.collaborators,
        "position": b.position,
        "size": b.size,
        "metadata": b.metadata,
    }
