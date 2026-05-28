#!/usr/bin/env python3
"""J.A.R.V.I.S. CLI Management Tool.

Usage:
  python scripts/cli.py --help
  python scripts/cli.py status
  python scripts/cli.py chat "Hello JARVIS"
  python scripts/cli.py memory query "what did I do yesterday"
  python scripts/cli.py memory store "Important fact" --room Technology
  python scripts/cli.py service orchestrator restart
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich import box

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.shared.config import settings

console = Console()
logger = logging.getLogger(__name__)

BASE_URL = f"http://localhost:{settings.orchestrator_port}"


# ============================================================
# Helpers
# ============================================================

async def api_get(path: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}{path}", timeout=10)
        resp.raise_for_status()
        return resp.json()


async def api_post(path: str, data: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}{path}", json=data or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()


# ============================================================
# Commands
# ============================================================

@click.group()
@click.version_option("1.0.0", prog_name="jarvis")
def cli():
    """J.A.R.V.I.S. Command Line Interface"""


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def status(json_output):
    """Show J.A.R.V.I.S. system status"""
    async def _run():
        try:
            result = await api_get("/health")
            if json_output:
                console.print_json(json.dumps(result))
                return

            table = Table(title="J.A.R.V.I.S. System Status", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Status", result.get("status", "unknown"))
            table.add_row("Uptime", f"{result.get('uptime_seconds', 0):.1f}s")
            table.add_row("Active Sessions", str(result.get("active_sessions", 0)))
            table.add_row("Memory", result.get("memory_status", "unknown"))
            table.add_row("Token Usage (Prompt)", str(
                result.get("token_usage", {}).get("total_prompt", 0)))
            table.add_row("Token Usage (Completion)", str(
                result.get("token_usage", {}).get("total_completion", 0)))

            console.print(table)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(_run())


@cli.command()
@click.argument("message")
@click.option("--session", default="cli-session", help="Session ID")
def chat(message: str, session: str):
    """Send a message to J.A.R.V.I.S."""
    async def _run():
        try:
            with console.status("[cyan]J.A.R.V.I.S. is thinking..."):
                result = await api_post("/chat", {
                    "message": message,
                    "session_id": session,
                })

            console.print()
            console.print(Panel(
                result.get("reply", ""),
                title="[bold cyan]J.A.R.V.I.S.[/bold cyan]",
                border_style="cyan",
                subtitle=f"[dim]emotion: {result.get('emotion', 'neutral')} | "
                         f"{result.get('processing_time_ms', 0):.0f}ms[/dim]",
            ))

            if result.get("actions_taken"):
                console.print("\n[dim]Actions taken:[/dim] " +
                              ", ".join(f"[green]{a}[/green]" for a in result["actions_taken"]))

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(_run())


@cli.group()
def memory():
    """Manage J.A.R.V.I.S. memory"""
    pass


@memory.command()
@click.argument("query")
@click.option("--n", "n_results", default=5, help="Number of results")
@click.option("--type", "mem_type", default=None, help="Memory type filter")
@click.option("--room", default=None, help="Memory palace room")
@click.option("--json", "json_output", is_flag=True)
def query(query: str, n_results: int, mem_type: Optional[str],
          room: Optional[str], json_output: bool):
    """Query J.A.R.V.I.S. memory"""
    memory_url = f"http://localhost:8001"  # Memory service

    async def _run():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{memory_url}/query", json={
                    "query": query,
                    "n_results": n_results,
                    "memory_type": mem_type,
                    "room_name": room,
                }, timeout=10)
                results = resp.json()

            if json_output:
                console.print_json(json.dumps(results))
                return

            if not results:
                console.print("[yellow]No memories found[/yellow]")
                return

            table = Table(title=f"Memory Results: '{query}'", box=box.SIMPLE)
            table.add_column("Type", style="cyan", width=12)
            table.add_column("Content", style="white")
            table.add_column("Score", style="green", justify="right", width=8)
            table.add_column("Room", style="blue", width=14)

            for r in results:
                if "adjacent_memories" in r:
                    continue
                table.add_row(
                    r.get("memory_type", "?"),
                    r.get("content", "")[:80] + ("..." if len(r.get("content", "")) > 80 else ""),
                    f"{r.get('score', 0):.2f}",
                    r.get("room_name", "-") or "-",
                )

            console.print(table)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(_run())


@memory.command()
@click.argument("content")
@click.option("--type", "mem_type", default="episodic",
              type=click.Choice(["episodic", "semantic", "procedural", "spatial"]))
@click.option("--importance", default="normal",
              type=click.Choice(["trivial", "low", "normal", "high", "critical"]))
@click.option("--room", default=None, help="Memory palace room name")
def store(content: str, mem_type: str, importance: str, room: Optional[str]):
    """Store something in J.A.R.V.I.S. memory"""
    memory_url = "http://localhost:8001"

    async def _run():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{memory_url}/store", json={
                    "content": content,
                    "memory_type": mem_type,
                    "importance": importance,
                    "room_name": room,
                }, timeout=10)
                result = resp.json()

            console.print(f"[green]Stored in memory:[/green] {result.get('id', '?')[:12]}...")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(_run())


@memory.command()
def palace():
    """Show the Memory Palace map"""
    memory_url = "http://localhost:8001"

    async def _run():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{memory_url}/palace", timeout=10)
                palace = resp.json()

            table = Table(title="Memory Palace", box=box.ROUNDED)
            table.add_column("Room", style="cyan", width=18)
            table.add_column("Topic", style="blue", width=16)
            table.add_column("Memories", style="green", justify="right", width=10)
            table.add_column("Adjacent", style="dim", width=30)

            for room_id, room in palace.items():
                adj = ", ".join(room.get("adjacent_rooms", [])[:3])
                table.add_row(
                    room.get("name", "?"),
                    room.get("topic", "?"),
                    str(room.get("memory_count", 0)),
                    adj,
                )

            console.print(table)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(_run())


@cli.group()
def service():
    """Manage J.A.R.V.I.S. services"""
    pass


@Service.command()
@click.argument("name", type=click.Choice(["orchestrator", "vision", "hearing",
                                           "speech", "action", "memory", "all"]))
@click.option("--command", type=click.Choice(["status", "restart"]), default="status")
def manage(name: str, command: str):
    """Get service status or restart"""
    ports = {
        "orchestrator": settings.orchestrator_port,
        "vision": settings.vision_port,
        "hearing": settings.hearing_port,
        "speech": settings.speech_port,
        "action": settings.action_port,
        "memory": 8001,
    }

    async def _run():
        services = [name] if name != "all" else list(ports.keys())
        table = Table(title="Service Status", box=box.SIMPLE)
        table.add_column("Service", style="cyan", width=16)
        table.add_column("Status", style="green", width=12)
        table.add_column("Port", justify="right", width=8)

        for svc in services:
            port = ports.get(svc, 0)
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"http://localhost:{port}/health", timeout=5
                    )
                    status = "OK" if resp.status_code == 200 else "ERROR"
            except Exception:
                status = "DOWN"

            table.add_row(svc, status, str(port))

        console.print(table)

    asyncio.run(_run())


@cli.command()
@click.argument("text")
@click.option("--emotion", default="neutral",
              type=click.Choice(["neutral", "happy", "serious", "excited",
                                 "calm", "angry", "sad", "whisper"]))
def speak(text: str, emotion: str):
    """Test TTS by synthesizing speech"""
    speech_url = f"http://localhost:{settings.speech_port}"

    async def _run():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{speech_url}/synthesize", json={
                    "text": text,
                    "emotion": emotion,
                }, timeout=30)
                result = resp.json()

            console.print(f"[green]TTS OK:[/green] {result.get('duration_ms', 0):.0f}ms, "
                          f"{len(result.get('audio', ''))} bytes audio")
            if result.get("visemes"):
                console.print(f"[dim]Visemes: {len(result['visemes'])} frames[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(_run())


@cli.command()
@click.option("--text", "list", is_flag=True, help="List recent conversations")
@click.option("--n", "limit", default=10, help="Number of items")
def recent(list: bool, limit: int):
    """Show recent conversation history"""
    memory_url = "http://localhost:8001"

    async def _run():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{memory_url}/recent?limit={limit}", timeout=10)
                items = resp.json()

            if not items:
                console.print("[yellow]No recent conversations[/yellow]")
                return

            table = Table(box=box.SIMPLE)
            table.add_column("Time", style="dim", width=20)
            table.add_column("Content", style="white")

            for item in items:
                from datetime import datetime
                ts = datetime.fromtimestamp(item.get("timestamp", 0))
                table.add_row(
                    ts.strftime("%H:%M:%S"),
                    item.get("content", "")[:100],
                )

            console.print(table)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(_run())


@cli.command()
def usage():
    """Show token usage statistics"""
    async def _run():
        try:
            result = await api_get("/health")
            tokens = result.get("token_usage", {})
            console.print(f"[cyan]Total Prompt Tokens:[/cyan] {tokens.get('total_prompt', 0)}")
            console.print(f"[cyan]Total Completion Tokens:[/cyan] {tokens.get('total_completion', 0)}")
            total = tokens.get('total_prompt', 0) + tokens.get('total_completion', 0)
            console.print(f"[green]Total: {total}[/green]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
