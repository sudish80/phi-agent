"""Tool wrappers for Real Download Engine"""
import logging
from backend.shared.download_engine import download_engine

logger = logging.getLogger(__name__)

def download_queue(url: str, filename: str = None, user_id: int = 0) -> dict:
    return download_engine.queue_download(user_id, url, filename)

def download_list(user_id: int = 0) -> dict:
    items = download_engine.list_downloads(user_id)
    return {"downloads": items, "count": len(items)}

def download_status(download_id: int) -> dict:
    return download_engine.get_status(download_id)

def download_pause(download_id: int) -> dict:
    return download_engine.pause(download_id)

def download_resume(download_id: int) -> dict:
    return download_engine.resume(download_id)

def download_cancel(download_id: int) -> dict:
    return download_engine.cancel(download_id)

def download_stats() -> dict:
    return download_engine.get_stats()

def set_bandwidth(mbps: float) -> dict:
    download_engine.set_bandwidth(mbps)
    return {"status": "success", "bandwidth_mbps": mbps}

def set_concurrency(max_concurrent: int) -> dict:
    download_engine.set_concurrency(max_concurrent)
    return {"status": "success", "max_concurrent": max_concurrent}

def get_download_tools():
    from backend.orchestrator.agent import Tool
    return [
        Tool(name="download_queue", description="Queue a file download from a URL. Returns download_id to track progress.", parameters={"type": "object", "properties": {"url": {"type": "string", "description": "URL of the file to download"}, "filename": {"type": "string", "description": "Optional filename to save as"}, "user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": ["url"]}, handler=download_queue, category="utility"),
        Tool(name="download_list", description="List all downloads (active, queued, completed)", parameters={"type": "object", "properties": {"user_id": {"type": "integer", "description": "User ID (default 0)"}}, "required": []}, handler=download_list, category="utility"),
        Tool(name="download_status", description="Get status and progress of a specific download", parameters={"type": "object", "properties": {"download_id": {"type": "integer", "description": "Download ID from download_queue"}}, "required": ["download_id"]}, handler=download_status, category="utility"),
        Tool(name="download_pause", description="Pause an active download", parameters={"type": "object", "properties": {"download_id": {"type": "integer", "description": "Download ID to pause"}}, "required": ["download_id"]}, handler=download_pause, category="utility"),
        Tool(name="download_resume", description="Resume a paused download", parameters={"type": "object", "properties": {"download_id": {"type": "integer", "description": "Download ID to resume"}}, "required": ["download_id"]}, handler=download_resume, category="utility"),
        Tool(name="download_cancel", description="Cancel a queued or active download", parameters={"type": "object", "properties": {"download_id": {"type": "integer", "description": "Download ID to cancel"}}, "required": ["download_id"]}, handler=download_cancel, category="utility"),
        Tool(name="download_stats", description="Get download engine statistics (active, queued, completed, speed)", parameters={"type": "object", "properties": {}, "required": []}, handler=download_stats, category="utility"),
        Tool(name="set_bandwidth", description="Set download bandwidth limit in Mbps", parameters={"type": "object", "properties": {"mbps": {"type": "number", "description": "Bandwidth in Mbps (e.g., 5 for 5 MB/s)"}}, "required": ["mbps"]}, handler=set_bandwidth, category="utility"),
        Tool(name="set_concurrency", description="Set maximum concurrent downloads", parameters={"type": "object", "properties": {"max_concurrent": {"type": "integer", "description": "Max concurrent downloads (default 3)"}}, "required": ["max_concurrent"]}, handler=set_concurrency, category="utility"),
    ]
