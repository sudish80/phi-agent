"""Git operations module for J.A.R.V.I.S.

Git status, commit, push, pull, log, and branch management.
"""

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


async def git_status(repo_path: str = ".") -> str:
    """Show git status of a repository."""
    return await _git_cmd(["status"], repo_path)


async def git_log(repo_path: str = ".", count: int = 10) -> str:
    """Show recent git commit log."""
    return await _git_cmd(
        ["log", f"--max-count={count}", "--oneline", "--decorate"], repo_path)


async def git_diff(repo_path: str = ".", staged: bool = False) -> str:
    """Show git diff (unstaged or staged)."""
    args = ["diff", "--cached"] if staged else ["diff"]
    return await _git_cmd(args, repo_path)


async def git_commit(repo_path: str = ".", message: str = "JARVIS auto-commit") -> str:
    """Stage all changes and commit."""
    result = await _git_cmd(["add", "-A"], repo_path)
    if "Error" in result:
        return result
    return await _git_cmd(["commit", "-m", message], repo_path)


async def git_push(repo_path: str = ".", remote: str = "origin",
                   branch: str = "") -> str:
    """Push to remote repository."""
    if branch:
        return await _git_cmd(["push", remote, branch], repo_path)
    return await _git_cmd(["push"], repo_path)


async def git_pull(repo_path: str = ".", remote: str = "origin",
                   branch: str = "") -> str:
    """Pull from remote repository."""
    if branch:
        return await _git_cmd(["pull", remote, branch], repo_path)
    return await _git_cmd(["pull"], repo_path)


async def git_branch(repo_path: str = ".") -> str:
    """List git branches."""
    return await _git_cmd(["branch", "-a"], repo_path)


async def _git_cmd(args: list, repo_path: str) -> str:
    loop = asyncio.get_event_loop()

    def _run():
        import subprocess
        full = os.path.abspath(os.path.expanduser(repo_path))
        if not os.path.exists(os.path.join(full, ".git")):
            return f"Not a git repository: {full}"
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True, text=True, timeout=30,
                cwd=full,
            )
            output = result.stdout or ""
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            return output.strip() or "(no output)"
        except FileNotFoundError:
            return "Git not found. Install git to use this feature."
        except subprocess.TimeoutExpired:
            return "Git command timed out."
        except Exception as e:
            return f"Git error: {e}"

    return await loop.run_in_executor(None, _run)
