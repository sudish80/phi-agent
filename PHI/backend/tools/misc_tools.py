"""Misc tools — random, color, math, yes/no query."""

import random
import secrets
import logging

logger = logging.getLogger(__name__)


def random_number(min_val: float = 0, max_val: float = 100, integer: bool = True) -> str:
    if min_val >= max_val:
        return "Error: min must be less than max"
    if integer:
        return str(random.randint(int(min_val), int(max_val)))
    return f"{random.uniform(min_val, max_val):.4f}"


def random_choice(options: list, count: int = 1) -> str:
    if not options:
        return "Error: no options provided"
    if count > len(options):
        count = len(options)
    chosen = random.sample(options, count) if count > 1 else [random.choice(options)]
    return ", ".join(str(c) for c in chosen)


def color_convert(color: str, from_format: str = "hex", to_format: str = "rgb") -> str:
    try:
        if from_format == "hex" and to_format == "rgb":
            c = color.lstrip("#")
            r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            return f"rgb({r}, {g}, {b})"
        elif from_format == "rgb" and to_format == "hex":
            parts = color.strip("rgb() ").split(",")
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            return f"#{r:02x}{g:02x}{b:02x}"
        elif from_format == "hex" and to_format == "hsl":
            c = color.lstrip("#")
            r, g, b = tuple(int(c[i:i+2], 16) / 255.0 for i in (0, 2, 4))
            mx, mn = max(r, g, b), min(r, g, b)
            l = (mx + mn) / 2
            if mx == mn: return "hsl(0, 0%, {:.0f}%)".format(l * 100)
            s = (mx - mn) / (1 - abs(2 * l - 1)) if l > 0 else 0
            if mx == r: h = 60 * (((g - b) / (mx - mn)) % 6)
            elif mx == g: h = 60 * (((b - r) / (mx - mn)) + 2)
            else: h = 60 * (((r - g) / (mx - mn)) + 4)
            return f"hsl({h:.0f}, {s*100:.0f}%, {l*100:.0f}%)"
        else:
            return f"Error: unsupported conversion from {from_format} to {to_format}"
    except Exception as e:
        return f"Color error: {e}"


def math_calculate(expression: str) -> str:
    allowed = set("0123456789+-*/.()% ")
    if not all(c in allowed for c in expression):
        return "Error: expression contains disallowed characters"
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except ZeroDivisionError:
        return "Error: division by zero"
    except Exception as e:
        return f"Math error: {e}"


def query_yesno(question: str) -> str:
    answers = ["Yes", "No", "Maybe", "Ask again later", "Definitely", "Absolutely not", "I wouldn't count on it", "Signs point to yes"]
    return f"Q: {question}\nA: {secrets.choice(answers)}"
