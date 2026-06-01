"""Before-tool-call hooks — intercept, validate, and block tool calls before execution.

Mirrors openclaw's agent-tools.before-tool-call.ts with:
  - Plugin hooks (before_tool_call)
  - Loop detection (detect stuck tool loops)
  - Policy enforcement (tool allow/deny)
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Awaitable
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ToolCallContext:
    session_id: str
    tool_name: str
    tool_args: Dict[str, Any]
    tool_call_id: str
    step: int
    timestamp: float = 0.0


@dataclass
class BeforeToolCallResult:
    blocked: bool = False
    reason: str = ""
    replacement_output: Optional[str] = None


# ---- Loop detection ----

@dataclass
class ToolCallRecord:
    tool_name: str
    args_hash: str
    timestamp: float
    result_hash: str = ""


class ToolLoopDetector:
    """Detects stuck tool loops (same tool + same args repeatedly)."""

    def __init__(self, max_repeats: int = 3, window_seconds: float = 60.0):
        self.max_repeats = max_repeats
        self.window_seconds = window_seconds
        self._records: Dict[str, List[ToolCallRecord]] = defaultdict(list)

    def _hash_args(self, args: Dict[str, Any]) -> str:
        return str(sorted(args.items()))

    def record_call(self, session_id: str, tool_name: str,
                     args: Dict[str, Any], result: str = "") -> None:
        now = time.time()
        record = ToolCallRecord(
            tool_name=tool_name,
            args_hash=self._hash_args(args),
            timestamp=now,
            result_hash=result[:100],
        )
        self._records[session_id].append(record)
        # Prune old records
        self._records[session_id] = [
            r for r in self._records[session_id]
            if now - r.timestamp < self.window_seconds
        ]

    def is_looping(self, session_id: str, tool_name: str,
                    args: Dict[str, Any]) -> Optional[str]:
        """Returns reason if loop detected, None otherwise."""
        now = time.time()
        recent = [
            r for r in self._records.get(session_id, [])
            if now - r.timestamp < self.window_seconds
            and r.tool_name == tool_name
        ]
        if len(recent) < self.max_repeats:
            return None

        # Check if same tool with same args repeatedly
        args_hash = self._hash_args(args)
        same_args = [r for r in recent if r.args_hash == args_hash]
        if len(same_args) >= self.max_repeats:
            return f"Tool '{tool_name}' called with identical args {self.max_repeats} times"

        return None

    def reset_session(self, session_id: str) -> None:
        self._records.pop(session_id, None)


# ---- Before-tool-call hook system ----

class BeforeToolCallHook:
    """Base class for before-tool-call hooks."""

    async def __call__(self, ctx: ToolCallContext) -> BeforeToolCallResult:
        return BeforeToolCallResult()


class PolicyEnforcementHook(BeforeToolCallHook):
    """Check tool policy before allowing execution."""

    def __init__(self, allowed_tools: Optional[set] = None,
                 denied_tools: Optional[set] = None):
        self.allowed_tools = allowed_tools
        self.denied_tools = denied_tools or set()

    async def __call__(self, ctx: ToolCallContext) -> BeforeToolCallResult:
        if ctx.tool_name in self.denied_tools:
            return BeforeToolCallResult(
                blocked=True,
                reason=f"Tool '{ctx.tool_name}' is denied by policy",
                replacement_output=f"Tool '{ctx.tool_name}' is not allowed.",
            )
        if self.allowed_tools and ctx.tool_name not in self.allowed_tools:
            return BeforeToolCallResult(
                blocked=True,
                reason=f"Tool '{ctx.tool_name}' not in allowed tools",
                replacement_output=f"Tool '{ctx.tool_name}' is not available for this session.",
            )
        return BeforeToolCallResult()


class LoopDetectionHook(BeforeToolCallHook):
    """Detect and block tool loops."""

    def __init__(self, detector: ToolLoopDetector):
        self.detector = detector

    async def __call__(self, ctx: ToolCallContext) -> BeforeToolCallResult:
        reason = self.detector.is_looping(ctx.session_id, ctx.tool_name, ctx.tool_args)
        if reason:
            return BeforeToolCallResult(
                blocked=True,
                reason=reason,
                replacement_output="I seem to be stuck in a loop. Let me try a different approach.",
            )
        return BeforeToolCallResult()


class BeforeToolCallManager:
    """Manages and runs all before-tool-call hooks."""

    def __init__(self):
        self._hooks: List[BeforeToolCallHook] = []
        self.loop_detector = ToolLoopDetector()

    def register(self, hook: BeforeToolCallHook) -> None:
        self._hooks.append(hook)
        logger.info("BeforeToolCallManager: registered hook %s", type(hook).__name__)

    async def run_hooks(self, ctx: ToolCallContext) -> BeforeToolCallResult:
        for hook in self._hooks:
            try:
                result = await hook(ctx)
                if result.blocked:
                    logger.warning("Tool call blocked: %s - %s", ctx.tool_name, result.reason)
                    return result
            except Exception as e:
                logger.exception("Before-tool-call hook failed: %s", e)
        return BeforeToolCallResult()

    def record_result(self, ctx: ToolCallContext, result: str = "") -> None:
        self.loop_detector.record_call(
            ctx.session_id, ctx.tool_name, ctx.tool_args, result
        )

    def reset_session(self, session_id: str) -> None:
        self.loop_detector.reset_session(session_id)


# Global singleton
before_tool_call_manager = BeforeToolCallManager()


def setup_default_hooks(allowed_tools: Optional[set] = None) -> None:
    """Register default hook set."""
    before_tool_call_manager.register(LoopDetectionHook(before_tool_call_manager.loop_detector))
    before_tool_call_manager.register(PolicyEnforcementHook(allowed_tools=allowed_tools))
