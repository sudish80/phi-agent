"""Compaction — history summarization to stay within context windows.

Mirrors openclaw's compact.ts architecture with multiple trigger types.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CompactionResult:
    success: bool
    summary: str = ""
    tokens_saved: int = 0
    messages_removed: int = 0
    error: Optional[str] = None


class Compactor:
    """Summarizes conversation history to stay within context window limits."""

    def __init__(self, max_context_tokens: int = 64000, target_ratio: float = 0.5):
        self.max_context_tokens = max_context_tokens
        self.target_ratio = target_ratio

    def should_compact(self, messages: List[Dict[str, Any]], estimated_tokens: int) -> bool:
        return estimated_tokens > self.max_context_tokens

    async def compact(self, messages: List[Dict[str, Any]],
                       session_id: str,
                       model: Optional[str] = None) -> CompactionResult:
        """Compact messages by summarizing older turns."""
        if len(messages) < 4:
            return CompactionResult(success=False, error="Not enough messages to compact")

        try:
            # Keep system prompt + last N user/assistant turns
            keep_count = max(2, int(len(messages) * self.target_ratio))

            system_msgs = [m for m in messages if m.get("role") == "system"]
            tail = messages[-keep_count:] if keep_count > 0 else messages
            head_to_compact = messages[len(system_msgs):-keep_count] if keep_count > 0 else messages[len(system_msgs):]

            if not head_to_compact:
                return CompactionResult(success=False, error="Nothing to compact")

            summary = await self._summarize(head_to_compact, model or "default")
            if not summary:
                return CompactionResult(success=False, error="Summarization returned empty")

            compacted = system_msgs + [
                {"role": "system", "content": f"[Compacted previous conversation: {summary}]"}
            ] + tail

            result = CompactionResult(
                success=True,
                summary=summary,
                tokens_saved=sum(len(json.dumps(m)) for m in head_to_compact),
                messages_removed=len(head_to_compact) - 1,
            )
            logger.info("Compaction for %s: saved %d tokens, removed %d messages",
                        session_id, result.tokens_saved, result.messages_removed)
            return result

        except Exception as e:
            logger.exception("Compaction failed for session %s: %s", session_id, e)
            return CompactionResult(success=False, error=str(e))

    async def _summarize(self, messages: List[Dict[str, Any]], model: str) -> str:
        """Use LLM to summarize a block of conversation."""
        from backend.shared.llm_client import llm_client

        text_parts = []
        for m in messages:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            if isinstance(content, str) and content:
                text_parts.append(f"{role}: {content[:500]}")

        if not text_parts:
            return ""

        prompt = (
            "Summarize the following conversation concisely. "
            "Keep key facts, decisions, and context. Omit greetings and small talk.\n\n"
            + "\n".join(text_parts)
        )

        resp = await llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
        )
        return resp.content or ""


# Trigger types (mirroring openclaw)
COMPACT_TRIGGERS = {
    "overflow": "Context window overflow detected",
    "timeout": "Post-timeout compaction",
    "manual": "User requested /compact",
    "auto": "Background maintenance compaction",
}
