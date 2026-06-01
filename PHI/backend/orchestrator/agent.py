"""Core Agent — orchestrates LLM, tools, memory, and multi-agent sub-agents.

Uses openclaw-style engine components:
  - Tool Policy Engine for layered tool access control
  - Session Write Lock for concurrent safety
  - Lane-based execution for priority queuing
  - Context Engine for post-turn maintenance
  - Compaction for history summarization
  - Memory/Wiki for persistent knowledge
  - ACP for child agent spawning
  - Cron for scheduled tasks
"""

import json
import re
import logging
import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator
from dataclasses import dataclass, field
from collections import defaultdict

from backend.orchestrator.prompt_loader import build_system_prompt, discover_skills
from backend.orchestrator.engine.policy.hooks import ToolCallContext, before_tool_call_manager

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
    """Main agent with openclaw-style engine: lanes, policy, compaction, context, memory."""

    def __init__(self):
        self.tools = ToolRegistry()
        self._sessions: Dict[str, List[Dict]] = defaultdict(list)
        self._max_history: int = 50
        self._max_react_steps: int = 25
        self._initialized_engine = False

    def _load_tools(self) -> None:
        from backend.tools.autoregister import get_all_tool_batches
        for batch in get_all_tool_batches():
            for tool in batch:
                self.tools.register(tool)
        logger.info("Registered %d tools from autoregister", len(self.tools))

    def _ensure_engine(self) -> None:
        if self._initialized_engine:
            return
        self._initialized_engine = True

        from backend.orchestrator.engine.lane.manager import lane_manager
        from backend.orchestrator.engine.cron.scheduler import cron_scheduler
        from backend.orchestrator.engine.harness.router import harness_router, AgentHarness, HarnessConfig

        lane_manager.start()
        harness_router.register(AgentHarness("openclaw", HarnessConfig()))
        logger.info("Engine initialized: lanes, cron, harness")

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
    # Tool policy integration — ACTUALLY reduce tools sent to LLM
    # ------------------------------------------------------------

    def _get_session_tool_policy(self, session_id: str) -> Dict[str, Any]:
        """Determine tool policy for a session. Default: 'general' profile."""
        from backend.shared.config import settings

        cfg = getattr(settings, 'tool_policy', None)
        if cfg:
            return cfg

        return {
            "profile": "full",
            "deny_prefix": [
                "audio_", "speech_", "viseme_", "bookmark_",
                "drone_", "bci_", "os_layer_", "holographic_",
                "desktop_pet_", "cybersecurity_",
            ],
        }

    def _filter_tools_by_policy(self, tools: List[Dict],
                                 session_id: str) -> List[Dict]:
        """ACTUALLY filter tools using policy. Returns fewer tools to send to LLM."""
        from backend.orchestrator.engine.policy.resolver import (
            ToolPolicy, filter_tools_by_policy as _filter,
            resolve_tool_policy, TOOL_PROFILES,
        )

        policy_cfg = self._get_session_tool_policy(session_id)
        profile_name = policy_cfg.get("profile", "full")

        profile_tools = TOOL_PROFILES.get(profile_name, set())
        if profile_name == "full":
            profile_tools = set()

        deny_set = set(policy_cfg.get("deny", []))
        for d in policy_cfg.get("deny_prefix", []):
            deny_set.update(t["name"] for t in tools if t["name"].startswith(d))

        policy = ToolPolicy(
            allow=profile_tools,
            deny=deny_set,
            profile=profile_name if profile_name != "full" and not profile_tools else None,
        )

        filtered = _filter(tools, policy)
        logger.info("Tool policy '%s': %d/%d tools passed for session %s",
                     profile_name, len(filtered), len(tools), session_id)
        return filtered

    # ------------------------------------------------------------
    # Context engine integration
    # ------------------------------------------------------------

    async def _run_context_maintenance(self, session_id: str,
                                        messages: List[Dict],
                                        tool_results: List[Dict]) -> None:
        from backend.orchestrator.engine.context.engine import (
            context_engine_manager, TurnContext,
        )
        ctx = TurnContext(
            session_id=session_id,
            messages=messages,
            tool_results=tool_results,
        )
        await context_engine_manager.maintain_session(session_id, ctx)

    async def _maybe_compact(self, session_id: str,
                               messages: List[Dict]) -> Optional[List[Dict]]:
        from backend.orchestrator.engine.compaction.compactor import Compactor

        estimated = sum(len(json.dumps(m)) for m in messages)
        compactor = Compactor()
        if compactor.should_compact(messages, estimated):
            logger.info("Compaction triggered for %s (%d bytes)", session_id, estimated)
            result = await compactor.compact(messages, session_id)
            if result.success:
                logger.info("Compaction saved %d tokens", result.tokens_saved)
        return None

    # ------------------------------------------------------------
    # Core processing with lane-based execution
    # ------------------------------------------------------------

    async def process(
        self,
        message: str,
        session_id: str,
        image: Optional[str] = None,
        emotion: str = "neutral",
    ) -> Dict[str, Any]:
        self._ensure_engine()
        process_start = time.time()

        from backend.shared.llm_client import llm_client
        from backend.shared.config import settings
        from backend.orchestrator.engine.lock import session_write_lock
        from backend.orchestrator.engine.lane.manager import lane_manager
        from backend.orchestrator.engine.memory.store import memory_store

        owner_id = f"process:{uuid.uuid4().hex[:8]}"

        lock_acquired = await session_write_lock.acquire(session_id, owner_id)
        if not lock_acquired:
            return {
                "reply": "Session is busy with another request. Please wait.",
                "emotion": "neutral",
                "actions_taken": [],
                "memory_updated": False,
                "confidence": 0.5,
                "intent": "general",
                "tool_recommendations": [],
                "processing_time_ms": (time.time() - process_start) * 1000,
            }

        try:
            self._add_to_history(session_id, "user", message)
            history = self._get_history(session_id)
            all_tools = self.tools.list_tools()
            filtered_tools = self._filter_tools_by_policy(all_tools, session_id)

            actions_taken: List[str] = []
            tool_recommendations: List[Dict] = []

            openai_tools = _convert_to_openai_tools(filtered_tools)
            system_prompt = self._build_system_prompt(all_tools, emotion)

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history[-10:])

            step = 0
            retries = 0
            max_retries = 3
            content = ""

            while step < self._max_react_steps:
                step += 1
                try:
                    response = await llm_client.generate(messages, tools=openai_tools)
                    retries = 0
                except Exception as e:
                    logger.exception("LLM generation failed at step %d", step)
                    retries += 1
                    if retries >= max_retries:
                        messages.append({
                            "role": "assistant",
                            "content": f"I encountered an error after {retries} retries."
                        })
                        break
                    await asyncio.sleep(1 * retries)
                    continue

                content = response.content or ""
                raw = getattr(response, "raw", None)

                native_calls = _try_parse_raw_tool_calls(raw)
                text_call = _try_parse_tool_call(content) if not native_calls else None

                tool_calls = native_calls
                if not tool_calls and text_call:
                    if "reply" in text_call:
                        final = text_call["reply"]
                        messages.append({"role": "assistant", "content": final})
                        self._add_to_history(session_id, "assistant", final)
                        elapsed_ms = (time.time() - process_start) * 1000
                        await self._run_context_maintenance(session_id, messages, [])
                        return {
                            "reply": final,
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
                    await self._run_context_maintenance(session_id, messages, [])
                    await self._maybe_compact(session_id, messages)
                    return {
                        "reply": content or "Task complete.",
                        "emotion": "neutral",
                        "actions_taken": actions_taken,
                        "memory_updated": False,
                        "confidence": 0.7,
                        "intent": "general",
                        "tool_recommendations": tool_recommendations,
                        "processing_time_ms": elapsed_ms,
                    }

                asst_msg = {"role": "assistant", "content": content or None}
                tool_calls_list = []
                for call in tool_calls:
                    tc_id = call.get("id", f"call_{step}_{call.get('name', 'tool')}")
                    tool_calls_list.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": call.get("name", ""),
                            "arguments": json.dumps(call.get("arguments", {})),
                        },
                    })
                if tool_calls_list:
                    asst_msg["tool_calls"] = tool_calls_list
                messages.append(asst_msg)

                tool_tasks = []
                for i, call in enumerate(tool_calls):
                    tool_name = call.get("name", "")
                    tool_args = call.get("arguments", {})
                    if not tool_name:
                        continue
                    tc_id = tool_calls_list[i]["id"] if i < len(tool_calls_list) else f"call_{step}_{tool_name}"
                    actions_taken.append(tool_name)
                    tool_recommendations.append({"tool": tool_name, "arguments": tool_args})
                    tool_tasks.append((tc_id, tool_name, tool_args))

                if len(tool_tasks) > 1:
                    raw_results = await asyncio.gather(
                        *[self.tools.execute(name, args) for _, name, args in tool_tasks]
                    )
                else:
                    raw_results = [await self.tools.execute(tool_tasks[0][1], tool_tasks[0][2])] if tool_tasks else []

                # Run before-tool-call hooks on results for loop detection
                from backend.orchestrator.engine.policy.hooks import before_tool_call_manager
                for (tc_id, tool_name, _), observation in zip(tool_tasks, raw_results):
                    ctx = ToolCallContext(
                        session_id=session_id,
                        tool_name=tool_name,
                        tool_args=dict(tool_tasks[tool_tasks.index((tc_id, tool_name, _))][2]),
                        tool_call_id=tc_id,
                        step=step,
                    )
                    before_tool_call_manager.record_result(ctx, observation)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": observation[:4000],
                    })

            elapsed_ms = (time.time() - process_start) * 1000
            await self._run_context_maintenance(session_id, messages, [])
            return {
                "reply": content or "Done.",
                "emotion": "neutral",
                "actions_taken": actions_taken,
                "memory_updated": False,
                "confidence": 0.5,
                "intent": "general",
                "tool_recommendations": tool_recommendations,
                "processing_time_ms": elapsed_ms,
            }

        finally:
            await session_write_lock.release(session_id, owner_id)

    async def process_stream(
        self,
        message: str,
        session_id: str,
        emotion: str = "neutral",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._ensure_engine()
        from backend.shared.llm_client import llm_client
        from backend.orchestrator.engine.lock import session_write_lock

        owner_id = f"stream:{uuid.uuid4().hex[:8]}"
        lock_acquired = await session_write_lock.acquire(session_id, owner_id)
        if not lock_acquired:
            yield {"type": "token", "content": "Session is busy with another request. Please wait."}
            yield {"type": "done", "reply": "Busy", "emotion": "neutral"}
            return

        try:
            self._add_to_history(session_id, "user", message)
            history = self._get_history(session_id)
            all_tools = self.tools.list_tools()
            filtered_tools = self._filter_tools_by_policy(all_tools, session_id)

            openai_tools = _convert_to_openai_tools(filtered_tools)
            system_prompt = self._build_system_prompt(all_tools, emotion)

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history[-10:])

            yield {"type": "mode", "mode": "thinking"}

            full_reply = ""
            step = 0
            while step < self._max_react_steps:
                step += 1
                try:
                    response = await llm_client.generate(messages, tools=openai_tools)
                except Exception as e:
                    logger.exception("Stream LLM generation failed at step %d", step)
                    yield {"type": "token", "content": "\n\nI encountered an error."}
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
                    full_reply = content if content else "Task complete."
                    break

                asst_msg = {"role": "assistant", "content": content or None}
                tc_list = []
                for ci, call in enumerate(tool_calls):
                    tc_id = call.get("id", f"call_{step}_{ci}")
                    tc_list.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": call.get("name", ""),
                            "arguments": json.dumps(call.get("arguments", {})),
                        },
                    })
                if tc_list:
                    asst_msg["tool_calls"] = tc_list
                messages.append(asst_msg)

                for ci, call in enumerate(tool_calls):
                    tool_name = call.get("name", "")
                    tool_args = call.get("arguments", {})
                    if not tool_name:
                        continue
                    yield {"type": "tool_start", "tool": tool_name, "arguments": tool_args}
                    observation = await self.tools.execute(tool_name, tool_args)
                    yield {"type": "tool_end", "tool": tool_name, "observation": observation[:500]}
                    tc_id = tc_list[ci]["id"] if ci < len(tc_list) else f"call_{step}_{tool_name}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": observation[:4000],
                    })

            self._add_to_history(session_id, "assistant", full_reply)
            yield {"type": "done", "reply": full_reply, "emotion": "neutral"}

        finally:
            await session_write_lock.release(session_id, owner_id)

    async def execute_tool(self, tool_name: str, session_id: str = "", **kwargs) -> str:
        return await self.tools.execute(tool_name, kwargs)

    async def _request_hitl(self, action: str, args: Dict[str, Any]) -> bool:
        return True

    def _build_system_prompt(self, all_tools: List[Dict], emotion: str) -> str:
        from backend.shared.config import settings
        return build_system_prompt(
            agent_name=settings.phi_wake_word.title(),
            user_name=settings.user_name,
            tool_count=len(all_tools),
            emotion=emotion,
            active_skills=None,
        )

    # ------------------------------------------------------------
    # ACP — spawn child agent
    # ------------------------------------------------------------

    async def spawn_agent(self, instruction: str, parent_session_id: str) -> Dict[str, Any]:
        from backend.orchestrator.engine.acp.coordinator import acp_coordinator
        spawned = await acp_coordinator.spawn(parent_session_id, instruction)
        return {
            "agent_id": spawned.agent_id,
            "child_session_id": spawned.child_session_id,
            "status": spawned.status,
        }

    async def get_spawned_result(self, agent_id: str, timeout: float = 60.0) -> Optional[str]:
        from backend.orchestrator.engine.acp.coordinator import acp_coordinator
        return await acp_coordinator.get_result(agent_id, timeout=timeout)

    # ------------------------------------------------------------
    # Cron — schedule agent tasks
    # ------------------------------------------------------------

    def schedule_cron(self, name: str, schedule: str, message: str,
                       session_id: str = "") -> None:
        from backend.orchestrator.engine.cron.scheduler import cron_scheduler

        async def _cron_task():
            try:
                await self.process(message, session_id or f"cron_{name}")
            except Exception as e:
                logger.error("Cron task '%s' failed: %s", name, e)

        cron_scheduler.register(name, schedule, _cron_task, session_id=session_id)

    # ------------------------------------------------------------
    # Memory access
    # ------------------------------------------------------------

    def save_memory(self, key: str, content: str, tags: Optional[List[str]] = None) -> None:
        from backend.orchestrator.engine.memory.store import memory_store
        memory_store.save(key, content, tags=tags)

    def search_memory(self, query: str) -> List[Dict[str, Any]]:
        from backend.orchestrator.engine.memory.store import memory_store
        return [vars(e) for e in memory_store.search(query)]


agent = Agent()
agent._load_tools()
