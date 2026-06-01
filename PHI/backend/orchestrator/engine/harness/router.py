"""Agent Harness — backend abstraction for multi-provider support.

Mirrors openclaw's harness/selection.ts.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HarnessConfig:
    provider: str = "openclaw"  # openclaw | codex | copilot
    model: str = "gpt-4o"
    max_tokens: int = 8192
    temperature: float = 0.3
    reasoning_effort: str = "high"


class AgentHarness:
    """Abstract harness for running agent turns against a backend."""

    def __init__(self, name: str, config: HarnessConfig):
        self.name = name
        self.config = config

    async def generate(self, messages: List[Dict[str, Any]],
                        tools: Optional[List[Dict]] = None) -> Any:
        """Send messages to the LLM and return response."""
        from backend.shared.llm_client import llm_client
        return await llm_client.generate(messages, tools=tools)

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def supports_tool_calling(self) -> bool:
        return True


class HarnessRouter:
    """Routes agent turns to the correct harness based on provider/model."""

    def __init__(self):
        self._harnesses: Dict[str, AgentHarness] = {}

    def register(self, harness: AgentHarness) -> None:
        self._harnesses[harness.name] = harness
        logger.info("HarnessRouter: registered '%s'", harness.name)

    def select(self, provider: str, model: str) -> AgentHarness:
        """Select the best harness for a provider/model combination."""
        key = f"{provider}/{model}"
        if key in self._harnesses:
            return self._harnesses[key]

        if provider in self._harnesses:
            return self._harnesses[provider]

        return self._harnesses.get("openclaw", AgentHarness("openclaw", HarnessConfig()))

    async def generate(self, provider: str, model: str,
                        messages: List[Dict[str, Any]],
                        tools: Optional[List[Dict]] = None) -> Any:
        harness = self.select(provider, model)
        return await harness.generate(messages, tools=tools)


# Global singleton
harness_router = HarnessRouter()
