"""Code tools — Python execution sandbox and template rendering."""

import sys
import io
import logging
import textwrap

logger = logging.getLogger(__name__)

try:
    from jinja2 import Environment, BaseLoader, TemplateNotFound
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False


def run_python(code: str, timeout: int = 5) -> str:
    safe_builtins = {
        "abs": abs, "all": all, "any": any, "bool": bool, "chr": chr,
        "dict": dict, "dir": dir, "enumerate": enumerate, "filter": filter,
        "float": float, "format": format, "frozenset": frozenset, "int": int,
        "isinstance": isinstance, "issubclass": issubclass, "iter": iter,
        "len": len, "list": list, "map": map, "max": max, "min": min,
        "next": next, "object": object, "ord": ord, "pow": pow,
        "range": range, "repr": repr, "reversed": reversed, "round": round,
        "set": set, "slice": slice, "sorted": sorted, "str": str,
        "sum": sum, "tuple": tuple, "type": type, "zip": zip,
        "True": True, "False": False, "None": None,
        "print": lambda *a, **kw: None, "__import__": __import__,
    }
    restricted = {"os", "sys", "subprocess", "shutil", "pathlib", "ctypes", "socket", "requests", "urllib"}
    try:
        for mod_name in restricted:
            if mod_name in code or f"import {mod_name}" in code:
                return f"Error: '{mod_name}' is not allowed for security reasons"
        local_scope = {}
        exec(textwrap.dedent(code), {"__builtins__": safe_builtins}, local_scope)
        results = {k: v for k, v in local_scope.items() if not k.startswith("_")}
        return "\n".join(f"{k} = {v!r}" for k, v in results.items()) if results else "Code executed (no output)"
    except SyntaxError as e:
        return f"Syntax error: {e}"
    except Exception as e:
        return f"Execution error: {e}"


def render_template(template_text: str, data_json: str) -> str:
    if not HAS_JINJA:
        return "Error: jinja2 not installed. Run: pip install jinja2"
    try:
        import json
        data = json.loads(data_json) if isinstance(data_json, str) else data_json
        env = Environment(loader=BaseLoader(), autoescape=False)
        template = env.from_string(template_text)
        return template.render(data)
    except json.JSONDecodeError as e:
        return f"JSON parse error: {e}"
    except Exception as e:
        return f"Template error: {e}"
