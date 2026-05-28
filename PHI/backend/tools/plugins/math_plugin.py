"""Second test plugin — for hot-reload testing."""

import json
import random

plugin_metadata = {
    "name": "Math Tools",
    "version": "2.0.0",
    "author": "J.A.R.V.I.S. Team",
    "description": "Mathematical utility functions.",
}


async def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        return json.dumps({"error": "Expression contains disallowed characters"})
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return json.dumps({"expression": expression, "result": result})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def roll_dice(sides: int = 6, count: int = 1) -> str:
    """Roll dice and return results."""
    results = [random.randint(1, sides) for _ in range(count)]
    return json.dumps({
        "dice": f"{count}d{sides}",
        "results": results,
        "total": sum(results),
    })


def get_tools():
    return [
        ("plugin_calculate", "Evaluate a mathematical expression safely", {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "Math expression"}},
            "required": ["expression"],
        }, calculate, "utility"),
        ("plugin_roll_dice", "Roll dice with specified sides and count", {
            "type": "object",
            "properties": {
                "sides": {"type": "integer", "description": "Number of sides per die"},
                "count": {"type": "integer", "description": "Number of dice to roll"},
            },
            "required": [],
        }, roll_dice, "fun"),
    ]
