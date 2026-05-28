"""Core Agent — orchestrates LLM, tools, memory, and multi-agent sub-agents."""

import json
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    category: str = "utility"


class ToolRegistry:
    """Registry for discovering and executing tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._lock = asyncio.Lock()

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "category": t.category,
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, kwargs: Dict[str, Any]) -> str:
        tool = self.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found."
        try:
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(**kwargs)
            else:
                result = tool.handler(**kwargs)
            return str(result) if result is not None else ""
        except Exception as e:
            logger.exception(f"Tool '{name}' execution failed")
            return f"Error executing {name}: {e}"

    def __len__(self) -> int:
        return len(self._tools)


class Agent:
    """Main agent with LLM-driven ReAct loop, tool registry, and session memory."""

    def __init__(self):
        self.tools = ToolRegistry()
        self._sessions: Dict[str, List[Dict]] = defaultdict(list)
        self._max_history: int = 50

    def _load_tools(self) -> None:
        from backend.tools.autoregister import get_all_tool_batches
        for batch in get_all_tool_batches():
            for tool in batch:
                self.tools.register(tool)
        logger.info("Registered %d tools from autoregister", len(self.tools))

    # ------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------

    def _get_history(self, session_id: str) -> List[Dict]:
        return self._sessions.get(session_id, [])

    def _add_to_history(self, session_id: str, role: str, content: str) -> None:
        self._sessions[session_id].append({"role": role, "content": content})
        if len(self._sessions[session_id]) > self._max_history:
            self._sessions[session_id] = self._sessions[session_id][-self._max_history:]

    def reset_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # ------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------

    async def process(
        self,
        message: str,
        session_id: str,
        image: Optional[str] = None,
        emotion: str = "neutral",
    ) -> Dict[str, Any]:
        start = time.time()

        from backend.shared.llm_client import llm_client
        from backend.shared.config import settings

        history = self._get_history(session_id)
        self._add_to_history(session_id, "user", message)

        system_prompt = self._build_system_prompt(session_id, emotion)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-10:])

        try:
            response = await llm_client.generate(messages)
            reply_text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.exception("LLM generation failed")
            reply_text = "I apologize, I encountered an error processing your request."

        self._add_to_history(session_id, "assistant", reply_text)

        elapsed_ms = (time.time() - start) * 1000

        return {
            "reply": reply_text,
            "emotion": "neutral",
            "actions_taken": [],
            "memory_updated": False,
            "confidence": 0.7,
            "intent": "general",
            "tool_recommendations": [],
            "processing_time_ms": elapsed_ms,
        }

    async def process_stream(
        self,
        message: str,
        session_id: str,
        emotion: str = "neutral",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        from backend.shared.llm_client import llm_client
        from backend.shared.config import settings

        history = self._get_history(session_id)
        self._add_to_history(session_id, "user", message)

        system_prompt = self._build_system_prompt(session_id, emotion)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-10:])

        yield {"type": "mode", "mode": "thinking"}

        full_reply = ""
        try:
            async for chunk in llm_client.generate_stream(messages):
                full_reply += chunk
                yield {"type": "token", "content": chunk}
        except Exception as e:
            logger.exception("Stream generation failed")
            yield {"type": "token", "content": "I apologize, I encountered an error."}

        self._add_to_history(session_id, "assistant", full_reply)

        yield {"type": "done", "reply": full_reply, "emotion": "neutral"}

    async def execute_tool(self, tool_name: str, session_id: str = "", **kwargs) -> str:
        return await self.tools.execute(tool_name, kwargs)

    async def _request_hitl(self, action: str, args: Dict[str, Any]) -> bool:
        """Human-in-the-loop approval for sensitive actions.
        
        Returns True (approved) by default. Subclasses or wrappers can
        override to prompt the user via WebSocket or CLI.
        """
        return True

    def _build_system_prompt(self, session_id: str, emotion: str) -> str:
        from backend.shared.config import settings
        tools_info = self.tools.list_tools()
        tools_desc = "\n".join(
            f"- {t['name']}: {t['description']}" for t in tools_info[:50]
        )
        if len(tools_info) > 50:
            tools_desc += f"\n- ... and {len(tools_info) - 50} more tools"

        return (
            f"You are {settings.phi_wake_word.title()}, an AI assistant. "
            f"Your creator is {settings.user_name}. "
            "You have access to the following tools:\n"
            f"{tools_desc}\n\n"
            f"Current user emotion: {emotion}\n"
            "Be helpful, concise, and friendly."
        )


agent = Agent()
agent._load_tools()
