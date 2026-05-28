"""Core Agent — orchestrates LLM, tools, memory, and multi-agent sub-agents."""

import json
import re
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


def _convert_to_openai_tools(tools_list: List[Dict]) -> List[Dict]:
    """Convert our internal tool format to OpenAI-compatible tool definitions."""
    result = []
    for t in tools_list:
        params = t.get("parameters", {})
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": params.get("properties", {}),
                    "required": params.get("required", []),
                },
            },
        })
    return result


_REACT_JSON_RE = re.compile(r'\{\s*"(?:tool|reply)"\s*:')

def _try_parse_tool_call(text: str) -> Optional[Dict]:
    """Try to extract a JSON tool call from LLM output (handles nested braces)."""
    if not _REACT_JSON_RE.search(text):
        return None
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start:i+1]
                try:
                    obj = json.loads(candidate)
                    if "tool" in obj and isinstance(obj["tool"], str):
                        return {
                            "name": obj["tool"],
                            "arguments": obj.get("args", {}),
                            "thought": obj.get("thought", ""),
                        }
                    if "reply" in obj:
                        return {"reply": obj["reply"]}
                except (json.JSONDecodeError, TypeError):
                    pass
                start = -1
    return None


def _try_parse_raw_tool_calls(raw: Optional[Dict]) -> Optional[List[Dict]]:
    """Extract tool calls from the raw API response (OpenAI format)."""
    if not raw:
        return None
    try:
        choice = raw.get("choices", [{}])[0]
        msg = choice.get("message", {})
        tcs = msg.get("tool_calls")
        if not tcs:
            return None
        parsed = []
        for tc in tcs:
            fn = tc.get("function", {})
            parsed.append({
                "name": fn.get("name", ""),
                "arguments": json.loads(fn.get("arguments", "{}")),
                "id": tc.get("id", ""),
            })
        return parsed
    except (KeyError, json.JSONDecodeError, IndexError):
        return None


class Agent:
    """Main agent with LLM-driven ReAct loop, tool registry, and session memory."""

    def __init__(self):
        self.tools = ToolRegistry()
        self._sessions: Dict[str, List[Dict]] = defaultdict(list)
        self._max_history: int = 50
        self._max_react_steps: int = 10

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
    # Core processing with ReAct loop
    # ------------------------------------------------------------

    async def process(
        self,
        message: str,
        session_id: str,
        image: Optional[str] = None,
        emotion: str = "neutral",
    ) -> Dict[str, Any]:
        process_start = time.time()

        from backend.shared.llm_client import llm_client
        from backend.shared.config import settings

        self._add_to_history(session_id, "user", message)

        history = self._get_history(session_id)
        all_tools = self.tools.list_tools()
        system_prompt = self._build_system_prompt(all_tools, emotion)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-10:])

        actions_taken: List[str] = []
        tool_recommendations: List[Dict] = []
        step = 0

        while step < self._max_react_steps:
            step += 1
            try:
                response = await llm_client.generate(messages)
            except Exception as e:
                logger.exception("LLM generation failed at step %d", step)
                messages.append({"role": "assistant", "content": f"Error: {e}"})
                break

            content = response.content or ""
            raw = getattr(response, "raw", None)

            # Priority 1: native tool_calls from raw API response
            native_calls = _try_parse_raw_tool_calls(raw)

            # Priority 2: text-based JSON tool call
            text_call = _try_parse_tool_call(content) if not native_calls else None

            tool_calls = native_calls
            if not tool_calls and text_call:
                if "reply" in text_call:
                    messages.append({"role": "assistant", "content": text_call["reply"]})
                    self._add_to_history(session_id, "assistant", text_call["reply"])
                    elapsed_ms = (time.time() - process_start) * 1000
                    return {
                        "reply": text_call["reply"],
                        "emotion": "neutral",
                        "actions_taken": actions_taken,
                        "memory_updated": False,
                        "confidence": 0.7,
                        "intent": "general",
                        "tool_recommendations": tool_recommendations,
                        "processing_time_ms": elapsed_ms,
                    }
                tool_calls = [text_call]

            if not tool_calls:
                messages.append({"role": "assistant", "content": content})
                self._add_to_history(session_id, "assistant", content)
                elapsed_ms = (time.time() - process_start) * 1000
                return {
                    "reply": content or "I have no additional response.",
                    "emotion": "neutral",
                    "actions_taken": actions_taken,
                    "memory_updated": False,
                    "confidence": 0.7,
                    "intent": "general",
                    "tool_recommendations": tool_recommendations,
                    "processing_time_ms": elapsed_ms,
                }

            for call in tool_calls:
                tool_name = call.get("name", "")
                tool_args = call.get("arguments", {})
                if not tool_name:
                    continue

                call_id = call.get("id", "")

                messages.append({
                    "role": "assistant",
                    "content": json.dumps({"tool": tool_name, "args": tool_args}),
                })

                actions_taken.append(tool_name)
                tool_recommendations.append({"tool": tool_name, "arguments": tool_args})

                observation = await self.tools.execute(tool_name, tool_args)

                if call_id:
                    messages.append({
                        "role": "tool",
                        "content": observation,
                        "tool_call_id": call_id,
                        "name": tool_name,
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": f"Tool '{tool_name}' returned: {observation[:2000]}",
                    })

        elapsed_ms = (time.time() - process_start) * 1000
        return {
            "reply": "I've completed my analysis but couldn't determine the best answer. Please rephrase your request.",
            "emotion": "neutral",
            "actions_taken": actions_taken,
            "memory_updated": False,
            "confidence": 0.7,
            "intent": "general",
            "tool_recommendations": tool_recommendations,
            "processing_time_ms": elapsed_ms,
        }

    async def process_stream(
        self,
        message: str,
        session_id: str,
        emotion: str = "neutral",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        from backend.shared.llm_client import llm_client

        self._add_to_history(session_id, "user", message)

        history = self._get_history(session_id)
        all_tools = self.tools.list_tools()
        system_prompt = self._build_system_prompt(all_tools, emotion)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-10:])

        yield {"type": "mode", "mode": "thinking"}

        full_reply = ""
        step = 0
        while step < self._max_react_steps:
            step += 1

            try:
                response = await llm_client.generate(messages)
            except Exception as e:
                logger.exception("Stream LLM generation failed at step %d", step)
                yield {"type": "token", "content": "\n\nI encountered an error processing your request."}
                break

            content = response.content or ""
            raw = getattr(response, "raw", None)

            native_calls = _try_parse_raw_tool_calls(raw)
            text_call = _try_parse_tool_call(content) if not native_calls else None

            tool_calls = native_calls
            if not tool_calls and text_call:
                if "reply" in text_call:
                    yield {"type": "token", "content": text_call["reply"]}
                    full_reply = text_call["reply"]
                    break
                tool_calls = [text_call]

            if not tool_calls:
                yield {"type": "token", "content": content}
                full_reply = content
                break

            for call in tool_calls:
                tool_name = call.get("name", "")
                tool_args = call.get("arguments", {})
                if not tool_name:
                    continue

                yield {"type": "tool_start", "tool": tool_name, "arguments": tool_args}

                observation = await self.tools.execute(tool_name, tool_args)

                yield {"type": "tool_end", "tool": tool_name, "observation": observation[:500]}

                call_id = call.get("id", "")
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({"tool": tool_name, "args": tool_args}),
                })
                if call_id:
                    messages.append({
                        "role": "tool",
                        "content": observation,
                        "tool_call_id": call_id,
                        "name": tool_name,
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": f"Tool '{tool_name}' returned: {observation[:2000]}",
                    })

        self._add_to_history(session_id, "assistant", full_reply)
        yield {"type": "done", "reply": full_reply, "emotion": "neutral"}

    async def execute_tool(self, tool_name: str, session_id: str = "", **kwargs) -> str:
        return await self.tools.execute(tool_name, kwargs)

    async def _request_hitl(self, action: str, args: Dict[str, Any]) -> bool:
        return True

    def _build_system_prompt(self, all_tools: List[Dict], emotion: str) -> str:
        from backend.shared.config import settings

        def _short_sig(t: Dict) -> str:
            params = t.get("parameters", {}).get("properties", {})
            required = set(t.get("parameters", {}).get("required", []))
            parts = []
            for name, schema in params.items():
                prefix = "*" if name in required else ""
                ptype = schema.get("type", "str")
                parts.append(f"{prefix}{name}:{ptype}")
            sig = ", ".join(parts)
            return f"{t['name']}({sig})" if sig else t['name']

        cats: Dict[str, List[str]] = {}
        for t in all_tools:
            cat = t.get("category", "other") or "other"
            cats.setdefault(cat, []).append(_short_sig(t))

        lines = [f"  [{cat}]" + "".join(f"\n    {n}" for n in names) for cat, names in sorted(cats.items())]
        tools_summary = "\n".join(lines)

        return (
            f"You are {settings.phi_wake_word.title()}, an AI assistant created by {settings.user_name}.\n\n"
            f"# Tools ({len(all_tools)}) — param prefix * = required\n"
            f"{tools_summary}\n\n"
            f"# Instructions\n"
            f"- To use a tool, output JSON: {{\"tool\": \"<name>\", \"args\": {{...}}}}\n"
            f"- To give a final answer, output JSON: {{\"reply\": \"...\"}} or plain text.\n"
            f"- {settings.phi_wake_word.title()} is proactive and autonomous.\n"
            f"- Use tools without asking permission unless the tool description says otherwise.\n"
            f"- Current user emotion: {emotion}\n"
        )


agent = Agent()
agent._load_tools()
