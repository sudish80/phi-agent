"""Data models for the Canvas/Thread system."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ThreadStatus(str, Enum):
    active = "active"
    archived = "archived"


class CanvasType(str, Enum):
    text = "text"
    code = "code"
    mermaid = "mermaid"
    drawing = "drawing"


class BlockType(str, Enum):
    text = "text"
    code = "code"
    mermaid = "mermaid"
    drawing = "drawing"
    image = "image"
    file = "file"
    embed = "embed"


@dataclass
class Thread:
    id: str
    title: str
    created_at: float
    updated_at: float
    status: ThreadStatus = ThreadStatus.active
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_thread_id: Optional[str] = None


@dataclass
class ThreadMessage:
    id: str
    thread_id: str
    role: str
    content: str
    timestamp: float
    parent_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


@dataclass
class Canvas:
    id: str
    thread_id: str
    type: CanvasType = CanvasType.text
    content: str = ""
    position: Optional[Dict[str, float]] = None
    size: Optional[Dict[str, float]] = None
    z_index: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    version: int = 1


@dataclass
class CanvasBlock:
    id: str
    canvas_id: str
    type: BlockType = BlockType.text
    content: str = ""
    language: Optional[str] = None
    locked_by: Optional[str] = None
    collaborators: List[str] = field(default_factory=list)
    position: Optional[Dict[str, float]] = None
    size: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
