"""Task System — persistent scheduled tasks and workflows."""

import logging
import time
import json
import asyncio
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str
    name: str
    workflow: str
    params: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    updated_at: float = 0.0
    result: Optional[str] = None
    error: Optional[str] = None


class TaskQueue:
    """Simple in-memory task queue with status tracking."""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._handlers: Dict[str, Callable] = {}

    def register_handler(self, workflow: str, handler: Callable) -> None:
        self._handlers[workflow] = handler

    def create_task(self, name: str, workflow: str,
                     params: Optional[Dict] = None) -> Task:
        import uuid
        task_id = uuid.uuid4().hex[:12]
        now = time.time()
        task = Task(
            id=task_id, name=name, workflow=workflow,
            params=params or {}, created_at=now, updated_at=now,
        )
        self._tasks[task_id] = task
        logger.info("Task created: %s (%s)", task_id, workflow)
        return task

    async def execute_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        handler = self._handlers.get(task.workflow)
        if not handler:
            task.status = TaskStatus.FAILED
            task.error = f"No handler for workflow '{task.workflow}'"
            return

        task.status = TaskStatus.RUNNING
        task.updated_at = time.time()
        try:
            result = await handler(task.params)
            task.status = TaskStatus.COMPLETED
            task.result = str(result)[:1000]
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        task.updated_at = time.time()

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 20) -> List[Task]:
        return sorted(
            self._tasks.values(),
            key=lambda t: t.created_at, reverse=True
        )[:limit]


task_queue = TaskQueue()
