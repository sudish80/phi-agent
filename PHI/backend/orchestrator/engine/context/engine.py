"""Context Engine — pluggable post-turn transcript maintenance.

Mirrors openclaw's context-engine-*.ts architecture.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TurnContext:
    session_id: str
    messages: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextEngine:
    """Pluggable engine that runs maintenance after each turn.

    Can rewrite transcript entries, run compaction, prune, or index.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._hooks: Dict[str, List[Callable[[TurnContext], Awaitable[None]]]] = {}

    def register_hook(self, event: str, hook: Callable[[TurnContext], Awaitable[None]]) -> None:
        self._hooks.setdefault(event, []).append(hook)
        logger.debug("ContextEngine '%s': registered hook for '%s'", self.name, event)

    async def run_hooks(self, event: str, ctx: TurnContext) -> None:
        for hook in self._hooks.get(event, []):
            try:
                await hook(ctx)
            except Exception as e:
                logger.exception("ContextEngine '%s' hook '%s' failed: %s", self.name, event, e)

    async def maintain(self, ctx: TurnContext) -> None:
        """Run after each turn (bootstrap, compaction, or turn maintenance)."""
        await self.run_hooks("after_turn", ctx)
        if ctx.metadata.get("should_compact"):
            await self.run_hooks("before_compaction", ctx)
            await self._do_compact(ctx)
            await self.run_hooks("after_compaction", ctx)

    async def _do_compact(self, ctx: TurnContext) -> None:
        """Default compaction — subclasses override for custom logic."""
        pass

    async def llm_complete(self, prompt: str) -> str:
        """Context engines can access an LLM for summarization."""
        from backend.shared.llm_client import llm_client
        from backend.shared.llm_client import LLMResponse
        resp = await llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
        )
        return resp.content or ""


class ContextEngineManager:
    """Manages multiple context engines per session."""

    def __init__(self):
        self._engines: Dict[str, ContextEngine] = {}
        self._session_bindings: Dict[str, str] = {}

    def register(self, name: str, engine: ContextEngine) -> None:
        self._engines[name] = engine
        logger.info("ContextEngineManager: registered '%s'", name)

    def get_for_session(self, session_id: str) -> Optional[ContextEngine]:
        engine_name = self._session_bindings.get(session_id, "default")
        return self._engines.get(engine_name)

    def bind_session(self, session_id: str, engine_name: str = "default") -> None:
        self._session_bindings[session_id] = engine_name

    async def maintain_session(self, session_id: str, ctx: TurnContext) -> None:
        engine = self.get_for_session(session_id)
        if engine:
            await engine.maintain(ctx)


# Global singleton
context_engine_manager = ContextEngineManager()
