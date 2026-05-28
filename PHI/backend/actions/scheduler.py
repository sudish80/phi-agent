"""Task scheduler module for J.A.R.V.I.S.

Schedule one-time or recurring tasks.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_scheduled_tasks: Dict[str, Dict[str, Any]] = {}


async def schedule_reminder(delay_minutes: float, message: str) -> str:
    """Schedule a one-time reminder after a delay in minutes."""
    import uuid
    task_id = uuid.uuid4().hex[:8]
    eta = datetime.now() + timedelta(minutes=delay_minutes)

    async def _remind():
        await asyncio.sleep(delay_minutes * 60)
        logger.info(f"Reminder: {message}")
        _scheduled_tasks.pop(task_id, None)

    asyncio.create_task(_remind())
    _scheduled_tasks[task_id] = {
        "type": "reminder",
        "message": message,
        "eta": eta.isoformat(),
        "active": True,
    }
    return (f"Reminder scheduled: '{message}' in {delay_minutes} min. "
            f"Task ID: {task_id}")


async def schedule_at(when: str, message: str) -> str:
    """Schedule a task at a specific time (HH:MM 24h format)."""
    try:
        hour, minute = map(int, when.split(":"))
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        delay = (target - now).total_seconds() / 60
        return await schedule_reminder(delay, message)
    except ValueError:
        return f"Invalid time format: '{when}'. Use HH:MM (24h, e.g. 14:30)"


async def list_scheduled_tasks() -> str:
    """List all currently scheduled tasks."""
    if not _scheduled_tasks:
        return "No scheduled tasks."
    lines = [f"**{len(_scheduled_tasks)} Scheduled Task(s)**"]
    for tid, info in _scheduled_tasks.items():
        lines.append(f"  [{tid}] {info['message']} @ {info['eta']}")
    return "\n".join(lines)


async def cancel_task(task_id: str) -> str:
    """Cancel a scheduled task by ID."""
    if task_id in _scheduled_tasks:
        _scheduled_tasks[task_id]["active"] = False
        del _scheduled_tasks[task_id]
        return f"Cancelled task: {task_id}"
    return f"Task not found: {task_id}"
