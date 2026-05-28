"""Text tools — analyze, regex, JSON, CSV, markdown, dates, timezone, unit conversion."""

import re
import json
import csv
import io
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def text_analyze(text: str) -> str:
    words = text.split()
    chars = len(text)
    sentences = len(re.findall(r'[.!?]+', text))
    lines = text.count("\n") + 1
    reading_time = max(1, round(len(words) / 200))
    return f"Words: {len(words)}\nCharacters: {chars}\nSentences: {sentences}\nLines: {lines}\nReading time: ~{reading_time} min"


def regex_match(text: str, pattern: str, flags: str = "") -> str:
    try:
        f = 0
        if "i" in flags: f |= re.IGNORECASE
        if "m" in flags: f |= re.MULTILINE
        if "s" in flags: f |= re.DOTALL
        matches = list(re.finditer(pattern, text, f))
        if not matches:
            return "No matches found"
        lines = [f"Found {len(matches)} match(es):"]
        for i, m in enumerate(matches, 1):
            lines.append(f"  {i}: pos={m.start()}-{m.end()}, text={m.group()!r}")
        return "\n".join(lines)
    except re.error as e:
        return f"Regex error: {e}"


def regex_replace(text: str, pattern: str, replacement: str, flags: str = "") -> str:
    try:
        f = 0
        if "i" in flags: f |= re.IGNORECASE
        if "m" in flags: f |= re.MULTILINE
        if "s" in flags: f |= re.DOTALL
        result, count = re.subn(pattern, replacement, text, flags=f)
        return f"Replaced {count} occurrence(s):\n{result}"
    except re.error as e:
        return f"Regex error: {e}"


def json_validate(text: str) -> str:
    try:
        parsed = json.loads(text)
        return f"Valid JSON ({type(parsed).__name__})"
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"


def json_transform(data: str, query: str = "") -> str:
    try:
        parsed = json.loads(data)
        if not query:
            return json.dumps(parsed, indent=2)
        parts = query.strip(".").split(".")
        current = parsed
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, f"<key '{part}' not found>")
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    current = f"<index {part} out of range>"
            else:
                current = f"<cannot traverse into {type(current).__name__}>"
                break
        return json.dumps(current, indent=2, default=str)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"


def csv_parse(content: str, delimiter: str = ",") -> str:
    try:
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)
        if not rows:
            return "No rows found"
        headers = list(rows[0].keys())
        lines = [f"Columns: {', '.join(headers)}", f"Rows: {len(rows)}"]
        for i, row in enumerate(rows[:10], 1):
            vals = [f"{k}={v}" for k, v in row.items() if v]
            lines.append(f"  {i}: {', '.join(vals)}")
        if len(rows) > 10:
            lines.append(f"  ... and {len(rows) - 10} more rows")
        return "\n".join(lines)
    except Exception as e:
        return f"CSV error: {e}"


def csv_to_json(content: str, delimiter: str = ",") -> str:
    try:
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)
        return json.dumps(rows, indent=2) if rows else "[]"
    except Exception as e:
        return f"CSV error: {e}"


def markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.split("\n")
    html_parts = []
    in_list = False
    for line in lines:
        if re.match(r'^#{1,6}\s', line):
            level = len(re.match(r'^#+', line).group())
            html_parts.append(f"<h{level}>{line[level+1:]}</h{level}>")
        elif re.match(r'^[-*]\s', line):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{line[2:]}</li>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if line.strip() == "":
                html_parts.append("<br>")
            else:
                html_parts.append(f"<p>{line}</p>")
    if in_list:
        html_parts.append("</ul>")
    return "\n".join(html_parts)


def date_format(date_str: str, input_format: str = "", output_format: str = "%Y-%m-%d %H:%M:%S") -> str:
    try:
        if input_format:
            dt = datetime.strptime(date_str, input_format)
        else:
            dt = datetime.fromisoformat(date_str)
        return dt.strftime(output_format)
    except ValueError as e:
        return f"Date error: {e}"


def timezone_convert(date_str: str, from_tz: str = "UTC", to_tz: str = "US/Eastern", input_format: str = "%Y-%m-%d %H:%M:%S") -> str:
    try:
        from dateutil import tz
        dt = datetime.strptime(date_str, input_format)
        dt = dt.replace(tzinfo=tz.gettz(from_tz))
        converted = dt.astimezone(tz.gettz(to_tz))
        return converted.strftime("%Y-%m-%d %H:%M:%S %Z")
    except ImportError:
        return "Error: python-dateutil not installed. Run: pip install python-dateutil"
    except Exception as e:
        return f"Timezone error: {e}"


def unit_convert(value: float, from_unit: str, to_unit: str) -> str:
    conversions = {
        ("c", "f"): lambda v: v * 9/5 + 32,
        ("f", "c"): lambda v: (v - 32) * 5/9,
        ("c", "k"): lambda v: v + 273.15,
        ("k", "c"): lambda v: v - 273.15,
        ("km", "mi"): lambda v: v * 0.621371,
        ("mi", "km"): lambda v: v / 0.621371,
        ("kg", "lb"): lambda v: v * 2.20462,
        ("lb", "kg"): lambda v: v / 2.20462,
        ("m", "ft"): lambda v: v * 3.28084,
        ("ft", "m"): lambda v: v / 3.28084,
        ("l", "gal"): lambda v: v * 0.264172,
        ("gal", "l"): lambda v: v / 0.264172,
    }
    key = (from_unit.lower().strip(), to_unit.lower().strip())
    if key in conversions:
        result = conversions[key](value)
        return f"{value} {from_unit} = {result:.4f} {to_unit}"
    return f"Error: unsupported conversion from {from_unit} to {to_unit}"
