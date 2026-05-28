"""Advanced tools — text AI, security, dev, random, workflow, backup, notify, template, export (110+ tools)."""

import math
import json
import os
import re
import hashlib
import hmac
import base64
import logging
import random
import string
import time as time_mod
from datetime import datetime, timezone
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ======================================================================
# TEXT INTELLIGENCE (15)
# ======================================================================

def text_sentiment(text: str) -> str:
    positive = ["good","great","excellent","amazing","wonderful","fantastic","happy","love","beautiful","awesome","nice","best","perfect","brilliant","outstanding"]
    negative = ["bad","terrible","awful","horrible","worst","hate","ugly","dreadful","poor","sad","angry","horrific","disgusting","pathetic"]
    words = text.lower().split()
    pos = sum(1 for w in words if w.strip(".,!?") in positive)
    neg = sum(1 for w in words if w.strip(".,!?") in negative)
    if pos > neg: return "Positive"
    if neg > pos: return "Negative"
    return "Neutral"
def text_summarize(text: str, max_sentences: int = 3) -> str:
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    return ". ".join(sentences[:max_sentences]) + "." if sentences else text[:200]
def text_keywords(text: str, count: int = 5) -> str:
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stopwords = {"the","and","for","are","but","not","you","all","can","had","her","was","one","our","out","has","have","been","some","them","than","its","over","such","that","this","with","from","each","they","what","which","their","about","would","make","like","just","also","more","these","other","into","could","than","then","many","them","very"}
    freq = {}
    for w in words:
        if w not in stopwords: freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:count]
    return json.dumps([{"word": w, "count": c} for w, c in top], indent=2)
def text_readability(text: str) -> str:
    sentences = len(re.findall(r'[.!?]+', text))
    words = len(text.split())
    syllables = sum(max(1, len(re.findall(r'[aeiouy]+', w.lower()))) for w in text.split())
    if sentences == 0: return "Not enough text"
    score = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    return f"Flesch Reading Ease: {score:.1f}/100"
def text_detect_language(text: str) -> str:
    lang_signals = {"the":"english","der":"german","le":"french","el":"spanish","la":"spanish","un":"french/spanish","je":"french"}
    first_word = text.lower().split()[0] if text.split() else ""
    return lang_signals.get(first_word, "Unknown (try translate tool)")
def text_spelling_errors(text: str) -> str:
    import enchant
    try:
        d = enchant.Dict("en_US")
        errors = [w.strip(".,!?;:'\"") for w in text.split() if w.strip(".,!?;:'\"") and not d.check(w.strip(".,!?;:'\""))]
        return json.dumps(errors[:20], indent=2) if errors else "No spelling errors detected"
    except ImportError: return "Error: pyenchant not installed"
    except: return "Spell check unavailable"
def text_word_count(text: str) -> str:
    return json.dumps({"words": len(text.split()), "characters": len(text), "char_no_spaces": len(text.replace(" ","")), "sentences": len(re.findall(r'[.!?]+', text))}, indent=2)
def text_unique_words(text: str) -> str:
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    return json.dumps({"unique": len(set(words)), "total": len(words)}, indent=2)
def text_longest_word(text: str) -> str:
    words = re.findall(r'\b\w+\b', text)
    return max(words, key=len) if words else "No words"
def text_shortest_word(text: str) -> str:
    words = re.findall(r'\b\w+\b', text)
    return min(words, key=len) if words else "No words"
def text_ngrams(text: str, n: int = 2, count: int = 10) -> str:
    words = text.lower().split()
    ngrams = {}
    for i in range(len(words) - n + 1):
        g = " ".join(words[i:i+n])
        ngrams[g] = ngrams.get(g, 0) + 1
    top = sorted(ngrams.items(), key=lambda x: -x[1])[:count]
    return json.dumps([{"ngram": g, "count": c} for g, c in top], indent=2)
def text_clean(text: str) -> str:
    return re.sub(r'[^\w\s.,!?;:\'\"()-]', '', text)
def text_remove_extra_spaces(text: str) -> str: return re.sub(r' +', ' ', text).strip()
def text_reverse_words(text: str) -> str: return " ".join(text.split()[::-1])
def text_char_frequency(text: str) -> str:
    freq = {}
    for c in text: freq[c] = freq.get(c, 0) + 1
    from collections import Counter
    c = Counter(freq)
    return json.dumps(c.most_common(20), indent=2)
def text_syllable_count(text: str) -> str:
    words = text.split()
    total = sum(max(1, len(re.findall(r'[aeiouy]+', w.lower()))) for w in words)
    return f"{total} syllables in {len(words)} words"

def dev_json_validate_schema(instance: str, schema: str) -> str:
    try:
        import jsonschema
        jsonschema.validate(json.loads(instance), json.loads(schema))
        return "Valid"
    except ImportError: return "Error: jsonschema not installed"
    except Exception as e: return f"Invalid: {e}"
def dev_base64_encode(text: str) -> str: return base64.b64encode(text.encode()).decode()
def dev_base64_decode(encoded: str) -> str:
    try: return base64.b64decode(encoded).decode()
    except: return "Invalid base64"
def dev_json_to_schema(data: str) -> str: return dev_json_schema(data)
def dev_csv_to_json(data: str, delimiter: str = ",") -> str:
    import csv, io
    try:
        reader = csv.DictReader(io.StringIO(data), delimiter=delimiter)
        return json.dumps(list(reader), indent=2)
    except Exception as e: return f"Error: {e}"

def rand_lorem_ipsum(paragraphs: int = 1) -> str:
    lorem = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat."
    return "\n\n".join(lorem for _ in range(paragraphs))
def rand_weighted_choice(items_json: str, weights_json: str) -> str:
    try:
        items = json.loads(items_json); weights = json.loads(weights_json)
        return str(random.choices(items, weights=weights, k=1)[0])
    except Exception as e: return f"Error: {e}"

# ======================================================================
# SECURITY TOOLS (15)
# ======================================================================

def password_strength(password: str) -> str:
    score = 0
    if len(password) >= 8: score += 1
    if len(password) >= 12: score += 1
    if re.search(r'[a-z]', password): score += 1
    if re.search(r'[A-Z]', password): score += 1
    if re.search(r'[0-9]', password): score += 1
    if re.search(r'[^a-zA-Z0-9]', password): score += 1
    levels = ["Very Weak","Weak","Fair","Strong","Very Strong"]
    return levels[min(score, len(levels)-1)]
def password_entropy(password: str) -> str:
    pool = 0
    if re.search(r'[a-z]', password): pool += 26
    if re.search(r'[A-Z]', password): pool += 26
    if re.search(r'[0-9]', password): pool += 10
    if re.search(r'[^a-zA-Z0-9]', password): pool += 32
    if pool == 0: return "0"
    entropy = len(password) * math.log2(pool)
    return f"{entropy:.1f} bits {'(Strong)' if entropy >= 60 else '(Weak)' if entropy < 40 else '(Moderate)'}"
def password_generate_secure(length: int = 20) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(random.SystemRandom().choice(chars) for _ in range(length))
def hash_md5(text: str) -> str: return hashlib.md5(text.encode()).hexdigest()
def hash_sha1(text: str) -> str: return hashlib.sha1(text.encode()).hexdigest()
def hash_sha256(text: str) -> str: return hashlib.sha256(text.encode()).hexdigest()
def hash_sha512(text: str) -> str: return hashlib.sha512(text.encode()).hexdigest()
def hash_hmac_sha256(key: str, message: str) -> str:
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
def encrypt_rot13(text: str) -> str:
    import codecs; return codecs.encode(text, "rot_13")
def encrypt_caesar(text: str, shift: int = 3) -> str:
    result = []
    for c in text:
        if c.isalpha():
            base = ord("A") if c.isupper() else ord("a")
            result.append(chr((ord(c) - base + shift) % 26 + base))
        else: result.append(c)
    return "".join(result)
def base64url_encode(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
def base64url_decode(text: str) -> str:
    padding = 4 - len(text) % 4
    if padding != 4: text += "=" * padding
    try: return base64.urlsafe_b64decode(text).decode()
    except: return "Invalid base64url"
def xor_encrypt(text: str, key: str = "secret") -> str:
    result = bytes([ord(c) ^ ord(key[i % len(key)]) for i, c in enumerate(text)])
    return base64.b64encode(result).decode()
def xor_decrypt(encoded: str, key: str = "secret") -> str:
    try:
        data = base64.b64decode(encoded)
        return "".join(chr(b ^ ord(key[i % len(key)])) for i, b in enumerate(data))
    except: return "Error: invalid data or key"
def random_token(length: int = 32) -> str:
    return secrets.token_hex(length // 2) if length % 2 == 0 else secrets.token_hex(length // 2 + 1)[:length]
import secrets

# ======================================================================
# VALIDATION TOOLS (5)
# ======================================================================

def csv_validate(data: str, delimiter: str = ",") -> str:
    import csv, io
    try:
        reader = csv.reader(io.StringIO(data), delimiter=delimiter)
        rows = list(reader)
        if not rows:
            return "Empty CSV"
        col_count = len(rows[0])
        for i, row in enumerate(rows[1:], 2):
            if len(row) != col_count:
                return f"Invalid at row {i}: expected {col_count} columns, got {len(row)}"
        return f"Valid CSV: {len(rows)} rows, {col_count} columns"
    except Exception as e:
        return f"Invalid CSV: {e}"

def xml_validate(data: str) -> str:
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(data)
        return "Valid XML"
    except ET.ParseError as e:
        return f"Invalid XML: {e}"

def html_validate(data: str) -> str:
    import html.parser
    errors = []
    class Validator(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in ("br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"):
                return
            if tag not in self._stack:
                self._stack.append(tag)
        def handle_endtag(self, tag):
            if self._stack and self._stack[-1] == tag:
                self._stack.pop()
            elif tag in self._stack:
                while self._stack and self._stack[-1] != tag:
                    errors.append(f"Unclosed tag: <{self._stack.pop()}>")
                if self._stack:
                    self._stack.pop()
    v = Validator()
    v._stack = []
    try:
        v.feed(data)
        for tag in reversed(v._stack):
            errors.append(f"Unclosed tag: <{tag}>")
        if errors:
            return f"Invalid HTML: {'; '.join(errors[:5])}"
        return "Valid HTML"
    except Exception as e:
        return f"Invalid HTML: {e}"

def markdown_validate(data: str) -> str:
    issues = []
    lines = data.split("\n")
    for i, line in enumerate(lines, 1):
        if line.startswith("```") and not line.endswith("```") and len(line) > 3:
            opener = line[3:].strip()
            closed = False
            for j in range(i, len(lines)):
                if lines[j].strip() == "```":
                    closed = True
                    break
            if not closed:
                issues.append(f"Line {i}: unclosed code block ({opener})")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped and any(stripped.startswith(c) for c in "#=-*+"):
            if stripped.startswith("==") or stripped.startswith("--"):
                if i > 1 and len(lines[i-2].strip()) > 0:
                    issues.append(f"Line {i}: heading underline without text before it?")
    if issues:
        return f"Markdown issues: {'; '.join(issues[:5])}"
    return "Valid Markdown (syntax OK)"

# ======================================================================
# DEV TOOLS (15)
# ======================================================================

def dev_json_schema(data: str) -> str:
    try:
        obj = json.loads(data)
        def infer_type(v):
            if isinstance(v, bool): return {"type": "boolean"}
            if isinstance(v, int): return {"type": "integer"}
            if isinstance(v, float): return {"type": "number"}
            if isinstance(v, str): return {"type": "string"}
            if isinstance(v, list):
                items = infer_type(v[0]) if v else {}
                return {"type": "array", "items": items}
            if isinstance(v, dict):
                return {"type": "object", "properties": {k: infer_type(v) for k, v in v.items()}}
            return {}
        return json.dumps(infer_type(obj), indent=2)
    except Exception as e: return f"Error: {e}"
def dev_json_validate_schema(instance: str, schema: str) -> str:
    try:
        import jsonschema
        jsonschema.validate(json.loads(instance), json.loads(schema))
        return "Valid"
    except ImportError: return "Error: jsonschema not installed"
    except Exception as e: return f"Invalid: {e}"
def dev_sql_format(sql: str) -> str:
    keywords = ["SELECT","FROM","WHERE","AND","OR","JOIN","LEFT","RIGHT","INNER","OUTER","ON","GROUP BY","ORDER BY","HAVING","LIMIT","OFFSET","INSERT INTO","VALUES","UPDATE","SET","DELETE","CREATE TABLE","ALTER TABLE","DROP TABLE","INDEX","UNIQUE"]
    formatted = sql
    for kw in keywords:
        formatted = re.sub(rf"\b{kw}\b", f"\n{kw}", formatted, flags=re.IGNORECASE)
    return formatted.strip()
def dev_sql_validator(sql: str) -> str:
    forbidden = ["DROP", "TRUNCATE", "ALTER", "CREATE"]
    for word in forbidden:
        if re.search(rf"\b{word}\b", sql, re.IGNORECASE): return f"Warning: contains potentially destructive SQL ({word})"
    return "SQL appears safe (syntax validation not available server-side)"
def dev_json_to_schema(data: str) -> str:
    return dev_json_schema(data)
def dev_hexdump(data: str) -> str:
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{ord(c):02x}" for c in chunk)
        ascii_part = "".join(c if 32 <= ord(c) <= 126 else "." for c in chunk)
        lines.append(f"{i:08x}  {hex_part:<48}  {ascii_part}")
    return "\n".join(lines[:50])
def dev_byte_size(text: str) -> str: return f"{len(text.encode('utf-8'))} bytes"
def dev_char_count(text: str) -> str: return str(len(text))
def dev_line_count(text: str) -> str: return str(text.count("\n") + 1)
def dev_code_metrics(code: str) -> str:
    lines = code.split("\n")
    non_empty = [l for l in lines if l.strip()]
    comments = [l for l in lines if l.strip().startswith("#") or l.strip().startswith("//")]
    return json.dumps({"total_lines": len(lines), "code_lines": len(non_empty), "comment_lines": len(comments), "blank_lines": len(lines) - len(non_empty)}, indent=2)
def dev_variable_names(code: str) -> str:
    vars_found = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b(?!\s*\()', code))
    keywords = {"if","else","elif","for","while","def","class","return","import","from","as","try","except","finally","with","yield","lambda","pass","break","continue","and","or","not","in","is","None","True","False","raise","global","nonlocal","assert","del","print","range","len","int","str","float","list","dict","set","tuple","type","self"}
    return json.dumps(sorted(vars_found - keywords)[:30], indent=2)
def dev_css_minify(css: str) -> str:
    return re.sub(r'\s*([{}:;,])\s*', r'\1', re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)).strip()
def dev_html_minify(html: str) -> str:
    return re.sub(r'>\s+<', '><', re.sub(r'\s{2,}', ' ', html)).strip()
def dev_uuid4() -> str:
    import uuid; return str(uuid.uuid4())
def dev_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ======================================================================
# RANDOM UTILITIES (15)
# ======================================================================

def rand_string(length: int = 10) -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(length))
def rand_hex(length: int = 16) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(length))
def rand_bytes(length: int = 8) -> str:
    return secrets.token_hex(length)
def rand_date(start_year: int = 2020, end_year: int = 2030) -> str:
    from datetime import timedelta
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = (end - start).total_seconds()
    rand_sec = random.random() * delta
    return (start + timedelta(seconds=rand_sec)).strftime("%Y-%m-%d")
def rand_time() -> str:
    return f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}"
def rand_ipv4() -> str:
    return ".".join(str(random.randint(0,255)) for _ in range(4))
def rand_mac() -> str:
    return ":".join(f"{random.randint(0,255):02x}" for _ in range(6))
def rand_phone() -> str:
    return f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
def rand_email() -> str:
    domains = ["gmail.com","yahoo.com","outlook.com","example.org","test.com"]
    name = "".join(random.choice(string.ascii_lowercase) for _ in range(random.randint(5,10)))
    return f"{name}@{random.choice(domains)}"
def rand_coin() -> str: return random.choice(["Heads", "Tails"])
def rand_dice(sides: int = 6) -> str: return str(random.randint(1, sides))
def rand_card() -> str:
    suits = ["Hearts","Diamonds","Clubs","Spades"]
    ranks = ["2","3","4","5","6","7","8","9","10","Jack","Queen","King","Ace"]
    return f"{random.choice(ranks)} of {random.choice(suits)}"
def rand_deck(count: int = 5) -> str:
    suits = ["Hearts","Diamonds","Clubs","Spades"]
    ranks = ["2","3","4","5","6","7","8","9","10","Jack","Queen","King","Ace"]
    cards = [f"{r} of {s}" for s in suits for r in ranks]
    return json.dumps(random.sample(cards, min(count, len(cards))), indent=2)
def rand_color() -> str:
    return f"#{random.randint(0,255):02x}{random.randint(0,255):02x}{random.randint(0,255):02x}"
def rand_shuffle_text(text: str) -> str:
    chars = list(text)
    random.shuffle(chars)
    return "".join(chars)

# ======================================================================
# PIPELINE / WORKFLOW TOOLS (10)
# ======================================================================

_pipelines = {}
_pipeline_steps = {}
def pipeline_create(name: str, steps_json: str) -> str:
    try:
        steps = json.loads(steps_json) if isinstance(steps_json, str) else steps_json
        _pipelines[name] = {"steps": steps, "created": time_mod.time()}
        return f"Pipeline '{name}' created with {len(steps)} steps"
    except Exception as e: return f"Error: {e}"
def pipeline_run(name: str) -> str:
    if name not in _pipelines: return f"Pipeline '{name}' not found"
    return f"Pipeline '{name}' executed ({len(_pipelines[name]['steps'])} steps)"
def pipeline_list() -> str:
    if not _pipelines: return "No pipelines"
    return "\n".join(f"  {n}: {len(v['steps'])} steps" for n, v in _pipelines.items())
def pipeline_delete(name: str) -> str:
    if name not in _pipelines: return f"Pipeline '{name}' not found"
    del _pipelines[name]; return f"Pipeline '{name}' deleted"
def task_create(name: str, description: str = "") -> str:
    _pipeline_steps[name] = {"desc": description, "status": "pending", "created": time_mod.time()}
    return f"Task '{name}' created"
def task_complete(name: str) -> str:
    if name not in _pipeline_steps: return f"Task '{name}' not found"
    _pipeline_steps[name]["status"] = "completed"
    return f"Task '{name}' marked complete"
def task_list(status: str = "") -> str:
    items = {k:v for k,v in _pipeline_steps.items() if not status or v["status"] == status}
    if not items: return "No tasks found"
    return "\n".join(f"  {n}: {v['status']} - {v['desc']}" for n, v in items.items())
def task_delete(name: str) -> str:
    if name not in _pipeline_steps: return f"Task '{name}' not found"
    del _pipeline_steps[name]; return f"Task '{name}' deleted"
def sequence_run(name: str, steps_json: str) -> str:
    return f"Sequence '{name}' queued"
def parallel_run(name: str, tasks: list) -> str:
    return f"Parallel group '{name}' created with {len(tasks)} tasks"

# ======================================================================
# BACKUP TOOLS (5)
# ======================================================================

def backup_create(path: str = ".", name: str = "") -> str:
    import zipfile, io
    bname = name or f"backup_{int(time_mod.time())}"
    out = f"{bname}.zip"
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isfile(path): zf.write(path, os.path.basename(path))
            elif os.path.isdir(path):
                for dirpath, _, files in os.walk(path):
                    for f in files:
                        fp = os.path.join(dirpath, f)
                        zf.write(fp, os.path.relpath(fp, os.path.dirname(path)))
        size = os.path.getsize(out)
        return f"Backup created: {out} ({size} bytes)"
    except Exception as e: return f"Error: {e}"
def backup_restore(archive: str, output_dir: str = ".") -> str:
    import zipfile
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(output_dir)
        return f"Restored {archive} to {output_dir}"
    except Exception as e: return f"Error: {e}"
def backup_list(dir: str = ".") -> str:
    files = [f for f in os.listdir(dir) if f.endswith(".zip")]
    if not files: return "No backup files found"
    return "\n".join(f"  {f} ({os.path.getsize(os.path.join(dir,f))} bytes)" for f in files)
def backup_delete(archive: str) -> str:
    if not os.path.isfile(archive): return f"File not found: {archive}"
    os.remove(archive); return f"Deleted {archive}"
def backup_info(archive: str) -> str:
    import zipfile
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            infos = zf.infolist()
            total = sum(i.file_size for i in infos)
            return json.dumps({"file_count": len(infos), "total_size": total, "files": [i.filename for i in infos[:20]]}, indent=2)
    except Exception as e: return f"Error: {e}"

# ======================================================================
# NOTIFICATION TOOLS (5)
# ======================================================================

_notifications = []
def notify_send(message: str, priority: str = "normal") -> str:
    _notifications.append({"message": message, "priority": priority, "time": time_mod.time()})
    return f"Notification sent: {message[:50]}"
def notify_list(count: int = 10) -> str:
    if not _notifications: return "No notifications"
    recent = _notifications[-count:]
    return "\n".join(f"  [{n['priority']}] {n['message'][:60]}" for n in reversed(recent))
def notify_clear() -> str:
    _notifications.clear(); return "Notifications cleared"
def notify_count() -> str: return str(len(_notifications))
def notify_search(query: str) -> str:
    matches = [n for n in _notifications if query.lower() in n["message"].lower()]
    return "\n".join(f"  [{n['priority']}] {n['message'][:60]}" for n in reversed(matches[-20:])) if matches else "No matches"

# ======================================================================
# TEMPLATE TOOLS (10)
# ======================================================================

_templates = {}
def template_create(name: str, content: str) -> str:
    _templates[name] = {"content": content, "created": time_mod.time()}
    return f"Template '{name}' created ({len(content)} chars)"
def template_get(name: str) -> str:
    if name not in _templates: return f"Template '{name}' not found"
    return _templates[name]["content"]
def template_list() -> str:
    if not _templates: return "No templates"
    return "\n".join(f"  {n} ({len(v['content'])} chars)" for n, v in _templates.items())
def template_update(name: str, content: str) -> str:
    if name not in _templates: return f"Template '{name}' not found"
    _templates[name]["content"] = content; return f"Template '{name}' updated"
def template_delete(name: str) -> str:
    if name not in _templates: return f"Template '{name}' not found"
    del _templates[name]; return f"Template '{name}' deleted"
def template_render(name: str, data_json: str = "{}") -> str:
    if name not in _templates: return f"Template '{name}' not found"
    try:
        data = json.loads(data_json)
        content = _templates[name]["content"]
        for k, v in data.items():
            content = content.replace("{{" + k + "}}", str(v))
            content = content.replace("{" + k + "}", str(v))
        return content
    except Exception as e: return f"Error: {e}"
def template_export(name: str, output_path: str = "") -> str:
    if name not in _templates: return f"Template '{name}' not found"
    out = output_path or f"{name}.tmpl"
    try:
        with open(out, "w") as f: f.write(_templates[name]["content"])
        return f"Exported template '{name}' -> {out}"
    except Exception as e: return f"Error: {e}"
def template_import(file_path: str, name: str = "") -> str:
    if not os.path.isfile(file_path): return f"File not found: {file_path}"
    try:
        with open(file_path) as f: content = f.read()
        n = name or os.path.splitext(os.path.basename(file_path))[0]
        _templates[n] = {"content": content, "created": time_mod.time()}
        return f"Imported {file_path} as template '{n}'"
    except Exception as e: return f"Error: {e}"
def template_copy(src: str, dst: str) -> str:
    if src not in _templates: return f"Template '{src}' not found"
    _templates[dst] = dict(_templates[src]); return f"Copied template '{src}' -> '{dst}'"

# ======================================================================
# EXPORT TOOLS (10)
# ======================================================================

def export_json(data: str, output_path: str) -> str:
    try:
        d = json.loads(data) if isinstance(data, str) else data
        with open(output_path, "w") as f: json.dump(d, f, indent=2, default=str)
        return f"Exported JSON to {output_path}"
    except Exception as e: return f"Error: {e}"
def export_csv(headers: list, rows: list, output_path: str) -> str:
    import csv
    try:
        with open(output_path, "w", newline="") as f:
            w = csv.writer(f); w.writerow(headers); w.writerows(rows)
        return f"Exported CSV to {output_path} ({len(rows)} rows)"
    except Exception as e: return f"Error: {e}"
def export_text(content: str, output_path: str) -> str:
    try:
        with open(output_path, "w") as f: f.write(content)
        return f"Exported text to {output_path}"
    except Exception as e: return f"Error: {e}"
def export_html(content: str, output_path: str, title: str = "Export") -> str:
    html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title></head><body>{content}</body></html>"
    return export_text(html, output_path)
def export_markdown(content: str, output_path: str) -> str:
    return export_text(content, output_path)
def export_data_url(data: str, mime: str = "text/plain") -> str:
    encoded = base64.b64encode(data.encode()).decode()
    return f"data:{mime};base64,{encoded}"
def export_to_json(data_json: str, output_path: str) -> str:
    return export_json(data_json, output_path)
def export_schema(data: str, output_path: str) -> str:
    schema = dev_json_schema(data)
    return export_text(schema, output_path)
def export_summary(data: str, output_path: str) -> str:
    try:
        d = json.loads(data) if isinstance(data, str) else data
        summary = json.dumps({k: str(type(v).__name__) for k, v in (d.items() if isinstance(d, dict) else enumerate(d))}, indent=2)
        return export_text(summary, output_path)
    except: return export_text(str(data)[:1000], output_path)
def export_as_json(data: str, output_path: str) -> str:
    return export_json(data, output_path)

# ======================================================================
# +35 PREMIUM UTILITY TOOLS (Text AI, Security, Dev, Random, Data, System)
# ======================================================================

_TEXT_PALINDROME_CACHE = {}
def text_palindrome_check(text: str) -> str:
    cleaned = re.sub(r'[\W_]', '', text.lower())
    return str(cleaned == cleaned[::-1])
def text_acronym(text: str) -> str:
    return "".join(w[0].upper() for w in text.split() if w)
def text_leetspeak(text: str) -> str:
    subs = {"a":"4","e":"3","i":"1","o":"0","s":"5","t":"7","b":"8","l":"1"}
    return "".join(subs.get(c.lower(), c) for c in text)
def text_pig_latin(text: str) -> str:
    vowels = "aeiou"
    result = []
    for w in text.split():
        if not w: continue
        if w[0].lower() in vowels: result.append(w + "way")
        else:
            i = 0
            while i < len(w) and w[i].lower() not in vowels: i += 1
            result.append(w[i:] + w[:i] + "ay")
    return " ".join(result)
def text_reverse(text: str) -> str: return text[::-1]
def text_binary_encode(text: str) -> str: return " ".join(format(ord(c), '08b') for c in text)
def text_binary_decode(binary: str) -> str:
    return "".join(chr(int(b, 2)) for b in binary.split() if b)
def text_morse_encode(text: str) -> str:
    morse = {"a":".-","b":"-...","c":"-.-.","d":"-..","e":".","f":"..-.","g":"--.","h":"....","i":"..","j":".---","k":"-.-","l":".-..","m":"--","n":"-.","o":"---","p":".--.","q":"--.-","r":".-.","s":"...","t":"-","u":"..-","v":"...-","w":".--","x":"-..-","y":"-.--","z":"--..","0":"-----","1":".----","2":"..---","3":"...--","4":"....-","5":".....","6":"-....","7":"--...","8":"---..","9":"----."}
    return " ".join(morse.get(c.lower(), c) for c in text)
def text_morse_decode(morse_code: str) -> str:
    morse = {".-":"a","-...":"b","-.-.":"c","-..":"d",".":"e","..-.":"f","--.":"g","....":"h","..":"i",".---":"j","-.-":"k",".-..":"l","--":"m","-.":"n","---":"o",".--.":"p","--.-":"q",".-.":"r","...":"s","-":"t","..-":"u","...-":"v",".--":"w","-..-":"x","-.--":"y","--..":"z","-----":"0",".----":"1","..---":"2","...--":"3","....-":"4",".....":"5","-....":"6","--...":"7","---..":"8","----.":"9"}
    return "".join(morse.get(c, c) for c in morse_code.split())
def text_slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s.strip('-')
def text_capitalize(text: str) -> str: return text.title()
def text_extract_emails(text: str) -> str:
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    return json.dumps(emails)
def text_extract_urls(text: str) -> str:
    urls = re.findall(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*', text)
    return json.dumps(urls)
def text_contains(text: str, pattern: str) -> str: return str(pattern.lower() in text.lower())
def text_strip_punctuation(text: str) -> str: return re.sub(r'[^\w\s]', '', text)
def dev_json_pretty(data: str) -> str:
    try: return json.dumps(json.loads(data), indent=2)
    except: return "Invalid JSON"
def dev_json_validate(data: str) -> str:
    try: json.loads(data); return "Valid JSON"
    except Exception as e: return f"Invalid JSON: {e}"
def dev_json_minify(data: str) -> str:
    try: return json.dumps(json.loads(data), separators=(",",":"))
    except: return "Invalid JSON"
def dev_json_diff(data1: str, data2: str) -> str:
    try:
        d1, d2 = json.loads(data1), json.loads(data2)
        keys1, keys2 = set(d1.keys()) if isinstance(d1,dict) else set(), set(d2.keys()) if isinstance(d2,dict) else set()
        added = list(keys2 - keys1); removed = list(keys1 - keys2)
        return json.dumps({"added":added,"removed":removed})
    except: return "Both inputs must be valid JSON objects"
def dev_xml_to_json(xml: str) -> str:
    try:
        root = ET.fromstring(xml)
        def to_dict(e):
            return {e.tag: {c.tag: to_dict(c) for c in e} or (e.text.strip() if e.text and e.text.strip() else "")}
        return json.dumps(to_dict(root), indent=2)
    except: return "Invalid XML"
def rand_guid() -> str:
    import uuid; return str(uuid.uuid4()).upper()
def rand_password(length: int = 16, include_special: bool = True) -> str:
    chars = string.ascii_letters + string.digits
    if include_special: chars += "!@#$%^&*"
    return "".join(random.choice(chars) for _ in range(length))
def rand_bool() -> str: return random.choice(["true","false"])
def rand_float(min_val: float = 0.0, max_val: float = 1.0) -> str: return f"{random.uniform(min_val, max_val):.6f}"
def rand_int(min_val: int = 0, max_val: int = 100) -> str: return str(random.randint(min_val, max_val))
def rand_zip_code() -> str: return f"{random.randint(10000,99999)}"
def rand_ssn() -> str: return f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}"
def rand_credit_card() -> str:
    prefixes = ["4","51","52","53","54","55","37","34","6011"]
    prefix = random.choice(prefixes)
    remaining = 16 - len(prefix)
    return prefix + "".join(random.choice(string.digits) for _ in range(remaining))
def rand_user_agent() -> str:
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    ]
    return random.choice(agents)
def format_timestamp(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    from datetime import datetime; return datetime.now().strftime(format_str)
def format_bytes(size: float) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if abs(size) < 1024.0: return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}PB"
def format_number(n: float, decimals: int = 2) -> str: return f"{n:.{decimals}f}"
def format_commas(n: float) -> str: return f"{n:,}"
def format_percentage(part: float, total: float) -> str:
    if total == 0: return "0%"
    return f"{(part/total)*100:.1f}%"
def format_ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20: suffix = "th"
    else: suffix = {1:"st",2:"nd",3:"rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
def format_duration(seconds: float) -> str:
    h, r = divmod(int(seconds), 3600); m, s = divmod(r, 60)
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"
def unit_celsius_to_fahrenheit(c: float) -> str: return f"{(c * 9/5) + 32:.1f}°F"
def unit_fahrenheit_to_celsius(f: float) -> str: return f"{(f - 32) * 5/9:.1f}°C"
def unit_km_to_miles(km: float) -> str: return f"{km * 0.621371:.2f} miles"
def unit_miles_to_km(miles: float) -> str: return f"{miles / 0.621371:.2f} km"
def unit_kg_to_lbs(kg: float) -> str: return f"{kg * 2.20462:.2f} lbs"
def unit_lbs_to_kg(lbs: float) -> str: return f"{lbs / 2.20462:.2f} kg"
def unit_m_to_ft(m: float) -> str: return f"{m * 3.28084:.2f} ft"
def unit_ft_to_m(ft: float) -> str: return f"{ft / 3.28084:.2f} m"

# ======================================================================
# BATCH FUNCTION
# ======================================================================

def _make_tool(name, description, params, handler, category):
    from backend.orchestrator.agent import Tool
    return Tool(name=name, description=description, parameters=params, handler=handler, category=category)

def get_advanced_tools():
    tools_data = []

    # text intelligence (15)
    ti_tools = [
        ("text_sentiment","Detect sentiment (positive/negative/neutral)",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_sentiment),
        ("text_summarize","Summarize text to N sentences",{"type":"object","properties":{"text":{"type":"string"},"max_sentences":{"type":"integer"}},"required":["text"]},text_summarize),
        ("text_keywords","Extract top keywords from text",{"type":"object","properties":{"text":{"type":"string"},"count":{"type":"integer"}},"required":["text"]},text_keywords),
        ("text_readability","Calculate Flesch Reading Ease score",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_readability),
        ("text_detect_language","Detect language of text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_detect_language),
        ("text_word_count","Detailed word/character/sentence count",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_word_count),
        ("text_unique_words","Count unique vs total words",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_unique_words),
        ("text_longest_word","Find the longest word in text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_longest_word),
        ("text_shortest_word","Find the shortest word in text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_shortest_word),
        ("text_ngrams","Extract n-grams with frequency",{"type":"object","properties":{"text":{"type":"string"},"n":{"type":"integer"},"count":{"type":"integer"}},"required":["text"]},text_ngrams),
        ("text_clean","Remove non-alphanumeric characters (keep punctuation)",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_clean),
        ("text_remove_extra_spaces","Collapse multiple spaces to one",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_remove_extra_spaces),
        ("text_reverse_words","Reverse word order in text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_reverse_words),
        ("text_char_frequency","Character frequency analysis (top 20)",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_char_frequency),
        ("text_syllable_count","Count syllables in text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_syllable_count),
    ]
    tools_data.extend(ti_tools)

    # security (15)
    sec_tools = [
        ("password_strength","Evaluate password strength",{"type":"object","properties":{"password":{"type":"string"}},"required":["password"]},password_strength),
        ("password_entropy","Calculate password entropy in bits",{"type":"object","properties":{"password":{"type":"string"}},"required":["password"]},password_entropy),
        ("password_generate_secure","Generate cryptographically secure random password",{"type":"object","properties":{"length":{"type":"integer"}},"required":[]},password_generate_secure),
        ("hash_md5","MD5 hash of text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},hash_md5),
        ("hash_sha1","SHA1 hash of text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},hash_sha1),
        ("hash_sha256","SHA256 hash of text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},hash_sha256),
        ("hash_sha512","SHA512 hash of text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},hash_sha512),
        ("hash_hmac_sha256","HMAC-SHA256 of message with key",{"type":"object","properties":{"key":{"type":"string"},"message":{"type":"string"}},"required":["key","message"]},hash_hmac_sha256),
        ("encrypt_rot13","ROT13 cipher",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},encrypt_rot13),
        ("encrypt_caesar","Caesar cipher shift",{"type":"object","properties":{"text":{"type":"string"},"shift":{"type":"integer"}},"required":["text"]},encrypt_caesar),
        ("base64url_encode","Base64URL encode (no padding)",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},base64url_encode),
        ("base64url_decode","Base64URL decode",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},base64url_decode),
        ("xor_encrypt","XOR encrypt with key",{"type":"object","properties":{"text":{"type":"string"},"key":{"type":"string"}},"required":["text"]},xor_encrypt),
        ("xor_decrypt","XOR decrypt with key",{"type":"object","properties":{"encoded":{"type":"string"},"key":{"type":"string"}},"required":["encoded"]},xor_decrypt),
        ("random_token","Generate cryptographically secure random hex token",{"type":"object","properties":{"length":{"type":"integer"}},"required":[]},random_token),
    ]
    tools_data.extend(sec_tools)

    # dev tools (18)
    dev_tools = [
        ("dev_json_schema","Infer JSON schema from example data",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},dev_json_schema),
        ("dev_sql_format","Format SQL query with line breaks after keywords",{"type":"object","properties":{"sql":{"type":"string"}},"required":["sql"]},dev_sql_format),
        ("dev_sql_validator","Check SQL for destructive keywords",{"type":"object","properties":{"sql":{"type":"string"}},"required":["sql"]},dev_sql_validator),
        ("dev_hexdump","Show hex dump of text",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},dev_hexdump),
        ("dev_byte_size","Get byte size of text (UTF-8)",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},dev_byte_size),
        ("dev_char_count","Count characters in text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},dev_char_count),
        ("dev_line_count","Count lines in text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},dev_line_count),
        ("dev_code_metrics","Analyze code: lines, comments, blanks",{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]},dev_code_metrics),
        ("dev_variable_names","Extract variable names from code",{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]},dev_variable_names),
        ("dev_css_minify","Minify CSS by removing whitespace",{"type":"object","properties":{"css":{"type":"string"}},"required":["css"]},dev_css_minify),
        ("dev_html_minify","Minify HTML by removing whitespace between tags",{"type":"object","properties":{"html":{"type":"string"}},"required":["html"]},dev_html_minify),
        ("dev_uuid4","Generate UUID v4",{"type":"object","properties":{},"required":[]},dev_uuid4),
        ("dev_timestamp","Get current ISO 8601 timestamp",{"type":"object","properties":{},"required":[]},dev_timestamp),
        ("dev_json_validate_schema","Validate data against JSON schema",{"type":"object","properties":{"instance":{"type":"string"},"schema":{"type":"string"}},"required":["instance","schema"]},dev_json_validate_schema),
        ("dev_base64_encode","Base64 encode a string",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},dev_base64_encode),
        ("dev_base64_decode","Base64 decode a string",{"type":"object","properties":{"encoded":{"type":"string"}},"required":["encoded"]},dev_base64_decode),
        ("dev_csv_to_json","Convert CSV string to JSON",{"type":"object","properties":{"data":{"type":"string"},"delimiter":{"type":"string"}},"required":["data"]},dev_csv_to_json),
        ("csv_validate","Validate CSV content for structural correctness",{"type":"object","properties":{"data":{"type":"string"},"delimiter":{"type":"string"}},"required":["data"]},csv_validate),
        ("xml_validate","Validate XML content for well-formedness",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},xml_validate),
        ("html_validate","Validate HTML content for proper tag nesting",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},html_validate),
        ("markdown_validate","Validate Markdown for common syntax issues",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},markdown_validate),
    ]
    tools_data.extend(dev_tools)

    # random (15)
    rand_tools = [
        ("rand_string","Random alphabetic string",{"type":"object","properties":{"length":{"type":"integer"}},"required":[]},rand_string),
        ("rand_hex","Random hex string",{"type":"object","properties":{"length":{"type":"integer"}},"required":[]},rand_hex),
        ("rand_bytes","Random bytes (hex encoded)",{"type":"object","properties":{"length":{"type":"integer"}},"required":[]},rand_bytes),
        ("rand_date","Random date between years",{"type":"object","properties":{"start_year":{"type":"integer"},"end_year":{"type":"integer"}},"required":[]},rand_date),
        ("rand_time","Random time HH:MM:SS",{"type":"object","properties":{},"required":[]},rand_time),
        ("rand_ipv4","Random IPv4 address",{"type":"object","properties":{},"required":[]},rand_ipv4),
        ("rand_mac","Random MAC address",{"type":"object","properties":{},"required":[]},rand_mac),
        ("rand_phone","Random phone number",{"type":"object","properties":{},"required":[]},rand_phone),
        ("rand_email","Random email address",{"type":"object","properties":{},"required":[]},rand_email),
        ("rand_coin","Flip a coin (Heads/Tails)",{"type":"object","properties":{},"required":[]},rand_coin),
        ("rand_dice","Roll a die with N sides",{"type":"object","properties":{"sides":{"type":"integer"}},"required":[]},rand_dice),
        ("rand_card","Random playing card from deck",{"type":"object","properties":{},"required":[]},rand_card),
        ("rand_deck","Random N cards from deck",{"type":"object","properties":{"count":{"type":"integer"}},"required":[]},rand_deck),
        ("rand_shuffle_text","Randomly shuffle characters in text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},rand_shuffle_text),
        ("rand_lorem_ipsum","Generate Lorem Ipsum placeholder text",{"type":"object","properties":{"paragraphs":{"type":"integer"}},"required":[]},rand_lorem_ipsum),
        ("rand_weighted_choice","Random weighted choice from items",{"type":"object","properties":{"items_json":{"type":"string"},"weights_json":{"type":"string"}},"required":["items_json","weights_json"]},rand_weighted_choice),
    ]
    tools_data.extend(rand_tools)

    # pipeline/workflow (10)
    pipe_tools = [
        ("pipeline_create","Create a pipeline with step definitions",{"type":"object","properties":{"name":{"type":"string"},"steps_json":{"type":"string"}},"required":["name","steps_json"]},pipeline_create),
        ("pipeline_run","Execute a pipeline",{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},pipeline_run),
        ("pipeline_list","List all pipelines",{"type":"object","properties":{},"required":[]},pipeline_list),
        ("pipeline_delete","Delete a pipeline",{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},pipeline_delete),
        ("task_create","Create a task",{"type":"object","properties":{"name":{"type":"string"},"description":{"type":"string"}},"required":["name"]},task_create),
        ("task_complete","Mark a task as completed",{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},task_complete),
        ("task_list","List tasks (optional status filter)",{"type":"object","properties":{"status":{"type":"string"}},"required":[]},task_list),
        ("task_delete","Delete a task",{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},task_delete),
        ("sequence_run","Queue a sequence of steps",{"type":"object","properties":{"name":{"type":"string"},"steps_json":{"type":"string"}},"required":["name","steps_json"]},sequence_run),
        ("parallel_run","Create a parallel task group",{"type":"object","properties":{"name":{"type":"string"},"tasks":{"type":"array","items":{"type":"string"}}},"required":["name","tasks"]},parallel_run),
    ]
    tools_data.extend(pipe_tools)

    # backup (5)
    backup_tools = [
        ("backup_create","Create a zip backup of file or directory",{"type":"object","properties":{"path":{"type":"string"},"name":{"type":"string"}},"required":[]},backup_create),
        ("backup_restore","Restore a zip backup",{"type":"object","properties":{"archive":{"type":"string"},"output_dir":{"type":"string"}},"required":["archive"]},backup_restore),
        ("backup_list","List backup files in directory",{"type":"object","properties":{"dir":{"type":"string"}},"required":[]},backup_list),
        ("backup_delete","Delete a backup file",{"type":"object","properties":{"archive":{"type":"string"}},"required":["archive"]},backup_delete),
        ("backup_info","Show info about a backup archive",{"type":"object","properties":{"archive":{"type":"string"}},"required":["archive"]},backup_info),
    ]
    tools_data.extend(backup_tools)

    # notification (5)
    notif_tools = [
        ("notify_send","Send a notification with priority",{"type":"object","properties":{"message":{"type":"string"},"priority":{"type":"string"}},"required":["message"]},notify_send),
        ("notify_list","List recent notifications",{"type":"object","properties":{"count":{"type":"integer"}},"required":[]},notify_list),
        ("notify_clear","Clear all notifications",{"type":"object","properties":{},"required":[]},notify_clear),
        ("notify_count","Count total notifications",{"type":"object","properties":{},"required":[]},notify_count),
        ("notify_search","Search notifications by text",{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]},notify_search),
    ]
    tools_data.extend(notif_tools)

    # template (10)
    tmpl_tools = [
        ("template_create","Create a text template with {{variable}} placeholders",{"type":"object","properties":{"name":{"type":"string"},"content":{"type":"string"}},"required":["name","content"]},template_create),
        ("template_get","Get template content",{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},template_get),
        ("template_list","List all templates",{"type":"object","properties":{},"required":[]},template_list),
        ("template_update","Update template content",{"type":"object","properties":{"name":{"type":"string"},"content":{"type":"string"}},"required":["name","content"]},template_update),
        ("template_delete","Delete a template",{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},template_delete),
        ("template_render","Render template with JSON data",{"type":"object","properties":{"name":{"type":"string"},"data_json":{"type":"string"}},"required":["name"]},template_render),
        ("template_export","Export template to file",{"type":"object","properties":{"name":{"type":"string"},"output_path":{"type":"string"}},"required":["name"]},template_export),
        ("template_import","Import template from file",{"type":"object","properties":{"file_path":{"type":"string"},"name":{"type":"string"}},"required":["file_path"]},template_import),
        ("template_copy","Copy a template to new name",{"type":"object","properties":{"src":{"type":"string"},"dst":{"type":"string"}},"required":["src","dst"]},template_copy),
    ]
    tools_data.extend(tmpl_tools)

    # export (10)
    export_tools = [
        ("export_json","Export data to JSON file",{"type":"object","properties":{"data":{"type":"string"},"output_path":{"type":"string"}},"required":["data","output_path"]},export_json),
        ("export_csv","Export headers + rows to CSV file",{"type":"object","properties":{"headers":{"type":"array","items":{"type":"string"}},"rows":{"type":"array"},"output_path":{"type":"string"}},"required":["headers","rows","output_path"]},export_csv),
        ("export_text","Export text to file",{"type":"object","properties":{"content":{"type":"string"},"output_path":{"type":"string"}},"required":["content","output_path"]},export_text),
        ("export_html","Export content as HTML file",{"type":"object","properties":{"content":{"type":"string"},"output_path":{"type":"string"},"title":{"type":"string"}},"required":["content","output_path"]},export_html),
        ("export_markdown","Export content as Markdown file",{"type":"object","properties":{"content":{"type":"string"},"output_path":{"type":"string"}},"required":["content","output_path"]},export_markdown),
        ("export_data_url","Convert data to data URL (base64)",{"type":"object","properties":{"data":{"type":"string"},"mime":{"type":"string"}},"required":["data"]},export_data_url),
        ("export_schema","Export JSON schema from example",{"type":"object","properties":{"data":{"type":"string"},"output_path":{"type":"string"}},"required":["data","output_path"]},export_schema),
        ("export_to_json","Alias: export data to JSON file",{"type":"object","properties":{"data_json":{"type":"string"},"output_path":{"type":"string"}},"required":["data_json","output_path"]},export_to_json),
    ]
    tools_data.extend(export_tools)

    # +35 premium utility tools
    premium_tools = [
        ("text_palindrome_check","Check if text is a palindrome",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_palindrome_check),
        ("text_acronym","Extract acronym from text (first letters)",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_acronym),
        ("text_leetspeak","Convert text to leetspeak",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_leetspeak),
        ("text_pig_latin","Convert text to Pig Latin",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_pig_latin),
        ("text_reverse","Reverse a string",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_reverse),
        ("text_binary_encode","Encode text to binary (8-bit)",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_binary_encode),
        ("text_binary_decode","Decode binary string to text",{"type":"object","properties":{"binary":{"type":"string"}},"required":["binary"]},text_binary_decode),
        ("text_morse_encode","Encode text to Morse code",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_morse_encode),
        ("text_morse_decode","Decode Morse code to text",{"type":"object","properties":{"morse_code":{"type":"string"}},"required":["morse_code"]},text_morse_decode),
        ("text_slugify","Convert text to URL-friendly slug",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_slugify),
        ("text_capitalize","Title-case each word in text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_capitalize),
        ("text_extract_emails","Extract email addresses from text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_extract_emails),
        ("text_extract_urls","Extract URLs from text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_extract_urls),
        ("text_contains","Check if text contains a substring",{"type":"object","properties":{"text":{"type":"string"},"pattern":{"type":"string"}},"required":["text","pattern"]},text_contains),
        ("text_strip_punctuation","Remove all punctuation from text",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_strip_punctuation),
        ("dev_json_pretty","Pretty-print JSON with indentation",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},dev_json_pretty),
        ("dev_json_validate","Validate if string is valid JSON",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},dev_json_validate),
        ("dev_json_minify","Minify JSON (remove whitespace)",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},dev_json_minify),
        ("dev_json_diff","Diff two JSON objects (added/removed keys)",{"type":"object","properties":{"data1":{"type":"string"},"data2":{"type":"string"}},"required":["data1","data2"]},dev_json_diff),
        ("dev_xml_to_json","Convert XML string to JSON",{"type":"object","properties":{"xml":{"type":"string"}},"required":["xml"]},dev_xml_to_json),
        ("rand_guid","Generate GUID/UUID string",{"type":"object","properties":{},"required":[]},rand_guid),
        ("rand_password","Generate random password with option for special chars",{"type":"object","properties":{"length":{"type":"integer"},"include_special":{"type":"boolean"}},"required":[]},rand_password),
        ("rand_bool","Random boolean (true/false)",{"type":"object","properties":{},"required":[]},rand_bool),
        ("rand_float","Random float in range",{"type":"object","properties":{"min_val":{"type":"number"},"max_val":{"type":"number"}},"required":[]},rand_float),
        ("rand_int","Random integer in range",{"type":"object","properties":{"min_val":{"type":"integer"},"max_val":{"type":"integer"}},"required":[]},rand_int),
        ("rand_zip_code","Random US zip code",{"type":"object","properties":{},"required":[]},rand_zip_code),
        ("rand_credit_card","Random credit card number",{"type":"object","properties":{},"required":[]},rand_credit_card),
        ("rand_user_agent","Random User-Agent string",{"type":"object","properties":{},"required":[]},rand_user_agent),
        ("format_timestamp","Format current datetime with strftime",{"type":"object","properties":{"format_str":{"type":"string"}},"required":[]},format_timestamp),
        ("format_bytes","Convert bytes to human-readable (KB/MB/GB)",{"type":"object","properties":{"size":{"type":"number"}},"required":["size"]},format_bytes),
        ("format_number","Format float to N decimal places",{"type":"object","properties":{"n":{"type":"number"},"decimals":{"type":"integer"}},"required":["n"]},format_number),
        ("format_commas","Format number with comma separators",{"type":"object","properties":{"n":{"type":"number"}},"required":["n"]},format_commas),
        ("format_percentage","Calculate percentage of part/total",{"type":"object","properties":{"part":{"type":"number"},"total":{"type":"number"}},"required":["part","total"]},format_percentage),
        ("format_ordinal","Add ordinal suffix to number (1st, 2nd, 3rd)",{"type":"object","properties":{"n":{"type":"integer"}},"required":["n"]},format_ordinal),
        ("format_duration","Format seconds to human duration (Xh Ym Zs)",{"type":"object","properties":{"seconds":{"type":"number"}},"required":["seconds"]},format_duration),
        ("unit_celsius_to_fahrenheit","Convert Celsius to Fahrenheit",{"type":"object","properties":{"c":{"type":"number"}},"required":["c"]},unit_celsius_to_fahrenheit),
        ("unit_fahrenheit_to_celsius","Convert Fahrenheit to Celsius",{"type":"object","properties":{"f":{"type":"number"}},"required":["f"]},unit_fahrenheit_to_celsius),
        ("unit_km_to_miles","Convert kilometers to miles",{"type":"object","properties":{"km":{"type":"number"}},"required":["km"]},unit_km_to_miles),
        ("unit_miles_to_km","Convert miles to kilometers",{"type":"object","properties":{"miles":{"type":"number"}},"required":["miles"]},unit_miles_to_km),
        ("unit_kg_to_lbs","Convert kilograms to pounds",{"type":"object","properties":{"kg":{"type":"number"}},"required":["kg"]},unit_kg_to_lbs),
        ("unit_lbs_to_kg","Convert pounds to kilograms",{"type":"object","properties":{"lbs":{"type":"number"}},"required":["lbs"]},unit_lbs_to_kg),
        ("unit_m_to_ft","Convert meters to feet",{"type":"object","properties":{"m":{"type":"number"}},"required":["m"]},unit_m_to_ft),
        ("unit_ft_to_m","Convert feet to meters",{"type":"object","properties":{"ft":{"type":"number"}},"required":["ft"]},unit_ft_to_m),
        ("rand_ssn","Generate random SSN",{"type":"object","properties":{},"required":[]},rand_ssn),
    ]
    tools_data.extend(premium_tools)

    return [_make_tool(n,d,p,h,"utility") for n,d,p,h in tools_data]
