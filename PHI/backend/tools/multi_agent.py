"""Multi-Agent Orchestration — spawn specialized sub-agents for complex tasks.

Sub-agents have role-specific tool sets and work independently:
  - Researcher: web scraping, search, Wikipedia, news, jobs, social
  - Coder: code sandbox, git, development tools
  - Reviewer: monitoring, security, code analysis
  - Writer: communication, creative tools
  - Analyst: finance, data, monitoring
"""

import json
import time
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    WRITER = "writer"
    ANALYST = "analyst"


# Role definitions: system prompt prefix + tool categories allowed
ROLE_CONFIGS = {
    AgentRole.RESEARCHER: {
        "name": "Researcher",
        "description": "Searches the web, gathers information, and summarizes findings",
        "system_prompt_extra": "You are a research specialist. Your job is to find accurate, up-to-date information. Cite sources.",
        "tool_categories": ["web", "search", "utility"],
    },
    AgentRole.CODER: {
        "name": "Coder",
        "description": "Writes, analyzes, and debugs code",
        "system_prompt_extra": "You are a software engineer. Write clean, well-structured code. Explain your approach.",
        "tool_categories": ["development", "system", "utility"],
    },
    AgentRole.REVIEWER: {
        "name": "Reviewer",
        "description": "Reviews code, checks security, monitors systems",
        "system_prompt_extra": "You are a code reviewer and security auditor. Identify bugs, vulnerabilities, and improvements.",
        "tool_categories": ["development", "security", "monitoring"],
    },
    AgentRole.WRITER: {
        "name": "Writer",
        "description": "Drafts emails, documents, creative content",
        "system_prompt_extra": "You are a skilled writer. Adapt tone to the audience, be clear and persuasive.",
        "tool_categories": ["communication", "creative", "utility"],
    },
    AgentRole.ANALYST: {
        "name": "Analyst",
        "description": "Analyzes data, financials, trends, and metrics",
        "system_prompt_extra": "You are a data analyst. Use data to derive insights, spot trends, and make recommendations.",
        "tool_categories": ["finance", "monitoring", "web", "utility"],
    },
}


@dataclass
class SubAgent:
    agent_id: str
    role: AgentRole
    task: str
    status: str  # running, completed, failed, cancelled
    result: str = ""
    error: str = ""
    created_at: float = 0.0
    completed_at: float = 0.0
    tool_calls: int = 0
    parent_session: str = ""


# Active sub-agents
_sub_agents: Dict[str, SubAgent] = {}
_sub_agents_lock = asyncio.Lock()

# Maximum concurrent sub-agents
_MAX_CONCURRENT = 10


async def spawn_agent(role: str, task: str, context: str = "",
                      parent_session: str = "default") -> str:
    """Spawn a sub-agent with a specific role to work on a task.

    Args:
        role: One of: researcher, coder, reviewer, writer, analyst
        task: The task description for the sub-agent
        context: Optional context from the main conversation
        parent_session: Session ID of the parent agent

    Returns:
        JSON with agent_id and status
    """
    try:
        role_enum = AgentRole(role.lower())
    except ValueError:
        valid = [r.value for r in AgentRole]
        return json.dumps({"error": f"Invalid role '{role}'. Valid: {valid}"})

    async with _sub_agents_lock:
        active = sum(1 for a in _sub_agents.values() if a.status == "running")
        if active >= _MAX_CONCURRENT:
            return json.dumps({"error": f"Maximum {_MAX_CONCURRENT} concurrent agents reached"})

        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        agent = SubAgent(
            agent_id=agent_id,
            role=role_enum,
            task=task,
            status="running",
            created_at=time.time(),
            parent_session=parent_session,
        )
        _sub_agents[agent_id] = agent

    # Launch in background
    asyncio.create_task(_run_agent(agent_id, task, context))

    return json.dumps({
        "status": "spawned",
        "agent_id": agent_id,
        "role": role,
        "task": task[:200],
        "active_agents": active + 1,
    })


async def _run_agent(agent_id: str, task: str, context: str):
    """Background task that runs a sub-agent."""
    logger.info(f"Sub-agent {agent_id} starting: {task[:100]}")

    agent = _sub_agents.get(agent_id)
    if not agent:
        return

    try:
        # Build system prompt for this agent
        config = ROLE_CONFIGS.get(agent.role, {})
        prompt_extra = config.get("system_prompt_extra", "")
        allowed_cats = config.get("tool_categories", [])

        # Filter tools by role
        from backend.orchestrator.agent import agent as main_agent
        all_tools = list(main_agent.tools._tools.values())
        role_tools = [t for t in all_tools if t.category in allowed_cats or not t.category]
        role_tools_names = [t.name for t in role_tools]

        # Build system prompt
        sys_prompt = f"""You are a {config.get('name', agent.role.value)} sub-agent.
{prompt_extra}

YOUR TASK:
{task}

CONTEXT:
{context[:2000] if context else 'No additional context.'}

TOOLS AVAILABLE:
{', '.join(role_tools_names) if role_tools_names else 'No specialized tools for this role.'}

Respond with your findings. Use tools as needed."""
        from backend.shared.llm_client import llm_client

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": task},
        ]

        result = await llm_client.generate(messages)
        if isinstance(result, dict):
            agent.result = result.get("text", "")

            # Count tool calls if present in response
            tool_calls_count = 0
            if "tool_calls" in result:
                try:
                    tool_calls_count = len(result["tool_calls"])
                except Exception:
                    tool_calls_count = 0
            agent.tool_calls = tool_calls_count
        else:
            agent.result = str(result)
            agent.tool_calls = 0
        agent.status = "completed"

    except Exception as e:
        logger.error(f"Sub-agent {agent_id} failed: {e}")
        agent.status = "failed"
        agent.error = str(e)

    finally:
        agent.completed_at = time.time()
        logger.info(f"Sub-agent {agent_id} finished: status={agent.status}")


async def list_agents(status: str = "", parent_session: str = "") -> str:
    """List all spawned sub-agents, optionally filtered by status or session."""
    agents = []
    async with _sub_agents_lock:
        for a in _sub_agents.values():
            if status and a.status != status:
                continue
            if parent_session and a.parent_session != parent_session:
                continue
            agents.append({
                "agent_id": a.agent_id,
                "role": a.role.value,
                "task": a.task[:100],
                "status": a.status,
                "created_at": datetime.fromtimestamp(a.created_at, tz=timezone.utc).isoformat() if a.created_at else "",
                "completed_at": datetime.fromtimestamp(a.completed_at, tz=timezone.utc).isoformat() if a.completed_at else "",
                "duration_ms": round((a.completed_at - a.created_at) * 1000) if a.completed_at and a.created_at else 0,
                "tool_calls": a.tool_calls,
                "error": a.error,
                "parent_session": a.parent_session,
            })

    return json.dumps({
        "agents": agents,
        "count": len(agents),
        "running": sum(1 for a in _sub_agents.values() if a.status == "running"),
    }, indent=2)


async def get_agent_result(agent_id: str) -> str:
    """Get the result of a completed sub-agent."""
    async with _sub_agents_lock:
        agent = _sub_agents.get(agent_id)

    if not agent:
        return json.dumps({"error": f"Agent '{agent_id}' not found"})

    return json.dumps({
        "agent_id": agent.agent_id,
        "role": agent.role.value,
        "task": agent.task,
        "status": agent.status,
        "result": agent.result[:5000] if agent.result else "",
        "error": agent.error,
        "created_at": datetime.fromtimestamp(agent.created_at, tz=timezone.utc).isoformat() if agent.created_at else "",
        "completed_at": datetime.fromtimestamp(agent.completed_at, tz=timezone.utc).isoformat() if agent.completed_at else "",
        "duration_ms": round((agent.completed_at - agent.created_at) * 1000) if agent.completed_at and agent.created_at else 0,
        "tool_calls": agent.tool_calls,
    }, indent=2)


async def cancel_agent(agent_id: str) -> str:
    """Cancel a running sub-agent."""
    async with _sub_agents_lock:
        agent = _sub_agents.get(agent_id)

    if not agent:
        return json.dumps({"error": f"Agent '{agent_id}' not found"})

    if agent.status != "running":
        return json.dumps({"error": f"Agent '{agent_id}' is not running (status: {agent.status})"})

    agent.status = "cancelled"
    agent.completed_at = time.time()
    return json.dumps({"status": "cancelled", "agent_id": agent_id})


async def multi_agent_collaborate(primary_role: str, supporting_roles: str,
                                   task: str, context: str = "",
                                   parent_session: str = "default") -> str:
    """Spawn multiple agents with different roles to collaborate on a complex task.

    Args:
        primary_role: The main agent role (researcher, coder, reviewer, writer, analyst)
        supporting_roles: Comma-separated list of supporting roles
        task: The overall task description
        context: Optional context
        parent_session: Session ID

    Returns:
        JSON with all agent results
    """
    roles = [primary_role.strip().lower()]
    for r in supporting_roles.split(","):
        r = r.strip().lower()
        if r and r not in roles:
            roles.append(r)

    # Spawn all agents in parallel
    spawn_tasks = []
    for role in roles:
        spawn_tasks.append(spawn_agent(role, task, context, parent_session))

    spawn_results = await asyncio.gather(*spawn_tasks)

    # Extract agent IDs
    agent_ids = []
    for sr in spawn_results:
        data = json.loads(sr)
        if "agent_id" in data:
            agent_ids.append(data["agent_id"])

    if not agent_ids:
        return json.dumps({"error": "Failed to spawn any agents", "results": spawn_results})

    # Wait for all agents to complete (with timeout)
    async def wait_for_agent(aid: str, timeout: float = 120.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            async with _sub_agents_lock:
                agent = _sub_agents.get(aid)
                if agent and agent.status in ("completed", "failed", "cancelled"):
                    return agent
            await asyncio.sleep(1)
        # Timeout - cancel the agent
        await cancel_agent(aid)
        async with _sub_agents_lock:
            return _sub_agents.get(aid)

    agents = await asyncio.gather(*[wait_for_agent(aid) for aid in agent_ids])

    # Compile results
    results = []
    for agent in agents:
        if agent is None:
            continue
        results.append({
            "role": agent.role.value,
            "agent_id": agent.agent_id,
            "status": agent.status,
            "result_preview": agent.result[:1000] if agent.result else "",
            "error": agent.error,
            "duration_ms": round((agent.completed_at - agent.created_at) * 1000) if agent.completed_at and agent.created_at else 0,
        })

    # Synthesize final summary
    summary_parts = [f"Multi-agent collaboration on: {task[:200]}"]
    for r in results:
        status_icon = "✅" if r["status"] == "completed" else "❌" if r["status"] == "failed" else "⏹️"
        summary_parts.append(f"\n{status_icon} {r['role'].title()} ({r['agent_id']}): {r['status']} in {r['duration_ms']}ms")
        if r["result_preview"]:
            summary_parts.append(f"   {r['result_preview'][:200]}...")

    return json.dumps({
        "task": task,
        "primary_role": primary_role,
        "supporting_roles": supporting_roles,
        "agents": results,
        "total_agents": len(results),
        "completed": sum(1 for r in results if r["status"] == "completed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "summary": "\n".join(summary_parts),
    }, indent=2)


def cleanup_old_agents(max_age_hours: float = 24):
    """Remove agents older than max_age_hours from memory."""
    cutoff = time.time() - (max_age_hours * 3600)
    global _sub_agents
    to_remove = [aid for aid, agent in list(_sub_agents.items())
                 if agent.completed_at and agent.completed_at < cutoff]
    for aid in to_remove:
        _sub_agents.pop(aid, None)
