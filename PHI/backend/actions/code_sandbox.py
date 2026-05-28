"""Code sandbox for J.A.R.V.I.S.

Safely executes Python and JavaScript code in isolated subprocesses.
"""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import uuid

logger = logging.getLogger(__name__)

TIMEOUT = 30
MAX_OUTPUT = 10000


async def run_python(code: str, timeout: int = TIMEOUT) -> str:
    """Execute Python code in an isolated subprocess and return output."""
    if len(code) > 50000:
        return "Code too long (max 50000 chars)"

    loop = asyncio.get_event_loop()

    def _run():
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("import sys, json, math, random, datetime, os, re, collections, itertools, statistics\n\n")
            f.write("try:\n")
            for line in code.split("\n"):
                f.write(f"    {line}\n")
            f.write("except Exception as e:\n")
            f.write("    print('Error:', str(e), file=sys.stderr)\n")
            fpath = f.name

        try:
            result = subprocess.run(
                [sys.executable, fpath],
                capture_output=True, text=True,
                timeout=timeout,
            )
            output = result.stdout or ""
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if not output.strip():
                output = "(no output)"
            if len(output) > MAX_OUTPUT:
                output = output[:MAX_OUTPUT] + "\n... [truncated]"
            return output
        except subprocess.TimeoutExpired:
            return f"Execution timed out after {timeout}s"
        except Exception as e:
            return f"Execution error: {e}"
        finally:
            try:
                os.unlink(fpath)
            except PermissionError:
                pass

    return await loop.run_in_executor(None, _run)


async def run_javascript(code: str, timeout: int = TIMEOUT) -> str:
    """Execute JavaScript code using Node.js in an isolated subprocess."""
    if len(code) > 50000:
        return "Code too long (max 50000 chars)"

    loop = asyncio.get_event_loop()

    def _run():
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(code)
            fpath = f.name

        try:
            result = subprocess.run(
                ["node", fpath],
                capture_output=True, text=True,
                timeout=timeout,
                env={},
            )
            output = result.stdout or ""
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if not output.strip():
                output = "(no output)"
            if len(output) > MAX_OUTPUT:
                output = output[:MAX_OUTPUT] + "\n... [truncated]"
            return output
        except FileNotFoundError:
            return "Node.js not found. Install Node.js to run JavaScript."
        except subprocess.TimeoutExpired:
            return f"Execution timed out after {timeout}s"
        except Exception as e:
            return f"Execution error: {e}"
        finally:
            try:
                os.unlink(fpath)
            except PermissionError:
                pass

    return await loop.run_in_executor(None, _run)
