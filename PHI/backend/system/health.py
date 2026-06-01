"""Health check system for all PHI AI agent subsystems.

Provides a HealthChecker singleton with individual check methods for each
subsystem and a periodic background task running full checks.
"""

import os
import time
import asyncio
import logging
import platform
import shutil
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path

from backend.system.config import system_config

logger = logging.getLogger(__name__)


class CheckStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    detail: str = ""
    duration_ms: float = 0.0


CheckHandler = Callable[[], "Coroutine[None, None, CheckResult]"]


class HealthChecker:
    """Singleton health checker for all PHI agent subsystems."""

    _instance: Optional["HealthChecker"] = None

    def __new__(cls) -> "HealthChecker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._checks: Dict[str, CheckHandler] = {}
        self._results: List[CheckResult] = []
        self._background_task: Optional[asyncio.Task] = None
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register("database", self.check_database)
        self.register("redis", self.check_redis)
        self.register("llm", self.check_llm)
        self.register("mcp", self.check_mcp)
        self.register("channels", self.check_channels)
        self.register("calling", self.check_calling)
        self.register("audio", self.check_audio)
        self.register("disk", self.check_disk)
        self.register("memory", self.check_memory)

    def register(self, name: str, handler: CheckHandler) -> None:
        self._checks[name] = handler

    def unregister(self, name: str) -> None:
        self._checks.pop(name, None)

    async def check_database(self) -> CheckResult:
        start = time.perf_counter()
        paths = [
            ("session_store", system_config.session_db_path),
            ("thread_store", system_config.thread_db_path),
            ("canvas_store", system_config.canvas_db_path),
        ]
        unreachable: List[str] = []
        for label, db_path in paths:
            if not db_path:
                unreachable.append(f"{label}: no path configured")
                continue
            try:
                import aiosqlite
                async with aiosqlite.connect(db_path, timeout=5) as conn:
                    cursor = await conn.execute("SELECT 1")
                    await cursor.fetchone()
            except Exception as e:
                unreachable.append(f"{label}: {e}")
        elapsed = (time.perf_counter() - start) * 1000
        if unreachable:
            detail = "; ".join(unreachable)
            status = CheckStatus.ERROR if len(unreachable) == len(paths) else CheckStatus.WARN
            return CheckResult("database", status, detail, elapsed)
        return CheckResult("database", CheckStatus.OK, "All databases accessible", elapsed)

    async def check_redis(self) -> CheckResult:
        start = time.perf_counter()
        if not system_config.redis_enabled:
            return CheckResult("redis", CheckStatus.OK, "Redis not enabled, skipping", 0.0)
        try:
            import redis.asyncio as aioredis
            client = await aioredis.from_url(
                system_config.redis_url,
                socket_connect_timeout=3,
                decode_responses=True,
            )
            pong = await client.ping()
            await client.aclose()
            elapsed = (time.perf_counter() - start) * 1000
            if pong:
                return CheckResult("redis", CheckStatus.OK, "Redis ping succeeded", elapsed)
            return CheckResult("redis", CheckStatus.ERROR, "Redis ping returned false", elapsed)
        except ImportError:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("redis", CheckStatus.WARN, "redis-py not installed", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("redis", CheckStatus.ERROR, str(e), elapsed)

    async def check_llm(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from backend.shared.llm_client import llm_client
            resp = await llm_client.generate(
                messages=[{"role": "user", "content": "Reply with just the word: pong"}],
                allow_failover=True,
            )
            elapsed = (time.perf_counter() - start) * 1000
            if resp and resp.content:
                return CheckResult("llm", CheckStatus.OK, f"Responded via {resp.provider.value}", elapsed)
            return CheckResult("llm", CheckStatus.WARN, "Empty response", elapsed)
        except ImportError:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("llm", CheckStatus.WARN, "LLM client not available", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("llm", CheckStatus.ERROR, str(e), elapsed)

    async def check_mcp(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from backend.mcp.runtime import mcp_runtime
            tools = await mcp_runtime.discover_tools()
            elapsed = (time.perf_counter() - start) * 1000
            count = len(tools)
            if count > 0:
                return CheckResult("mcp", CheckStatus.OK, f"{count} MCP tool(s) discovered", elapsed)
            return CheckResult("mcp", CheckStatus.OK, "No MCP tools, but runtime is active", elapsed)
        except ImportError:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("mcp", CheckStatus.WARN, "MCP runtime not available", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("mcp", CheckStatus.ERROR, str(e), elapsed)

    async def check_channels(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from backend.channels.base import get_registered_channels
            channels = get_registered_channels()
            elapsed = (time.perf_counter() - start) * 1000
            if channels:
                names = [c.name for c in channels]
                return CheckResult("channels", CheckStatus.OK, f"Connected: {', '.join(names)}", elapsed)
            return CheckResult("channels", CheckStatus.OK, "No channels registered", elapsed)
        except ImportError:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("channels", CheckStatus.WARN, "Channels module not available", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("channels", CheckStatus.ERROR, str(e), elapsed)

    async def check_calling(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from backend.calling.manager import call_manager
            active = await call_manager.get_active_calls()
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("calling", CheckStatus.OK, f"{len(active)} active call(s)", elapsed)
        except ImportError:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("calling", CheckStatus.WARN, "Calling module not available", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("calling", CheckStatus.ERROR, str(e), elapsed)

    async def check_audio(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from backend.media.audio import get_audio_registry
            registry = get_audio_registry()
            processors = registry.list_processors()
            elapsed = (time.perf_counter() - start) * 1000
            if processors:
                return CheckResult("audio", CheckStatus.OK, f"Processors: {', '.join(processors)}", elapsed)
            return CheckResult("audio", CheckStatus.WARN, "No audio processors registered", elapsed)
        except ImportError:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("audio", CheckStatus.WARN, "Audio module not available", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("audio", CheckStatus.ERROR, str(e), elapsed)

    async def check_disk(self) -> CheckResult:
        start = time.perf_counter()
        dirs = {
            "audio": system_config.audio_store_path,
            "canvas": str(Path(system_config.canvas_db_path).parent),
            "memory": str(ROOT_DIR / "memory_store") if _root_dir() else "",
        }
        issues: List[str] = []
        warnings: List[str] = []
        for label, d in dirs.items():
            if not d or not os.path.isdir(d):
                issues.append(f"{label}: path missing or not a directory")
                continue
            try:
                usage = shutil.disk_usage(d)
                free_gb = usage.free / (1024 ** 3)
                total_gb = usage.total / (1024 ** 3)
                if free_gb < 0.5:
                    issues.append(f"{label}: only {free_gb:.2f} GB free")
                elif free_gb < 2.0:
                    warnings.append(f"{label}: {free_gb:.2f} GB free")
            except Exception as e:
                warnings.append(f"{label}: disk usage check failed ({e})")
        elapsed = (time.perf_counter() - start) * 1000
        if issues:
            detail = "; ".join(issues)
            if warnings:
                detail += " | " + "; ".join(warnings)
            return CheckResult("disk", CheckStatus.ERROR, detail, elapsed)
        if warnings:
            return CheckResult("disk", CheckStatus.WARN, "; ".join(warnings), elapsed)
        return CheckResult("disk", CheckStatus.OK, "Sufficient disk space", elapsed)

    async def check_memory(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import psutil
            mem = psutil.virtual_memory()
            elapsed = (time.perf_counter() - start) * 1000
            percent = mem.percent
            used_gb = mem.used / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)
            detail = f"{used_gb:.1f} / {total_gb:.1f} GB ({percent:.1f}%)"
            if percent > 90:
                return CheckResult("memory", CheckStatus.ERROR, detail, elapsed)
            if percent > 75:
                return CheckResult("memory", CheckStatus.WARN, detail, elapsed)
            return CheckResult("memory", CheckStatus.OK, detail, elapsed)
        except ImportError:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("memory", CheckStatus.WARN, "psutil not installed", elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult("memory", CheckStatus.ERROR, str(e), elapsed)

    async def run_check(self, name: str) -> Optional[CheckResult]:
        handler = self._checks.get(name)
        if handler is None:
            return None
        return await handler()

    async def full_check(self) -> List[CheckResult]:
        results: List[CheckResult] = []
        for name, handler in self._checks.items():
            try:
                result = await handler()
                results.append(result)
            except Exception as e:
                results.append(CheckResult(name, CheckStatus.ERROR, str(e), 0.0))
        self._results = results
        return results

    def summary(self) -> Dict:
        results = self._results
        if not results:
            return {"status": "unknown", "total": 0, "ok": 0, "warnings": 0, "errors": 0}
        ok_count = sum(1 for r in results if r.status == CheckStatus.OK)
        warn_count = sum(1 for r in results if r.status == CheckStatus.WARN)
        err_count = sum(1 for r in results if r.status == CheckStatus.ERROR)
        if err_count > 0:
            status = "error"
        elif warn_count > 0:
            status = "warning"
        else:
            status = "ok"
        return {
            "status": status,
            "total": len(results),
            "ok": ok_count,
            "warnings": warn_count,
            "errors": err_count,
            "results": [
                {"name": r.name, "status": r.status.value, "detail": r.detail, "duration_ms": round(r.duration_ms, 2)}
                for r in results
            ],
        }

    async def periodic_check(self, interval: int = 60) -> None:
        while True:
            try:
                results = await self.full_check()
                ok_count = sum(1 for r in results if r.status == CheckStatus.OK)
                err_count = sum(1 for r in results if r.status == CheckStatus.ERROR)
                warn_count = sum(1 for r in results if r.status == CheckStatus.WARN)
                logger.info(
                    "Health check complete: %d ok, %d warnings, %d errors",
                    ok_count, warn_count, err_count,
                )
                for r in results:
                    if r.status in (CheckStatus.WARN, CheckStatus.ERROR):
                        logger.warning("  [%s] %s: %s (%.0f ms)", r.status.value, r.name, r.detail, r.duration_ms)
            except Exception as e:
                logger.error("Periodic health check error: %s", e)
            await asyncio.sleep(interval)

    def start_background(self, interval: int = 60) -> None:
        if self._background_task is None or self._background_task.done():
            self._background_task = asyncio.create_task(self.periodic_check(interval))
            logger.info("Background health checker started (interval=%ds)", interval)

    def stop_background(self) -> None:
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            self._background_task = None
            logger.info("Background health checker stopped")


def _root_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent


ROOT_DIR = _root_dir()
health_checker = HealthChecker()
