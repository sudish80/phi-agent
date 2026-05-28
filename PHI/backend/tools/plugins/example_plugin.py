"""Example J.A.R.V.I.S. Plugin — Demonstrates the plugin API."""

import json
import random
from datetime import datetime

plugin_metadata = {
    "name": "Example Plugin",
    "version": "1.0.0",
    "author": "Plugin Developer",
    "description": "Demonstrates how to create plugins for J.A.R.V.I.S.",
}


async def reverse_text(text: str) -> str:
    """Reverse any text string."""
    return json.dumps({"original": text, "reversed": text[::-1]})


async def random_number(min_val: int = 1, max_val: int = 100) -> str:
    """Generate a random number between min and max."""
    num = random.randint(min_val, max_val)
    return json.dumps({"number": num, "range": f"{min_val}-{max_val}"})


async def current_timestamp() -> str:
    """Get the current timestamp in multiple formats."""
    now = datetime.now()
    return json.dumps({
        "iso": now.isoformat(),
        "unix": now.timestamp(),
        "readable": now.strftime("%A, %B %d, %Y at %I:%M %p"),
    })


async def text_stats(text: str) -> str:
    """Get statistics about a text (word count, char count, sentence count)."""
    words = text.split()
    sentences = [s for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    return json.dumps({
        "word_count": len(words),
        "char_count": len(text),
        "sentence_count": len(sentences),
        "avg_word_length": round(sum(len(w) for w in words) / max(len(words), 1), 2),
    })


def get_tools():
    """Return list of (name, description, parameters, handler, category) tuples."""
    return [
        ("plugin_reverse_text", "Reverse any text string", {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to reverse"}},
            "required": ["text"],
        }, reverse_text, "utility"),
        ("plugin_random_number", "Generate a random number between min and max", {
            "type": "object",
            "properties": {
                "min_val": {"type": "integer", "description": "Minimum value (default 1)"},
                "max_val": {"type": "integer", "description": "Maximum value (default 100)"},
            },
            "required": [],
        }, random_number, "fun"),
        ("plugin_current_timestamp", "Get the current timestamp in multiple formats", {
            "type": "object", "properties": {}, "required": [],
        }, current_timestamp, "utility"),
        ("plugin_text_stats", "Get word/character/sentence statistics for a text", {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to analyze"}},
            "required": ["text"],
        }, text_stats, "utility"),
    ]
