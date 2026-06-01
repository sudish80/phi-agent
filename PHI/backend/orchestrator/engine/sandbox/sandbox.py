"""Sandbox — isolated execution environment for agent tools.

Mirrors openclaw's sandbox/ architecture with Docker backend support.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    enabled: bool = False
    backend: str = "docker"  # docker | ssh | none
    image: str = "python:3.11-slim"
    timeout: int = 60
    network_enabled: bool = False
    allowed_tools: Set[str] = field(default_factory=lambda: {
        "bash_exec", "run_python", "file_read", "file_write", "file_search",
    })
    workspace_mount: str = "/workspace"
    memory_mb: int = 512
    cpu_quota: float = 1.0


class Sandbox:
    """Per-session sandbox for isolated tool execution."""

    def __init__(self, config: SandboxConfig, session_id: str):
        self.config = config
        self.session_id = session_id
        self._container_id: Optional[str] = None
        self._temp_dir: Optional[str] = None

    async def start(self) -> bool:
        if not self.config.enabled or self.config.backend != "docker":
            return False
        try:
            self._temp_dir = tempfile.mkdtemp(prefix=f"phi_sandbox_{self.session_id[:8]}_")
            cmd = [
                "docker", "run", "-d", "--rm",
                "--network", "none" if not self.config.network_enabled else "bridge",
                "-v", f"{self._temp_dir}:{self.config.workspace_mount}",
                "--memory", f"{self.config.memory_mb}m",
                "--cpus", str(self.config.cpu_quota),
                self.config.image,
                "sleep", "infinity",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error("Sandbox start failed: %s", stderr.decode())
                return False
            self._container_id = stdout.decode().strip()
            logger.info("Sandbox started: %s (container: %s)", self.session_id, self._container_id[:12])
            return True
        except FileNotFoundError:
            logger.warning("Docker not available, sandbox disabled")
            return False
        except Exception as e:
            logger.error("Sandbox start error: %s", e)
            return False

    async def stop(self) -> None:
        if self._container_id:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "kill", self._container_id,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                await proc.communicate()
                logger.info("Sandbox stopped: %s", self.session_id)
            except Exception as e:
                logger.error("Sandbox stop error: %s", e)
            self._container_id = None
        if self._temp_dir and os.path.exists(self._temp_dir):
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    async def exec(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Run a command inside the sandbox container."""
        if not self._container_id:
            return {"stdout": "", "stderr": "Sandbox not started", "returncode": -1}

        t = timeout or self.config.timeout
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", "-i", self._container_id,
                "sh", "-c", command,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=t)
            return {
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "returncode": proc.returncode or 0,
            }
        except asyncio.TimeoutError:
            return {"stdout": "", "stderr": f"Command timed out after {t}s", "returncode": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "returncode": -1}

    @property
    def is_running(self) -> bool:
        return self._container_id is not None


class SandboxManager:
    """Manages sandboxes across sessions."""

    def __init__(self):
        self._sandboxes: Dict[str, Sandbox] = {}
        self._default_config = SandboxConfig()

    async def get_or_create(self, session_id: str,
                             config: Optional[SandboxConfig] = None) -> Sandbox:
        if session_id in self._sandboxes:
            return self._sandboxes[session_id]
        sb = Sandbox(config or self._default_config, session_id)
        await sb.start()
        self._sandboxes[session_id] = sb
        return sb

    async def stop_session(self, session_id: str) -> None:
        sb = self._sandboxes.pop(session_id, None)
        if sb:
            await sb.stop()

    async def stop_all(self) -> None:
        for sid in list(self._sandboxes.keys()):
            await self.stop_session(sid)

    def prune_idle(self, max_idle_minutes: int = 30) -> int:
        """Placeholder — real implementation would track last activity timestamps."""
        return 0


# Global singleton
sandbox_manager = SandboxManager()
