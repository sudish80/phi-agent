"""Data tools — string, list, dict, number, statistics operations (100+ tools)."""

import math
import json
import random
import statistics
import hashlib
import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ======================================================================
# STRING TOOLS (25)
# ======================================================================

def str_reverse(text: str) -> str: return text[::-1]
def str_upper(text: str) -> str: return text.upper()
def str_lower(text: str) -> str: return text.lower()
def str_capitalize(text: str) -> str: return text.capitalize()
def str_title(text: str) -> str: return text.title()
def str_swapcase(text: str) -> str: return text.swapcase()
def str_truncate(text: str, max_len: int = 100, ellipsis: str = "...") -> str:
    return text[:max_len] + (ellipsis if len(text) > max_len else "")
def str_pad_left(text: str, width: int = 10, char: str = " ") -> str: return text.rjust(width, char)
def str_pad_right(text: str, width: int = 10, char: str = " ") -> str: return text.ljust(width, char)
def str_center(text: str, width: int = 10, char: str = " ") -> str: return text.center(width, char)
def str_strip(text: str, chars: str = "") -> str: return text.strip(chars) if chars else text.strip()
def str_lstrip(text: str, chars: str = "") -> str: return text.lstrip(chars) if chars else text.lstrip()
def str_rstrip(text: str, chars: str = "") -> str: return text.rstrip(chars) if chars else text.rstrip()
def str_split(text: str, delimiter: str = " ") -> str:
    return json.dumps(text.split(delimiter))
def str_join(items: list, delimiter: str = ", ") -> str: return delimiter.join(str(i) for i in items)
def str_replace(text: str, old: str, new: str, count: int = -1) -> str:
    return text.replace(old, new, count) if count >= 0 else text.replace(old, new)
def str_count(text: str, substring: str) -> str: return str(text.count(substring))
def str_find(text: str, substring: str, start: int = 0) -> str:
    idx = text.find(substring, start); return str(idx) if idx >= 0 else "Not found"
def str_contains(text: str, substring: str) -> str: return str(substring in text)
def str_startswith(text: str, prefix: str) -> str: return str(text.startswith(prefix))
def str_endswith(text: str, suffix: str) -> str: return str(text.endswith(suffix))
def str_isalpha(text: str) -> str: return str(text.isalpha())
def str_isdigit(text: str) -> str: return str(text.isdigit())
def str_isalnum(text: str) -> str: return str(text.isalnum())
def str_islower(text: str) -> str: return str(text.islower())
def str_isupper(text: str) -> str: return str(text.isupper())

# ======================================================================
# LIST TOOLS (15)
# ======================================================================

def list_shuffle(items: list) -> str:
    c = list(items); random.shuffle(c); return json.dumps(c)
def list_chunk(items: list, size: int = 2) -> str:
    return json.dumps([items[i:i+size] for i in range(0, len(items), size)])
def list_unique(items: list) -> str:
    seen = set(); return json.dumps([x for x in items if not (x in seen or seen.add(x))])
def list_flatten(items: list) -> str:
    result = []
    def _flatten(x):
        for i in x:
            if isinstance(i, list): _flatten(i)
            else: result.append(i)
    _flatten(items); return json.dumps(result)
def list_group_by(items: list, key: str = "0") -> str:
    groups = {}
    for item in items:
        k = item[key] if isinstance(item, dict) and key in item else str(item)
        groups.setdefault(k, []).append(item)
    return json.dumps(groups, default=str)
def list_sort(items: list, reverse: bool = False) -> str:
    try: return json.dumps(sorted(items, reverse=reverse), default=str)
    except: return json.dumps(sorted(items, key=str, reverse=reverse), default=str)
def list_reverse(items: list) -> str: return json.dumps(list(reversed(items)), default=str)
def list_rotate(items: list, n: int = 1) -> str:
    if not items: return "[]"
    n = n % len(items); return json.dumps(items[n:] + items[:n], default=str)
def list_sample(items: list, count: int = 1) -> str:
    k = min(count, len(items)); return json.dumps(random.sample(items, k) if k > 0 else [], default=str)
def list_weighted_sample(items: list, weights: list = None) -> str:
    if not items: return "[]"
    w = weights or [1]*len(items)
    return json.dumps(random.choices(items, weights=w, k=1)[0], default=str)
def list_union(a: list, b: list) -> str: return json.dumps(list(set(a) | set(b)), default=str)
def list_intersection(a: list, b: list) -> str: return json.dumps(list(set(a) & set(b)), default=str)
def list_difference(a: list, b: list) -> str: return json.dumps(list(set(a) - set(b)), default=str)
def list_sym_diff(a: list, b: list) -> str: return json.dumps(list(set(a) ^ set(b)), default=str)
def list_zip(a: list, b: list) -> str: return json.dumps(list(zip(a, b)), default=str)

# ======================================================================
# DICT TOOLS (15)
# ======================================================================

def dict_merge(dicts_json: str) -> str:
    try:
        dicts = json.loads(dicts_json)
        result = {}
        for d in dicts: result.update(d)
        return json.dumps(result, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_pick(data_json: str, keys: list) -> str:
    try:
        data = json.loads(data_json)
        return json.dumps({k: data[k] for k in keys if k in data}, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_omit(data_json: str, keys: list) -> str:
    try:
        data = json.loads(data_json)
        return json.dumps({k: v for k, v in data.items() if k not in keys}, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_flatten(data_json: str, parent_key: str = "", sep: str = ".") -> str:
    try:
        data = json.loads(data_json)
        items = []
        def _flatten(d, pk):
            if isinstance(d, dict):
                for k, v in d.items():
                    _flatten(v, f"{pk}{sep}{k}" if pk else k)
            elif isinstance(d, list):
                for i, v in enumerate(d):
                    _flatten(v, f"{pk}{sep}{i}" if pk else str(i))
            else: items.append((pk, d))
        _flatten(data, parent_key)
        return json.dumps(dict(items), indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_unflatten(data_json: str, sep: str = ".") -> str:
    try:
        data = json.loads(data_json)
        result = {}
        for flat_key, value in data.items():
            parts = flat_key.split(sep)
            current = result
            for part in parts[:-1]:
                if part not in current: current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        return json.dumps(result, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_deep_get(data_json: str, path: str) -> str:
    try:
        data = json.loads(data_json)
        parts = path.split(".")
        current = data
        for p in parts:
            if isinstance(current, dict): current = current.get(p)
            elif isinstance(current, list):
                try: current = current[int(p)]
                except: return f"Key '{p}' not found"
            else: return f"Cannot traverse into {type(current).__name__}"
        return json.dumps(current, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_deep_set(data_json: str, path: str, value_json: str) -> str:
    try:
        data = json.loads(data_json)
        val = json.loads(value_json)
        parts = path.split(".")
        current = data
        for p in parts[:-1]:
            if p not in current: current[p] = {}
            current = current[p]
        current[parts[-1]] = val
        return json.dumps(data, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_invert(data_json: str) -> str:
    try:
        data = json.loads(data_json)
        return json.dumps({str(v) if not isinstance(v, str) else v: k for k, v in data.items()}, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_sort_keys(data_json: str, reverse: bool = False) -> str:
    try:
        data = json.loads(data_json)
        return json.dumps(dict(sorted(data.items(), reverse=reverse)), indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_sort_values(data_json: str, reverse: bool = False) -> str:
    try:
        data = json.loads(data_json)
        return json.dumps(dict(sorted(data.items(), key=lambda x: x[1], reverse=reverse)), indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_rename_key(data_json: str, old_key: str, new_key: str) -> str:
    try:
        data = json.loads(data_json)
        if old_key in data: data[new_key] = data.pop(old_key)
        return json.dumps(data, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_diff(a_json: str, b_json: str) -> str:
    try:
        a, b = json.loads(a_json), json.loads(b_json)
        added = {k: b[k] for k in b if k not in a}
        removed = {k: a[k] for k in a if k not in b}
        changed = {k: {"from": a[k], "to": b[k]} for k in a if k in b and a[k] != b[k]}
        return json.dumps({"added": added, "removed": removed, "changed": changed}, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_filter(data_json: str, pattern: str = "") -> str:
    try:
        data = json.loads(data_json)
        filtered = {k: v for k, v in data.items() if pattern.lower() in str(k).lower() or pattern.lower() in str(v).lower()}
        return json.dumps(filtered, indent=2, default=str) if filtered else "No matches"
    except Exception as e: return f"Error: {e}"

# ======================================================================
# NUMBER TOOLS (20)
# ======================================================================

def num_round(value: float, decimals: int = 0) -> str: return str(round(value, decimals))
def num_floor(value: float) -> str: return str(math.floor(value))
def num_ceil(value: float) -> str: return str(math.ceil(value))
def num_clamp(value: float, min_val: float = 0, max_val: float = 100) -> str: return str(max(min_val, min(max_val, value)))
def num_percent(value: float, total: float) -> str:
    return f"{value / total * 100:.1f}%" if total else "Error: total is zero"
def num_is_prime(n: int) -> str:
    if n < 2: return "False"
    for i in range(2, int(math.sqrt(n)) + 1):
        if n % i == 0: return "False"
    return "True"
def num_factorize(n: int) -> str:
    factors = []; d = 2
    while d * d <= n:
        while n % d == 0: factors.append(d); n //= d
        d += 1
    if n > 1: factors.append(n)
    return json.dumps(factors)
def num_gcd(a: int, b: int) -> str: return str(math.gcd(a, b))
def num_lcm(a: int, b: int) -> str: return str(a * b // math.gcd(a, b))
def num_fibonacci(n: int) -> str:
    seq = [0, 1]
    for i in range(2, n): seq.append(seq[-1] + seq[-2])
    return json.dumps(seq[:n])
def num_to_binary(n: int) -> str: return bin(n)[2:]
def num_to_hex(n: int) -> str: return hex(n)[2:]
def num_to_octal(n: int) -> str: return oct(n)[2:]
def num_from_base(s: str, base: int = 16) -> str: return str(int(s, base))
def num_to_base(n: int, base: int = 16) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0: return "0"
    result = ""
    while n > 0: result = chars[n % base] + result; n //= base
    return result
def num_percent_change(old: float, new: float) -> str:
    return f"{(new - old) / old * 100:.2f}%" if old else "Error: old value is zero"
def num_ratio(a: float, b: float) -> str:
    if b == 0: return "Error: denominator is zero"
    g = math.gcd(int(a), int(b))
    return f"{int(a/g)}:{int(b/g)}"
def num_format(n: float, decimals: int = 2) -> str: return f"{n:,.{decimals}f}"
def num_abs(n: float) -> str: return str(abs(n))
def num_power(base: float, exp: float) -> str: return str(base ** exp)

# ======================================================================
# STATISTICS TOOLS (15)
# ======================================================================

def stat_mean(values: list) -> str:
    try: n = [float(v) for v in values]; return f"{sum(n)/len(n):.4f}"
    except: return "Error: non-numeric values"
def stat_median(values: list) -> str:
    try: return str(statistics.median([float(v) for v in values]))
    except: return "Error: non-numeric values"
def stat_mode(values: list) -> str:
    try:
        m = statistics.multimode(values)
        return json.dumps(m, default=str)
    except: return "No unique mode"
def stat_stddev(values: list) -> str:
    try: return f"{statistics.stdev([float(v) for v in values]):.4f}"
    except: return "Error: need at least 2 values"
def stat_variance(values: list) -> str:
    try: return f"{statistics.variance([float(v) for v in values]):.4f}"
    except: return "Error: need at least 2 values"
def stat_min(values: list) -> str:
    try: return str(min(float(v) for v in values))
    except: return "Error: non-numeric values"
def stat_max(values: list) -> str:
    try: return str(max(float(v) for v in values))
    except: return "Error: non-numeric values"
def stat_sum(values: list) -> str:
    try: return f"{sum(float(v) for v in values):.4f}"
    except: return "Error: non-numeric values"
def stat_count(values: list) -> str: return str(len(values))
def stat_percentile(values: list, p: float = 50) -> str:
    try:
        n = sorted(float(v) for v in values)
        k = (p / 100) * (len(n) - 1)
        f = int(k); c = math.ceil(k)
        if f == c: return str(n[f])
        return f"{n[f] * (c - k) + n[c] * (k - f):.4f}"
    except: return "Error: non-numeric values"
def stat_quartiles(values: list) -> str:
    try:
        n = sorted(float(v) for v in values)
        def q(p): return statistics.median(n[:len(n)//2]) if p == 25 else statistics.median(n[len(n)//2:]) if p == 75 else statistics.median(n)
        return json.dumps({"Q1": q(25), "Q2": q(50), "Q3": q(75)}, default=str)
    except: return "Error"

def stat_range(values: list) -> str:
    try: n = [float(v) for v in values]; return f"{max(n) - min(n):.4f}"
    except: return "Error"

def stat_correlation(x: list, y: list) -> str:
    try:
        xf, yf = [float(v) for v in x], [float(v) for v in y]
        n = len(xf)
        sx, sy, sxy, sx2, sy2 = sum(xf), sum(yf), sum(a*b for a,b in zip(xf,yf)), sum(v*v for v in xf), sum(v*v for v in yf)
        r = (n * sxy - sx * sy) / math.sqrt((n * sx2 - sx*sx) * (n * sy2 - sy*sy))
        return f"{r:.4f}"
    except: return "Error"

def stat_frequencies(values: list) -> str:
    try:
        freq = {}
        for v in values: freq[v] = freq.get(v, 0) + 1
        return json.dumps(dict(sorted(freq.items(), key=lambda x: -x[1])), default=str)
    except: return "Error"

# Extra stats
def stat_geometric_mean(values: list) -> str:
    try: n = [float(v) for v in values]; return f"{math.prod(n) ** (1/len(n)):.4f}"
    except: return "Error"
def stat_harmonic_mean(values: list) -> str:
    try: n = [float(v) for v in values]; return f"{len(n) / sum(1/v for v in n):.4f}"
    except: return "Error"
def stat_trimmed_mean(values: list, trim: float = 0.1) -> str:
    try:
        n = sorted(float(v) for v in values)
        k = int(len(n) * trim)
        return f"{sum(n[k:-k]) / max(len(n)-2*k, 1):.4f}"
    except: return "Error"
def stat_mad(values: list) -> str:
    try:
        n = [float(v) for v in values]; m = sum(n)/len(n)
        return f"{sum(abs(v-m) for v in n)/len(n):.4f}"
    except: return "Error"
def num_log(value: float, base: float = math.e) -> str:
    try: return f"{math.log(value, base):.6f}"
    except: return "Error"
def num_sqrt(value: float) -> str:
    try: return f"{math.sqrt(value):.6f}"
    except: return "Error"
def num_cbrt(value: float) -> str: return f"{value ** (1/3):.6f}"
def num_sin(degrees: float) -> str: return f"{math.sin(math.radians(degrees)):.6f}"
def num_cos(degrees: float) -> str: return f"{math.cos(math.radians(degrees)):.6f}"
def num_tan(degrees: float) -> str:
    try: return f"{math.tan(math.radians(degrees)):.6f}"
    except: return "Error"
def num_abs_diff(a: float, b: float) -> str: return f"{abs(a - b):.4f}"
def num_sign(value: float) -> str: return "Positive" if value > 0 else "Negative" if value < 0 else "Zero"
def num_factorial(n: int) -> str:
    try: return str(math.factorial(n))
    except: return "Error"
def num_inverse(value: float) -> str:
    try: return f"{1/value:.6f}"
    except: return "Error: division by zero"

# Extra string
def str_count_words(text: str) -> str: return str(len(text.split()))
def str_strip_html(text: str) -> str: return re.sub(r'<[^>]+>', '', text)

# Extra list
def list_min_val(items: list) -> str:
    try: return str(min(float(v) for v in items))
    except: return "Error"
def list_max_val(items: list) -> str:
    try: return str(max(float(v) for v in items))
    except: return "Error"
def list_avg_val(items: list) -> str:
    try: n = [float(v) for v in items]; return f"{sum(n)/len(n):.4f}"
    except: return "Error"
def list_sum_val(items: list) -> str:
    try: return f"{sum(float(v) for v in items):.4f}"
    except: return "Error"

# ======================================================================
# BATCH FUNCTION for autoregister
# ======================================================================

def get_data_tools():
    return [
        _make_tool(n, d, p, h, "utility")
        for n, d, p, h in [
            ("str_reverse", "Reverse a string", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_reverse),
            ("str_upper", "Convert string to uppercase", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_upper),
            ("str_lower", "Convert string to lowercase", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_lower),
            ("str_capitalize", "Capitalize first character of string", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_capitalize),
            ("str_title", "Convert string to title case", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_title),
            ("str_swapcase", "Swap case of all characters in string", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_swapcase),
            ("str_truncate", "Truncate string to max length with ellipsis", {"type":"object","properties":{"text":{"type":"string"},"max_len":{"type":"integer"},"ellipsis":{"type":"string"}},"required":["text"]}, str_truncate),
            ("str_pad_left", "Left-pad string to width", {"type":"object","properties":{"text":{"type":"string"},"width":{"type":"integer"},"char":{"type":"string"}},"required":["text","width"]}, str_pad_left),
            ("str_pad_right", "Right-pad string to width", {"type":"object","properties":{"text":{"type":"string"},"width":{"type":"integer"},"char":{"type":"string"}},"required":["text","width"]}, str_pad_right),
            ("str_center", "Center string within width", {"type":"object","properties":{"text":{"type":"string"},"width":{"type":"integer"},"char":{"type":"string"}},"required":["text","width"]}, str_center),
            ("str_strip", "Strip whitespace or specified chars from both ends", {"type":"object","properties":{"text":{"type":"string"},"chars":{"type":"string"}},"required":["text"]}, str_strip),
            ("str_lstrip", "Strip whitespace or chars from left side", {"type":"object","properties":{"text":{"type":"string"},"chars":{"type":"string"}},"required":["text"]}, str_lstrip),
            ("str_rstrip", "Strip whitespace or chars from right side", {"type":"object","properties":{"text":{"type":"string"},"chars":{"type":"string"}},"required":["text"]}, str_rstrip),
            ("str_split", "Split string by delimiter into list", {"type":"object","properties":{"text":{"type":"string"},"delimiter":{"type":"string"}},"required":["text"]}, str_split),
            ("str_join", "Join list of items with delimiter", {"type":"object","properties":{"items":{"type":"array","items":{}},"delimiter":{"type":"string"}},"required":["items"]}, str_join),
            ("str_replace", "Replace occurrences of old substring with new", {"type":"object","properties":{"text":{"type":"string"},"old":{"type":"string"},"new":{"type":"string"},"count":{"type":"integer"}},"required":["text","old","new"]}, str_replace),
            ("str_count", "Count occurrences of substring in text", {"type":"object","properties":{"text":{"type":"string"},"substring":{"type":"string"}},"required":["text","substring"]}, str_count),
            ("str_find", "Find position of substring in text", {"type":"object","properties":{"text":{"type":"string"},"substring":{"type":"string"},"start":{"type":"integer"}},"required":["text","substring"]}, str_find),
            ("str_contains", "Check if string contains substring", {"type":"object","properties":{"text":{"type":"string"},"substring":{"type":"string"}},"required":["text","substring"]}, str_contains),
            ("str_startswith", "Check if string starts with prefix", {"type":"object","properties":{"text":{"type":"string"},"prefix":{"type":"string"}},"required":["text","prefix"]}, str_startswith),
            ("str_endswith", "Check if string ends with suffix", {"type":"object","properties":{"text":{"type":"string"},"suffix":{"type":"string"}},"required":["text","suffix"]}, str_endswith),
            ("str_isalpha", "Check if string contains only letters", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_isalpha),
            ("str_isdigit", "Check if string contains only digits", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_isdigit),
            ("str_isalnum", "Check if string is alphanumeric", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_isalnum),
            ("str_islower", "Check if string is all lowercase", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_islower),
            ("str_isupper", "Check if string is all uppercase", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_isupper),
            ("list_shuffle", "Shuffle a list randomly", {"type":"object","properties":{"items":{"type":"array"}},"required":["items"]}, list_shuffle),
            ("list_chunk", "Split list into chunks of given size", {"type":"object","properties":{"items":{"type":"array"},"size":{"type":"integer"}},"required":["items","size"]}, list_chunk),
            ("list_unique", "Get unique elements preserving order", {"type":"object","properties":{"items":{"type":"array"}},"required":["items"]}, list_unique),
            ("list_flatten", "Flatten nested lists into single list", {"type":"object","properties":{"items":{"type":"array"}},"required":["items"]}, list_flatten),
            ("list_group_by", "Group list items by a key", {"type":"object","properties":{"items":{"type":"array"},"key":{"type":"string"}},"required":["items"]}, list_group_by),
            ("list_sort", "Sort a list", {"type":"object","properties":{"items":{"type":"array"},"reverse":{"type":"boolean"}},"required":["items"]}, list_sort),
            ("list_reverse", "Reverse a list", {"type":"object","properties":{"items":{"type":"array"}},"required":["items"]}, list_reverse),
            ("list_rotate", "Rotate list elements by n positions", {"type":"object","properties":{"items":{"type":"array"},"n":{"type":"integer"}},"required":["items"]}, list_rotate),
            ("list_sample", "Random sample from list without replacement", {"type":"object","properties":{"items":{"type":"array"},"count":{"type":"integer"}},"required":["items"]}, list_sample),
            ("list_weighted_sample", "Random weighted choice from list", {"type":"object","properties":{"items":{"type":"array"},"weights":{"type":"array","items":{"type":"number"}}},"required":["items"]}, list_weighted_sample),
            ("list_union", "Union of two lists (unique)", {"type":"object","properties":{"a":{"type":"array"},"b":{"type":"array"}},"required":["a","b"]}, list_union),
            ("list_intersection", "Intersection of two lists", {"type":"object","properties":{"a":{"type":"array"},"b":{"type":"array"}},"required":["a","b"]}, list_intersection),
            ("list_difference", "Elements in A not in B", {"type":"object","properties":{"a":{"type":"array"},"b":{"type":"array"}},"required":["a","b"]}, list_difference),
            ("list_sym_diff", "Symmetric difference of two lists", {"type":"object","properties":{"a":{"type":"array"},"b":{"type":"array"}},"required":["a","b"]}, list_sym_diff),
            ("list_zip", "Zip two lists element-wise", {"type":"object","properties":{"a":{"type":"array"},"b":{"type":"array"}},"required":["a","b"]}, list_zip),
            ("dict_merge", "Merge multiple dicts into one", {"type":"object","properties":{"dicts_json":{"type":"string","description":"JSON array of objects"}},"required":["dicts_json"]}, dict_merge),
            ("dict_pick", "Pick specific keys from a dict", {"type":"object","properties":{"data_json":{"type":"string"},"keys":{"type":"array","items":{"type":"string"}}},"required":["data_json","keys"]}, dict_pick),
            ("dict_omit", "Omit specific keys from a dict", {"type":"object","properties":{"data_json":{"type":"string"},"keys":{"type":"array","items":{"type":"string"}}},"required":["data_json","keys"]}, dict_omit),
            ("dict_flatten", "Flatten nested dict with dot notation", {"type":"object","properties":{"data_json":{"type":"string"},"parent_key":{"type":"string"},"sep":{"type":"string"}},"required":["data_json"]}, dict_flatten),
            ("dict_unflatten", "Unflatten dot-notation dict into nested", {"type":"object","properties":{"data_json":{"type":"string"},"sep":{"type":"string"}},"required":["data_json"]}, dict_unflatten),
            ("dict_deep_get", "Deep get a value by dot path", {"type":"object","properties":{"data_json":{"type":"string"},"path":{"type":"string","description":"Dot-notation path"}},"required":["data_json","path"]}, dict_deep_get),
            ("dict_deep_set", "Deep set a value by dot path", {"type":"object","properties":{"data_json":{"type":"string"},"path":{"type":"string"},"value_json":{"type":"string"}},"required":["data_json","path","value_json"]}, dict_deep_set),
            ("dict_invert", "Swap keys and values", {"type":"object","properties":{"data_json":{"type":"string"}},"required":["data_json"]}, dict_invert),
            ("dict_sort_keys", "Sort dict by keys", {"type":"object","properties":{"data_json":{"type":"string"},"reverse":{"type":"boolean"}},"required":["data_json"]}, dict_sort_keys),
            ("dict_sort_values", "Sort dict by values", {"type":"object","properties":{"data_json":{"type":"string"},"reverse":{"type":"boolean"}},"required":["data_json"]}, dict_sort_values),
            ("dict_rename_key", "Rename a key in dict", {"type":"object","properties":{"data_json":{"type":"string"},"old_key":{"type":"string"},"new_key":{"type":"string"}},"required":["data_json","old_key","new_key"]}, dict_rename_key),
            ("dict_diff", "Show differences between two dicts", {"type":"object","properties":{"a_json":{"type":"string"},"b_json":{"type":"string"}},"required":["a_json","b_json"]}, dict_diff),
            ("dict_filter", "Filter dict by key/value containing pattern", {"type":"object","properties":{"data_json":{"type":"string"},"pattern":{"type":"string"}},"required":["data_json"]}, dict_filter),
            ("num_round", "Round a number to given decimals", {"type":"object","properties":{"value":{"type":"number"},"decimals":{"type":"integer"}},"required":["value"]}, num_round),
            ("num_floor", "Floor a number (round down)", {"type":"object","properties":{"value":{"type":"number"}},"required":["value"]}, num_floor),
            ("num_ceil", "Ceil a number (round up)", {"type":"object","properties":{"value":{"type":"number"}},"required":["value"]}, num_ceil),
            ("num_clamp", "Clamp a number between min and max", {"type":"object","properties":{"value":{"type":"number"},"min_val":{"type":"number"},"max_val":{"type":"number"}},"required":["value"]}, num_clamp),
            ("num_percent", "Calculate percentage of total", {"type":"object","properties":{"value":{"type":"number"},"total":{"type":"number"}},"required":["value","total"]}, num_percent),
            ("num_is_prime", "Check if number is prime", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_is_prime),
            ("num_factorize", "Factorize a number into prime factors", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_factorize),
            ("num_gcd", "Greatest common divisor of two numbers", {"type":"object","properties":{"a":{"type":"integer"},"b":{"type":"integer"}},"required":["a","b"]}, num_gcd),
            ("num_lcm", "Least common multiple of two numbers", {"type":"object","properties":{"a":{"type":"integer"},"b":{"type":"integer"}},"required":["a","b"]}, num_lcm),
            ("num_fibonacci", "Generate first n Fibonacci numbers", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_fibonacci),
            ("num_to_binary", "Convert integer to binary string", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_to_binary),
            ("num_to_hex", "Convert integer to hex string", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_to_hex),
            ("num_to_octal", "Convert integer to octal string", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_to_octal),
            ("num_from_base", "Convert string from given base to decimal", {"type":"object","properties":{"s":{"type":"string"},"base":{"type":"integer"}},"required":["s","base"]}, num_from_base),
            ("num_to_base", "Convert decimal to arbitrary base (2-36)", {"type":"object","properties":{"n":{"type":"integer"},"base":{"type":"integer"}},"required":["n","base"]}, num_to_base),
            ("num_percent_change", "Calculate percent change between old and new", {"type":"object","properties":{"old":{"type":"number"},"new":{"type":"number"}},"required":["old","new"]}, num_percent_change),
            ("num_ratio", "Simplify ratio between two numbers", {"type":"object","properties":{"a":{"type":"number"},"b":{"type":"number"}},"required":["a","b"]}, num_ratio),
            ("num_format", "Format number with commas and decimals", {"type":"object","properties":{"n":{"type":"number"},"decimals":{"type":"integer"}},"required":["n"]}, num_format),
            ("num_abs", "Absolute value of a number", {"type":"object","properties":{"n":{"type":"number"}},"required":["n"]}, num_abs),
            ("num_power", "Raise base to exponent power", {"type":"object","properties":{"base":{"type":"number"},"exp":{"type":"number"}},"required":["base","exp"]}, num_power),
            ("stat_mean", "Calculate mean (average) of values", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_mean),
            ("stat_median", "Calculate median of values", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_median),
            ("stat_mode", "Find most frequent values (multimode)", {"type":"object","properties":{"values":{"type":"array"}},"required":["values"]}, stat_mode),
            ("stat_stddev", "Calculate standard deviation", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_stddev),
            ("stat_variance", "Calculate variance", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_variance),
            ("stat_min", "Minimum value in list", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_min),
            ("stat_max", "Maximum value in list", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_max),
            ("stat_sum", "Sum of all values", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_sum),
            ("stat_count", "Count number of values", {"type":"object","properties":{"values":{"type":"array"}},"required":["values"]}, stat_count),
            ("stat_percentile", "Calculate percentile of values", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}},"p":{"type":"number","description":"Percentile 0-100"}},"required":["values","p"]}, stat_percentile),
            ("stat_quartiles", "Calculate Q1, Q2 (median), Q3", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_quartiles),
            ("stat_range", "Calculate range (max-min)", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_range),
            ("stat_correlation", "Pearson correlation between two variables", {"type":"object","properties":{"x":{"type":"array","items":{"type":"number"}},"y":{"type":"array","items":{"type":"number"}}},"required":["x","y"]}, stat_correlation),
            ("stat_frequencies", "Frequency count of each value", {"type":"object","properties":{"values":{"type":"array"}},"required":["values"]}, stat_frequencies),
            # Extra
            ("stat_geometric_mean", "Geometric mean of values", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_geometric_mean),
            ("stat_harmonic_mean", "Harmonic mean of values", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_harmonic_mean),
            ("stat_trimmed_mean", "Trimmed mean (removes outliers)", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}},"trim":{"type":"number"}},"required":["values"]}, stat_trimmed_mean),
            ("stat_mad", "Mean absolute deviation", {"type":"object","properties":{"values":{"type":"array","items":{"type":"number"}}},"required":["values"]}, stat_mad),
            ("num_log", "Logarithm of value with given base", {"type":"object","properties":{"value":{"type":"number"},"base":{"type":"number"}},"required":["value"]}, num_log),
            ("num_sqrt", "Square root of value", {"type":"object","properties":{"value":{"type":"number"}},"required":["value"]}, num_sqrt),
            ("num_cbrt", "Cube root of value", {"type":"object","properties":{"value":{"type":"number"}},"required":["value"]}, num_cbrt),
            ("num_sin", "Sine of angle in degrees", {"type":"object","properties":{"degrees":{"type":"number"}},"required":["degrees"]}, num_sin),
            ("num_cos", "Cosine of angle in degrees", {"type":"object","properties":{"degrees":{"type":"number"}},"required":["degrees"]}, num_cos),
            ("num_tan", "Tangent of angle in degrees", {"type":"object","properties":{"degrees":{"type":"number"}},"required":["degrees"]}, num_tan),
            ("num_abs_diff", "Absolute difference between two numbers", {"type":"object","properties":{"a":{"type":"number"},"b":{"type":"number"}},"required":["a","b"]}, num_abs_diff),
            ("num_sign", "Sign of number (Positive/Negative/Zero)", {"type":"object","properties":{"value":{"type":"number"}},"required":["value"]}, num_sign),
            ("num_factorial", "Factorial of integer", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_factorial),
            ("num_inverse", "Reciprocal (1/value)", {"type":"object","properties":{"value":{"type":"number"}},"required":["value"]}, num_inverse),
            ("str_count_words", "Count words in text", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_count_words),
            ("str_strip_html", "Strip HTML tags from text", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_strip_html),
            ("list_min_val", "Minimum numeric value in list", {"type":"object","properties":{"items":{"type":"array","items":{"type":"number"}}},"required":["items"]}, list_min_val),
            ("list_max_val", "Maximum numeric value in list", {"type":"object","properties":{"items":{"type":"array","items":{"type":"number"}}},"required":["items"]}, list_max_val),
            ("list_avg_val", "Average of numeric values in list", {"type":"object","properties":{"items":{"type":"array","items":{"type":"number"}}},"required":["items"]}, list_avg_val),
            ("list_sum_val", "Sum of numeric values in list", {"type":"object","properties":{"items":{"type":"array","items":{"type":"number"}}},"required":["items"]}, list_sum_val),
            # +35 premium tools
            ("str_levenshtein", "Levenshtein edit distance between two strings", {"type":"object","properties":{"a":{"type":"string"},"b":{"type":"string"}},"required":["a","b"]}, str_levenshtein),
            ("str_similarity", "String similarity ratio (0-1)", {"type":"object","properties":{"a":{"type":"string"},"b":{"type":"string"}},"required":["a","b"]}, str_similarity),
            ("str_contains_any", "Check if string contains any of given substrings", {"type":"object","properties":{"text":{"type":"string"},"substrings":{"type":"array","items":{"type":"string"}}},"required":["text","substrings"]}, str_contains_any),
            ("str_starts_with", "Check if string starts with prefix", {"type":"object","properties":{"text":{"type":"string"},"prefix":{"type":"string"}},"required":["text","prefix"]}, str_starts_with),
            ("str_ends_with", "Check if string ends with suffix", {"type":"object","properties":{"text":{"type":"string"},"suffix":{"type":"string"}},"required":["text","suffix"]}, str_ends_with),
            ("str_truncate_simple", "Truncate string to max length with ellipsis (simpler variant)", {"type":"object","properties":{"text":{"type":"string"},"max_len":{"type":"integer"}},"required":["text","max_len"]}, str_truncate),
            ("str_wrap_lines", "Wrap text lines at given width", {"type":"object","properties":{"text":{"type":"string"},"width":{"type":"integer"}},"required":["text"]}, str_wrap_lines),
            ("str_justify_left", "Left-justify string to width", {"type":"object","properties":{"text":{"type":"string"},"width":{"type":"integer"}},"required":["text","width"]}, str_justify_left),
            ("str_justify_right", "Right-justify string to width", {"type":"object","properties":{"text":{"type":"string"},"width":{"type":"integer"}},"required":["text","width"]}, str_justify_right),
            ("str_justify_center", "Center-justify string to width", {"type":"object","properties":{"text":{"type":"string"},"width":{"type":"integer"}},"required":["text","width"]}, str_justify_center),
            ("str_is_alpha", "Check if string is alphabetic", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_is_alpha),
            ("str_is_digit", "Check if string is numeric", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_is_digit),
            ("str_is_alnum", "Check if string is alphanumeric", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_is_alnum),
            ("str_is_lower", "Check if string is all lowercase", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_is_lower),
            ("str_is_upper", "Check if string is all uppercase", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_is_upper),
            ("str_is_space", "Check if string contains only whitespace", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_is_space),
            ("str_swap_case", "Swap case of each character in string", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_swap_case),
            ("str_capitalize_words", "Capitalize first letter of each word", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_capitalize),
            ("str_count_chars", "Count each character occurrence in string", {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, str_count_chars),
            ("list_chunk_v2", "Split list into chunks of size N", {"type":"object","properties":{"items":{"type":"array"},"size":{"type":"integer"}},"required":["items","size"]}, list_chunk),
            ("list_flatten_one_level", "Flatten nested lists one level", {"type":"object","properties":{"items":{"type":"array"}},"required":["items"]}, list_flatten),
            ("list_unique_preserve_order", "Remove duplicates preserving order", {"type":"object","properties":{"items":{"type":"array"}},"required":["items"]}, list_unique),
            ("list_sort_num", "Sort list of numbers ascending/descending", {"type":"object","properties":{"items":{"type":"array","items":{"type":"number"}},"reverse":{"type":"boolean"}},"required":["items"]}, list_sort_num),
            ("list_sort_str", "Sort list of strings alphabetically", {"type":"object","properties":{"items":{"type":"array","items":{"type":"string"}},"reverse":{"type":"boolean"}},"required":["items"]}, list_sort_str),
            ("list_shuffle_random", "Shuffle list randomly", {"type":"object","properties":{"items":{"type":"array"}},"required":["items"]}, list_shuffle),
            ("list_sample_random", "Pick N random items from list without replacement", {"type":"object","properties":{"items":{"type":"array"},"n":{"type":"integer"}},"required":["items"]}, list_sample),
            ("list_rotate_by_n", "Rotate list by N positions", {"type":"object","properties":{"items":{"type":"array"},"n":{"type":"integer"}},"required":["items"]}, list_rotate),
            ("list_median_sorted", "Median of sorted numeric list", {"type":"object","properties":{"items":{"type":"array","items":{"type":"number"}}},"required":["items"]}, list_median_sorted),
            ("dict_group_by", "Group list of dicts by a key", {"type":"object","properties":{"data_json":{"type":"string"},"key":{"type":"string"}},"required":["data_json","key"]}, dict_group_by),
            ("dict_key_exists", "Check if key exists in dict", {"type":"object","properties":{"data_json":{"type":"string"},"key":{"type":"string"}},"required":["data_json","key"]}, dict_key_exists),
            ("num_is_even", "Check if integer is even", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_is_even),
            ("num_is_odd", "Check if integer is odd", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_is_odd),
            ("num_is_positive", "Check if number is positive", {"type":"object","properties":{"n":{"type":"number"}},"required":["n"]}, num_is_positive),
            ("num_is_negative", "Check if number is negative", {"type":"object","properties":{"n":{"type":"number"}},"required":["n"]}, num_is_negative),
            ("num_is_zero", "Check if number is zero", {"type":"object","properties":{"n":{"type":"number"}},"required":["n"]}, num_is_zero),
            ("num_to_roman", "Convert integer to Roman numeral", {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]}, num_to_roman),
            ("num_from_roman", "Convert Roman numeral to integer", {"type":"object","properties":{"roman":{"type":"string"}},"required":["roman"]}, num_from_roman),
        ]
    ]

def str_levenshtein(a: str, b: str) -> str:
    n, m = len(a), len(b); dp = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): dp[i][0] = i
    for j in range(m+1): dp[0][j] = j
    for i in range(1,n+1):
        for j in range(1,m+1):
            cost = 0 if a[i-1]==b[j-1] else 1
            dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+cost)
    return str(dp[n][m])
def str_similarity(a: str, b: str) -> str:
    n, m = len(a), len(b); dp = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): dp[i][0] = i
    for j in range(m+1): dp[0][j] = j
    for i in range(1,n+1):
        for j in range(1,m+1):
            cost = 0 if a[i-1]==b[j-1] else 1
            dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+cost)
    max_len = max(n,m); dist = dp[n][m]
    return f"{1 - dist/max_len:.4f}" if max_len else "1.0"
def str_contains_any(text: str, substrings: list) -> str: return str(any(s in text for s in substrings))
def str_starts_with(text: str, prefix: str) -> str: return str(text.startswith(prefix))
def str_ends_with(text: str, suffix: str) -> str: return str(text.endswith(suffix))
def str_truncate(text: str, max_len: int = 50) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text
def str_wrap_lines(text: str, width: int = 80) -> str:
    import textwrap; return "\n".join(textwrap.wrap(text, width=width))
def str_justify_left(text: str, width: int = 20) -> str: return text.ljust(width)
def str_justify_right(text: str, width: int = 20) -> str: return text.rjust(width)
def str_justify_center(text: str, width: int = 20) -> str: return text.center(width)
def str_is_alpha(text: str) -> str: return str(text.isalpha())
def str_is_digit(text: str) -> str: return str(text.isdigit())
def str_is_alnum(text: str) -> str: return str(text.isalnum())
def str_is_lower(text: str) -> str: return str(text.islower())
def str_is_upper(text: str) -> str: return str(text.isupper())
def str_is_space(text: str) -> str: return str(text.isspace())
def str_swap_case(text: str) -> str: return text.swapcase()
def str_capitalize(text: str) -> str: return " ".join(w.capitalize() for w in text.split())
def str_count_chars(text: str) -> str:
    from collections import Counter; return json.dumps(dict(Counter(text)))
def list_chunk(items: list, size: int = 2) -> str:
    return json.dumps([items[i:i+size] for i in range(0, len(items), size)])
def list_flatten(items: list) -> str:
    result = []
    for i in items: result.extend(i if isinstance(i, list) else [i])
    return json.dumps(result)
def list_unique(items: list) -> str:
    seen = set(); return json.dumps([x for x in items if not (x in seen or seen.add(x))])
def list_sort_num(items: list, reverse: bool = False) -> str:
    return json.dumps(sorted(items, reverse=reverse))
def list_sort_str(items: list, reverse: bool = False) -> str:
    return json.dumps(sorted(items, key=str.lower, reverse=reverse))
def list_shuffle(items: list) -> str:
    c = list(items); random.shuffle(c); return json.dumps(c)
def list_sample(items: list, n: int = 1) -> str:
    return json.dumps(random.sample(items, min(n, len(items))))
def list_rotate(items: list, n: int = 1) -> str:
    n = n % len(items) if items else 0; return json.dumps(items[n:] + items[:n])
def list_median_sorted(items: list) -> str:
    s = sorted(items); n = len(s)
    if n == 0: return "0"
    return str(s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2)
def dict_group_by(data_json: str, key: str) -> str:
    try:
        items = json.loads(data_json) if isinstance(data_json, str) else data_json
        groups = {}
        for item in items:
            k = item.get(key, "__none__")
            groups.setdefault(k, []).append(item)
        return json.dumps({str(k): v for k, v in groups.items()}, indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def dict_key_exists(data_json: str, key: str) -> str:
    try:
        d = json.loads(data_json) if isinstance(data_json, str) else data_json
        return str(key in d)
    except: return "False"
def num_is_even(n: int) -> str: return str(n % 2 == 0)
def num_is_odd(n: int) -> str: return str(n % 2 != 0)
def num_is_positive(n: float) -> str: return str(n > 0)
def num_is_negative(n: float) -> str: return str(n < 0)
def num_is_zero(n: float) -> str: return str(n == 0)
def num_to_roman(n: int) -> str:
    if n < 1 or n > 3999: return "Error: out of range (1-3999)"
    vals = [(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),(50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")]
    res = ""
    for v, s in vals:
        while n >= v: res += s; n -= v
    return res
def num_from_roman(roman: str) -> str:
    roman = roman.upper()
    vals = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
    total = 0; prev = 0
    for c in reversed(roman):
        cur = vals.get(c, 0)
        if cur < prev: total -= cur
        else: total += cur
        prev = cur
    return str(total)

def _make_tool(name, description, params, handler, category):
    from backend.orchestrator.agent import Tool
    return Tool(name=name, description=description, parameters=params, handler=handler, category=category)
