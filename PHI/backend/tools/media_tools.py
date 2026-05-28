"""Media tools — geo, time, color, file ops, HTTP, format conversion, documents, images, media (110+ tools)."""

import math
import json
import os
import shutil
import time as time_mod
import urllib.request
import urllib.error
import base64
import csv
import io
import xml.etree.ElementTree as ET
import logging
import yaml
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ======================================================================
# GEO TOOLS (10)
# ======================================================================

def geo_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    R = 6371
    dlat = math.radians(lat2 - lat1); dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return f"{R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)):.2f} km"
def geo_midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    return json.dumps({"lat": (lat1 + lat2) / 2, "lon": (lon1 + lon2) / 2})
def geo_bounding_box(lat: float, lon: float, radius_km: float = 10) -> str:
    lat_d = radius_km / 111.32; lon_d = radius_km / (111.32 * math.cos(math.radians(lat)))
    return json.dumps({"min_lat": lat - lat_d, "max_lat": lat + lat_d, "min_lon": lon - lon_d, "max_lon": lon + lon_d})
def geo_country_code(name: str) -> str:
    countries = {"united states":"US","canada":"CA","united kingdom":"GB","germany":"DE","france":"FR","japan":"JP","australia":"AU","india":"IN","brazil":"BR","china":"CN","russia":"RU","mexico":"MX","italy":"IT","spain":"ES","netherlands":"NL","sweden":"SE","norway":"NO","switzerland":"CH"}
    return countries.get(name.lower().strip(), f"Country '{name}' not in lookup table")
def geo_dms_to_decimal(deg: float, minutes: float, seconds: float, direction: str = "N") -> str:
    dec = deg + minutes/60 + seconds/3600
    if direction in ("S", "W"): dec = -dec
    return f"{dec:.6f}"
def geo_decimal_to_dms(dec: float) -> str:
    d = abs(dec); deg = int(d); m = int((d - deg) * 60); s = (d - deg - m/60) * 3600
    ns = "N" if dec >= 0 else "S"
    return f"{deg}°{m}'{s:.1f}\"{ns}"
def geo_elevation(lat: float, lon: float) -> str:
    try:
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
            return f"{d['results'][0]['elevation']} m"
    except: return "Elevation lookup unavailable"
def geo_timezone(lat: float, lon: float) -> str:
    try:
        url = f"http://api.timezonedb.com/v2.1/get-time-zone?key=&format=json&by=position&lat={lat}&lng={lon}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
            return d.get("zoneName", "Unknown")
    except: return "Timezone lookup unavailable"
def geo_sunrise_sunset(lat: float, lon: float, date: str = "today") -> str:
    try:
        url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}"
        if date and date != "today": url += f"&date={date}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
            return json.dumps(d.get("results", {}), indent=2)
    except: return "Sunrise/sunset lookup unavailable"
def geo_map_url(lat: float, lon: float, zoom: int = 12) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map={zoom}/{lat}/{lon}"

# ======================================================================
# TIME TOOLS (15)
# ======================================================================

def time_now(tz: str = "UTC") -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
def time_epoch() -> str: return str(time_mod.time())
def time_from_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
def time_diff(t1: str, t2: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    try:
        d1, d2 = datetime.strptime(t1, fmt), datetime.strptime(t2, fmt)
        diff = abs((d2 - d1).total_seconds())
        h, r = divmod(int(diff), 3600); m, s = divmod(r, 60)
        return f"{h}h {m}m {s}s"
    except Exception as e: return f"Error: {e}"
def time_add(date_str: str, days: int = 0, hours: int = 0, minutes: int = 0, fmt: str = "%Y-%m-%d") -> str:
    try:
        dt = datetime.strptime(date_str, fmt)
        dt += timedelta(days=days, hours=hours, minutes=minutes)
        return dt.strftime(fmt)
    except Exception as e: return f"Error: {e}"
def time_subtract(date_str: str, days: int = 0, hours: int = 0, minutes: int = 0, fmt: str = "%Y-%m-%d") -> str:
    return time_add(date_str, -days, -hours, -minutes, fmt)
def time_weekday(date_str: str, fmt: str = "%Y-%m-%d") -> str:
    try: return datetime.strptime(date_str, fmt).strftime("%A")
    except: return "Error: invalid date"
def time_julian_day(year: int, month: int, day: int) -> str:
    from datetime import date
    d = date(year, month, day)
    return str(d.toordinal() + 1721425)
def time_unix_timestamp() -> str: return str(int(time_mod.time()))
def time_iso_format(date_str: str, input_fmt: str = "%Y-%m-%d") -> str:
    try: return datetime.strptime(date_str, input_fmt).isoformat()
    except: return "Error: invalid date"
def time_days_between(d1: str, d2: str, fmt: str = "%Y-%m-%d") -> str:
    try: return str(abs((datetime.strptime(d2, fmt) - datetime.strptime(d1, fmt)).days))
    except: return "Error"
def time_age(birthdate: str, fmt: str = "%Y-%m-%d") -> str:
    try:
        bd = datetime.strptime(birthdate, fmt)
        today = datetime.now()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        return str(age)
    except: return "Error"
def time_next_weekday(target: str = "Monday") -> str:
    weekdays = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    if target.lower() not in weekdays: return "Error: invalid weekday"
    today = datetime.now()
    target_i = weekdays.index(target.lower())
    days_ahead = (target_i - today.weekday()) % 7
    if days_ahead == 0: days_ahead = 7
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
def time_is_leap_year(year: int) -> str: return str(year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
def time_days_in_month(year: int, month: int) -> str:
    import calendar; return str(calendar.monthrange(year, month)[1])

# ======================================================================
# COLOR TOOLS (10)
# ======================================================================

def color_palette(base_color: str = "#3498db", count: int = 5) -> str:
    c = base_color.lstrip("#")
    r, g, b = int(c[0:2],16), int(c[2:4],16), int(c[4:6],16)
    palette = []
    for i in range(count):
        f = i / max(count-1, 1)
        nr = int(r + (255-r)*f*0.5); ng = int(g*(1-f*0.5)); nb = int(b + (255-b)*f*0.3)
        palette.append(f"#{min(255,nr):02x}{min(255,ng):02x}{min(255,nb):02x}")
    return json.dumps(palette)
def color_complementary(hex_color: str) -> str:
    c = hex_color.lstrip("#"); r,g,b = int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)
    return f"#{255-r:02x}{255-g:02x}{255-b:02x}"
def color_analogous(hex_color: str) -> str:
    c = hex_color.lstrip("#"); r,g,b = int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)/255.0
    import colorsys; h,l,s = colorsys.rgb_to_hls(r/255,g/255,b)
    cols = []
    for offset in [-30, -15, 0, 15, 30]:
        nh = (h + offset/360) % 1.0
        nr,ng,nb = colorsys.hls_to_rgb(nh,l,s)
        cols.append(f"#{int(nr*255):02x}{int(ng*255):02x}{int(nb*255):02x}")
    return json.dumps(cols)
def color_triadic(hex_color: str) -> str:
    c = hex_color.lstrip("#")
    r,g,b = int(c[0:2],16)/255,int(c[2:4],16)/255,int(c[4:6],16)/255
    import colorsys; h,l,s = colorsys.rgb_to_hls(r,g,b)
    cols = []
    for offset in [0, 120, 240]:
        nh = (h + offset/360) % 1.0
        nr,ng,nb = colorsys.hls_to_rgb(nh,l,s)
        cols.append(f"#{int(nr*255):02x}{int(ng*255):02x}{int(nb*255):02x}")
    return json.dumps(cols)
def color_contrast_ratio(fg: str, bg: str = "#ffffff") -> str:
    def rel(c):
        c = c/255.0
        return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    def lum(hex_c):
        c = hex_c.lstrip("#")
        r,g,b = int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)
        return 0.2126*rel(r) + 0.7152*rel(g) + 0.0722*rel(b)
    l1,l2 = lum(fg),lum(bg)
    cr = (max(l1,l2)+0.05)/(min(l1,l2)+0.05)
    return f"{cr:.2f}:1"
def color_luminance(hex_color: str) -> str:
    c = hex_color.lstrip("#")
    r,g,b = int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)
    return f"{(0.299*r + 0.587*g + 0.114*b)/255:.3f}"
def color_brightness(hex_color: str) -> str:
    c = hex_color.lstrip("#")
    r,g,b = int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)
    return str((r*299 + g*587 + b*114) // 1000)
def color_is_dark(hex_color: str) -> str:
    return str(int(color_brightness(hex_color).split(" ")[-1].strip()) < 128) if "Error" not in color_brightness(hex_color) else "Error"
def color_random() -> str:
    return f"#{random.randint(0,255):02x}{random.randint(0,255):02x}{random.randint(0,255):02x}"
import random

# ======================================================================
# FILE OPS TOOLS (20)
# ======================================================================

def file_copy(src: str, dst: str) -> str:
    try: shutil.copy2(src, dst); return f"Copied {src} -> {dst}"
    except Exception as e: return f"Error: {e}"
def file_move(src: str, dst: str) -> str:
    try: shutil.move(src, dst); return f"Moved {src} -> {dst}"
    except Exception as e: return f"Error: {e}"
def file_delete(path: str) -> str:
    try:
        if os.path.isfile(path): os.remove(path); return f"Deleted {path}"
        elif os.path.isdir(path): shutil.rmtree(path); return f"Deleted directory {path}"
        else: return f"Path not found: {path}"
    except Exception as e: return f"Error: {e}"
def file_rename(src: str, dst: str) -> str:
    try: os.rename(src, dst); return f"Renamed {src} -> {dst}"
    except Exception as e: return f"Error: {e}"
def file_touch(path: str) -> str:
    try: Path(path).touch(); return f"Created {path}"
    except: return f"Error"
from pathlib import Path
def dir_create(path: str) -> str:
    try: os.makedirs(path, exist_ok=True); return f"Created directory {path}"
    except Exception as e: return f"Error: {e}"
def dir_list(path: str = ".") -> str:
    try:
        items = os.listdir(path)
        lines = [f"{'DIR' if os.path.isdir(os.path.join(path, i)) else 'FILE'} {i}" for i in sorted(items)]
        return "\n".join(lines) if lines else "Empty directory"
    except Exception as e: return f"Error: {e}"
def dir_tree(path: str = ".", max_depth: int = 3) -> str:
    try:
        result = []
        def _walk(p, d):
            if d > max_depth: return
            try:
                for item in sorted(os.listdir(p)):
                    fp = os.path.join(p, item)
                    prefix = "  " * d + ("[DIR] " if os.path.isdir(fp) else "[FILE] ")
                    result.append(f"{prefix}{item}")
                    if os.path.isdir(fp): _walk(fp, d+1)
            except: pass
        _walk(path, 0)
        return "\n".join(result) if result else "Empty"
    except Exception as e: return f"Error: {e}"
def file_size(path: str) -> str:
    try:
        s = os.path.getsize(path)
        for unit in ["B","KB","MB","GB"]:
            if s < 1024: return f"{s:.1f} {unit}"
            s /= 1024
        return f"{s:.1f} TB"
    except: return "Error"
def file_modified(path: str) -> str:
    try:
        t = os.path.getmtime(path)
        return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")
    except: return "Error"
def file_extension(path: str) -> str: return os.path.splitext(path)[1] or "No extension"
def file_dirname(path: str) -> str: return os.path.dirname(path) or "."
def file_basename(path: str) -> str: return os.path.basename(path)
def file_exists(path: str) -> str: return str(os.path.exists(path))
def file_is_file(path: str) -> str: return str(os.path.isfile(path))
def file_is_dir(path: str) -> str: return str(os.path.isdir(path))
def file_join(parts: list) -> str: return os.path.join(*parts)
def file_abspath(path: str) -> str: return os.path.abspath(path)
def file_split(path: str) -> str: return json.dumps(list(os.path.split(path)))
def file_read(path: str, encoding: str = "utf-8") -> str:
    try:
        with open(path, "r", encoding=encoding) as f: return f.read()[:50000]
    except Exception as e: return f"Error: {e}"
def file_write(path: str, content: str, encoding: str = "utf-8") -> str:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, "w", encoding=encoding) as f: f.write(content)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e: return f"Error: {e}"

# ======================================================================
# HTTP TOOLS (10)
# ======================================================================

def http_get(url: str, headers_json: str = "{}") -> str:
    try:
        h = json.loads(headers_json) if isinstance(headers_json, str) else headers_json
        h.setdefault("User-Agent", "Mozilla/5.0")
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", errors="replace")[:10000]
            return f"HTTP {r.status}\n{body}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.reason}\n{e.read().decode('utf-8',errors='replace')[:1000]}"
    except Exception as e: return f"Error: {e}"
def http_post(url: str, data_json: str = "{}", headers_json: str = "{}") -> str:
    try:
        h = json.loads(headers_json) if isinstance(headers_json, str) else headers_json
        h.setdefault("User-Agent", "Mozilla/5.0")
        h.setdefault("Content-Type", "application/json")
        data = json.dumps(json.loads(data_json) if isinstance(data_json, str) else data_json).encode()
        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", errors="replace")[:10000]
            return f"HTTP {r.status}\n{body}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.reason}\n{e.read().decode('utf-8',errors='replace')[:1000]}"
    except Exception as e: return f"Error: {e}"
def http_headers(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.dumps(dict(r.headers), indent=2, default=str)
    except Exception as e: return f"Error: {e}"
def http_status(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"HTTP {r.status} {r.reason}"
    except urllib.error.HTTPError as e: return f"HTTP {e.code} {e.reason}"
    except Exception as e: return f"Error: {e}"
def http_download(url: str, output_path: str = "") -> str:
    try:
        out = output_path or os.path.basename(url.split("?")[0]) or "download.bin"
        urllib.request.urlretrieve(url, out)
        s = os.path.getsize(out)
        return f"Downloaded {url} -> {out} ({s} bytes)"
    except Exception as e: return f"Error: {e}"
def url_encode(text: str) -> str:
    import urllib.parse; return urllib.parse.quote(text)
def url_decode(text: str) -> str:
    import urllib.parse; return urllib.parse.unquote(text)
def url_parse(url: str) -> str:
    import urllib.parse
    p = urllib.parse.urlparse(url)
    return json.dumps({"scheme":p.scheme,"netloc":p.netloc,"path":p.path,"params":p.params,"query":p.query,"fragment":p.fragment}, indent=2)
def base64_encode(text: str) -> str:
    return base64.b64encode(text.encode()).decode()
def base64_decode(encoded: str) -> str:
    try: return base64.b64decode(encoded).decode("utf-8", errors="replace")
    except: return base64.b64decode(encoded).hex()

# ======================================================================
# FORMAT CONVERSION TOOLS (15)
# ======================================================================

def json_prettify(data: str) -> str:
    try: return json.dumps(json.loads(data), indent=2)
    except Exception as e: return f"Error: {e}"
def json_minify(data: str) -> str:
    try: return json.dumps(json.loads(data), separators=(",",":"))
    except Exception as e: return f"Error: {e}"
def json_to_yaml(data: str) -> str:
    try:
        import yaml; return yaml.dump(json.loads(data), default_flow_style=False, allow_unicode=True)
    except ImportError: return "Error: PyYAML not installed"
    except Exception as e: return f"Error: {e}"
def yaml_to_json(data: str) -> str:
    try:
        import yaml; return json.dumps(yaml.safe_load(data), indent=2, default=str)
    except ImportError: return "Error: PyYAML not installed"
    except Exception as e: return f"Error: {e}"
def xml_to_json(data: str) -> str:
    try:
        root = ET.fromstring(data)
        def _to_dict(e):
            d = {}
            for child in e:
                if len(child) == 0 and child.text: d[child.tag] = child.text
                else: d[child.tag] = _to_dict(child)
            return d
        return json.dumps({root.tag: _to_dict(root)}, indent=2)
    except Exception as e: return f"Error: {e}"
def json_to_csv(data: str) -> str:
    try:
        rows = json.loads(data)
        if not rows: return "Empty array"
        if isinstance(rows, dict): rows = [rows]
        out = io.StringIO()
        w = csv.DictWriter(out, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
        return out.getvalue()
    except Exception as e: return f"Error: {e}"
def csv_to_json_str(data: str) -> str:
    try:
        reader = csv.DictReader(io.StringIO(data))
        return json.dumps(list(reader), indent=2)
    except Exception as e: return f"Error: {e}"
def html_escape(text: str) -> str:
    import html; return html.escape(text)
def html_unescape(text: str) -> str:
    import html; return html.unescape(text)
def slugify(text: str) -> str:
    import re; text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text); text = re.sub(r'[\s_]+', '-', text); text = re.sub(r'-+', '-', text)
    return text
def trim_whitespace(text: str) -> str:
    import re; return re.sub(r'\s+', ' ', text).strip()
def tab_to_spaces(text: str, spaces: int = 4) -> str: return text.replace("\t", " " * spaces)
def spaces_to_tabs(text: str, spaces: int = 4) -> str: return text.replace(" " * spaces, "\t")
def indent_text(text: str, level: int = 1, char: str = "  ") -> str:
    return "\n".join(char * level + line for line in text.split("\n"))
def wrap_text(text: str, width: int = 80) -> str:
    import textwrap; return "\n".join(textwrap.wrap(text, width=width))

# Extra tools
def http_put(url: str, data_json: str = "{}", headers_json: str = "{}") -> str:
    try:
        h = json.loads(headers_json); h.setdefault("User-Agent","Mozilla/5.0"); h.setdefault("Content-Type","application/json")
        data = json.dumps(json.loads(data_json)).encode()
        req = urllib.request.Request(url, data=data, headers=h, method="PUT")
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"HTTP {r.status}\n{r.read().decode('utf-8',errors='replace')[:5000]}"
    except urllib.error.HTTPError as e: return f"HTTP {e.code}: {e.reason}"
    except Exception as e: return f"Error: {e}"
def http_delete(url: str, headers_json: str = "{}") -> str:
    try:
        h = json.loads(headers_json); h.setdefault("User-Agent","Mozilla/5.0")
        req = urllib.request.Request(url, headers=h, method="DELETE")
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"HTTP {r.status}: {r.reason}"
    except urllib.error.HTTPError as e: return f"HTTP {e.code}: {e.reason}"
    except Exception as e: return f"Error: {e}"
def http_patch(url: str, data_json: str = "{}", headers_json: str = "{}") -> str:
    try:
        h = json.loads(headers_json); h.setdefault("User-Agent","Mozilla/5.0"); h.setdefault("Content-Type","application/json")
        data = json.dumps(json.loads(data_json)).encode()
        req = urllib.request.Request(url, data=data, headers=h, method="PATCH")
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"HTTP {r.status}\n{r.read().decode('utf-8',errors='replace')[:5000]}"
    except urllib.error.HTTPError as e: return f"HTTP {e.code}: {e.reason}"
    except Exception as e: return f"Error: {e}"
def file_append(path: str, content: str) -> str:
    try:
        with open(path, "a") as f: f.write(content)
        return f"Appended {len(content)} bytes to {path}"
    except Exception as e: return f"Error: {e}"
def file_prepend(path: str, content: str) -> str:
    try:
        if not os.path.isfile(path):
            with open(path, "w") as f: f.write(content)
            return f"Created {path} with {len(content)} bytes"
        with open(path) as f: existing = f.read()
        with open(path, "w") as f: f.write(content + existing)
        return f"Prepended {len(content)} bytes to {path}"
    except Exception as e: return f"Error: {e}"
def color_tetradic(hex_color: str) -> str:
    c = hex_color.lstrip("#")
    r,g,b = int(c[0:2],16)/255,int(c[2:4],16)/255,int(c[4:6],16)/255
    import colorsys; h,l,s = colorsys.rgb_to_hls(r,g,b)
    cols = []
    for offset in [0, 90, 180, 270]:
        nh = (h + offset/360) % 1.0
        nr,ng,nb = colorsys.hls_to_rgb(nh,l,s)
        cols.append(f"#{int(nr*255):02x}{int(ng*255):02x}{int(nb*255):02x}")
    return json.dumps(cols)
def color_shade(hex_color: str, percent: float = 20) -> str:
    c = hex_color.lstrip("#")
    r,g,b = int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)
    f = 1 - percent/100
    return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"
def color_tint(hex_color: str, percent: float = 20) -> str:
    c = hex_color.lstrip("#")
    r,g,b = int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)
    f = percent/100
    return f"#{int(r+(255-r)*f):02x}{int(g+(255-g)*f):02x}{int(b+(255-b)*f):02x}"
def pretty_table(data_json: str) -> str:
    try:
        rows = json.loads(data_json)
        if not rows: return "Empty data"
        if isinstance(rows, dict): rows = [rows]
        headers = list(rows[0].keys())
        col_widths = {h: max(len(h), max(len(str(r.get(h,""))) for r in rows)) for h in headers}
        sep = "+" + "+".join("-" * (col_widths[h]+2) for h in headers) + "+"
        header_row = "| " + " | ".join(h.ljust(col_widths[h]) for h in headers) + " |"
        lines = [sep, header_row, sep]
        for r in rows:
            lines.append("| " + " | ".join(str(r.get(h,"")).ljust(col_widths[h]) for h in headers) + " |")
        lines.append(sep)
        return "\n".join(lines)
    except Exception as e: return f"Error: {e}"
def csv_to_markdown(data: str, delimiter: str = ",") -> str:
    try:
        reader = csv.DictReader(io.StringIO(data), delimiter=delimiter)
        rows = list(reader)
        if not rows: return "Empty"
        headers = list(rows[0].keys())
        lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
        for r in rows:
            lines.append("| " + " | ".join(r.get(h,"") for h in headers) + " |")
        return "\n".join(lines)
    except Exception as e: return f"Error: {e}"
def json_to_markdown(data_json: str) -> str:
    try:
        obj = json.loads(data_json)
        if isinstance(obj, list):
            return csv_to_markdown("\n".join(delimiter.join(str(v) for v in r.values()) for r in obj), ",") if obj and isinstance(obj[0], dict) else json.dumps(obj,indent=2)
        return json.dumps(obj, indent=2, default=str)
    except: return "Error"

# Extra +30 media tools
def json_sort_keys(data: str) -> str:
    try: return json.dumps(json.loads(data), indent=2, sort_keys=True)
    except: return "Error"
def yaml_to_toml(data: str) -> str:
    try:
        d = yaml.safe_load(data) if 'yaml' in str(type(data)) else yaml.safe_load(data)
        if isinstance(d, dict):
            lines = []
            for k, v in d.items():
                if isinstance(v, dict):
                    lines.append(f"[{k}]")
                    for sk, sv in v.items(): lines.append(f"{sk} = {json.dumps(sv)}")
                else: lines.append(f"{k} = {json.dumps(v)}")
            return "\n".join(lines)
        return str(d)
    except: return json.dumps(data)
def toml_to_yaml(data: str) -> str:
    try: return yaml.dump(json.loads(data), default_flow_style=False) if data.strip().startswith("{") else data
    except: return "Error"
def html_to_text(html: str) -> str:
    import html.parser
    class H(html.parser.HTMLParser):
        def __init__(self): super().__init__(); self.text = []
        def handle_data(self, d): self.text.append(d)
    h = H(); h.feed(html); return " ".join(h.text)
def text_to_html(text: str) -> str:
    return f"<html><body><p>{'</p><p>'.join(text.split(chr(10)))}</p></body></html>"
def csv_merge(data1: str, data2: str, delimiter: str = ",") -> str:
    import csv, io
    try:
        r1 = list(csv.DictReader(io.StringIO(data1), delimiter=delimiter))
        r2 = list(csv.DictReader(io.StringIO(data2), delimiter=delimiter))
        if not r1 or not r2: return "Empty input"
        merged = r1 + r2
        out = io.StringIO(); w = csv.DictWriter(out, fieldnames=merged[0].keys())
        w.writeheader(); w.writerows(merged)
        return out.getvalue()
    except: return "Error"
def csv_filter(data: str, column: str, value: str, delimiter: str = ",") -> str:
    import csv, io
    try:
        rows = list(csv.DictReader(io.StringIO(data), delimiter=delimiter))
        filtered = [r for r in rows if r.get(column) == value]
        out = io.StringIO(); w = csv.DictWriter(out, fieldnames=rows[0].keys() if rows else [])
        w.writeheader(); w.writerows(filtered)
        return out.getvalue()
    except: return "Error"
def csv_sort(data: str, column: str, reverse: bool = False, delimiter: str = ",") -> str:
    import csv, io
    try:
        rows = list(csv.DictReader(io.StringIO(data), delimiter=delimiter))
        rows.sort(key=lambda r: r.get(column, ""), reverse=reverse)
        out = io.StringIO(); w = csv.DictWriter(out, fieldnames=rows[0].keys() if rows else [])
        w.writeheader(); w.writerows(rows)
        return out.getvalue()
    except: return "Error"
def csv_columns(data: str, delimiter: str = ",") -> str:
    import csv, io
    try:
        reader = csv.reader(io.StringIO(data), delimiter=delimiter)
        rows = list(reader)
        if not rows: return "Empty"
        return json.dumps({"columns": rows[0], "row_count": len(rows)-1, "data": rows[1:]}, indent=2, default=str)
    except: return "Error"
def geo_reverse_code(lat: float, lon: float) -> str:
    try:
        # Uses OpenStreetMap Nominatim
        import urllib.request, urllib.parse
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            return data.get("display_name", data.get("name", "Unknown"))
    except: return f"{lat},{lon}"
def time_to_timezone(epoch: float, tz: str = "UTC") -> str:
    try:
        from datetime import timezone as tz_mod
        try: import zoneinfo; tz_obj = zoneinfo.ZoneInfo(tz)
        except: tz_obj = tz_mod.utc if tz == "UTC" else tz_mod.utc
        dt = datetime.fromtimestamp(epoch, tz=tz_obj)
        return dt.isoformat()
    except: return str(epoch)
def time_list_timezones() -> str:
    try: import zoneinfo; return json.dumps(sorted(zoneinfo.available_timezones())[:50], indent=2) + "\n..." if zoneinfo.available_timezones() else "[]"
    except: return "Error"
def time_sleep_ms(ms: int = 1000) -> str:
    import time as t; t.sleep(ms/1000); return f"Slept {ms}ms"
def file_mkstemp(suffix: str = ".tmp", prefix: str = "jarvis_") -> str:
    import tempfile; f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix=prefix); return f.name
def file_chmod(path: str, mode: str = "644") -> str:
    try: os.chmod(path, int(mode, 8) if mode.isdigit() else 0o644); return f"Changed mode of {path} to {mode}"
    except: return f"Error changing permissions"
import csv as csv_mod
def file_head(path: str, n: int = 10) -> str:
    try:
        with open(path) as f: lines = [next(f) for _ in range(n)]
        return "".join(lines)
    except: return f"Error reading {path}"
def file_tail(path: str, n: int = 10) -> str:
    try:
        with open(path) as f: lines = f.readlines()
        return "".join(lines[-n:])
    except: return f"Error reading {path}"
def file_count_lines(path: str) -> str:
    try:
        with open(path) as f: return str(sum(1 for _ in f))
    except: return "Error"
def file_is_text(path: str) -> str:
    try:
        with open(path, 'rb') as f:
            chunk = f.read(1024)
            return str(not bool(chunk.translate(None, bytes(range(32,127)) + b'\n\r\t')))
    except: return "Error"
def http_head(url: str, headers_json: str = "{}") -> str:
    try:
        h = json.loads(headers_json); h.setdefault("User-Agent","Mozilla/5.0")
        req = urllib.request.Request(url, headers=h, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.dumps(dict(r.headers), indent=2)
    except: return "Error"
def http_options(url: str) -> str:
    try:
        req = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.headers.get("Allow", "Unknown")
    except: return "Error"
def url_shorten(url: str) -> str:
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({"url": url}).encode()
        req = urllib.request.Request("https://is.gd/create.php?format=simple", data=data)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode().strip()
    except: return url
def base64_encode_file(path: str) -> str:
    try:
        with open(path, 'rb') as f: return base64.b64encode(f.read()).decode()
    except: return "Error"
def base64_decode_to_file(encoded: str, path: str) -> str:
    try:
        data = base64.b64decode(encoded)
        with open(path, 'wb') as f: f.write(data)
        return f"Written {len(data)} bytes to {path}"
    except: return "Error"

_TIME_STOPWATCH = {}
_COLOR_NAMES = {
    "red":"#ff0000","green":"#008000","blue":"#0000ff","yellow":"#ffff00","cyan":"#00ffff",
    "magenta":"#ff00ff","white":"#ffffff","black":"#000000","gray":"#808080","grey":"#808080",
    "orange":"#ffa500","purple":"#800080","pink":"#ffc0cb","brown":"#a52a2a","navy":"#000080",
    "teal":"#008080","maroon":"#800000","lime":"#00ff00","aqua":"#00ffff","silver":"#c0c0c0",
    "fuchsia":"#ff00ff","olive":"#808000","indigo":"#4b0082","violet":"#ee82ee","tan":"#d2b48c",
    "beige":"#f5f5dc","coral":"#ff7f50","ivory":"#fffff0","khaki":"#f0e68c","lavender":"#e6e6fa",
    "plum":"#dda0dd","salmon":"#fa8072","sienna":"#a0522d","tomato":"#ff6347","wheat":"#f5deb3",
}
def color_name_to_hex(name: str) -> str:
    return _COLOR_NAMES.get(name.lower(), f"Unknown color: {name}")
def color_hex_to_name(hex_color: str) -> str:
    c = hex_color.lstrip("#").lower()
    best, best_dist = None, float("inf")
    for name, h in _COLOR_NAMES.items():
        hc = h.lstrip("#")
        dist = sum((int(c[i:i+2],16)-int(hc[i:i+2],16))**2 for i in (0,2,4))
        if dist < best_dist: best_dist, best = dist, name
    return best
def color_mix(c1: str, c2: str, ratio: float = 0.5) -> str:
    r1,g1,b1 = [int(c1.lstrip("#")[i:i+2],16) for i in (0,2,4)]
    r2,g2,b2 = [int(c2.lstrip("#")[i:i+2],16) for i in (0,2,4)]
    r = int(r1*ratio + r2*(1-ratio)); g = int(g1*ratio + g2*(1-ratio)); b = int(b1*ratio + b2*(1-ratio))
    return f"#{r:02x}{g:02x}{b:02x}"
def time_countdown(seconds: float = 10) -> str:
    import time as t
    for i in range(int(seconds), 0, -1): t.sleep(1)
    return f"Countdown finished after {int(seconds)}s"
def time_stopwatch(action: str) -> str:
    now = time_mod.time()
    if action == "start": _TIME_STOPWATCH["start"] = now; return f"Stopwatch started at {now}"
    elif action == "stop" and "start" in _TIME_STOPWATCH:
        elapsed = now - _TIME_STOPWATCH.pop("start")
        return f"Elapsed: {elapsed:.3f}s"
    return "No stopwatch running"
def geo_country_name(code: str) -> str:
    try:
        import pycountry; c = pycountry.countries.get(alpha_2=code.upper())
        return c.name if c else f"Unknown country code: {code}"
    except ImportError: return "Install pycountry for this feature"
def geo_ip_to_coords(ip: str) -> str:
    try:
        import urllib.request
        req = urllib.request.Request(f"http://ip-api.com/json/{ip}", headers={"User-Agent":"JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode())
            return json.dumps({"lat":d.get("lat"),"lon":d.get("lon"),"city":d.get("city"),"country":d.get("country")})
    except: return f"Could not locate {ip}"

# ======================================================================
# BATCH FUNCTION
# ======================================================================

def _make_tool(name, description, params, handler, category):
    from backend.orchestrator.agent import Tool
    return Tool(name=name, description=description, parameters=params, handler=handler, category=category)

def get_media_tools():
    import random as rnd
    tools_data = []

    # geo (10)
    geo_tools = [
        ("geo_distance","Haversine distance between two coordinates in km",{"type":"object","properties":{"lat1":{"type":"number"},"lon1":{"type":"number"},"lat2":{"type":"number"},"lon2":{"type":"number"}},"required":["lat1","lon1","lat2","lon2"]},geo_distance),
        ("geo_midpoint","Midpoint between two coordinates",{"type":"object","properties":{"lat1":{"type":"number"},"lon1":{"type":"number"},"lat2":{"type":"number"},"lon2":{"type":"number"}},"required":["lat1","lon1","lat2","lon2"]},geo_midpoint),
        ("geo_bounding_box","Get bounding box around a coordinate",{"type":"object","properties":{"lat":{"type":"number"},"lon":{"type":"number"},"radius_km":{"type":"number"}},"required":["lat","lon"]},geo_bounding_box),
        ("geo_country_code","Get ISO country code from country name",{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},geo_country_code),
        ("geo_dms_to_decimal","Convert DMS coordinates to decimal degrees",{"type":"object","properties":{"deg":{"type":"number"},"minutes":{"type":"number"},"seconds":{"type":"number"},"direction":{"type":"string"}},"required":["deg","minutes","seconds"]},geo_dms_to_decimal),
        ("geo_decimal_to_dms","Convert decimal degrees to DMS format",{"type":"object","properties":{"dec":{"type":"number"}},"required":["dec"]},geo_decimal_to_dms),
        ("geo_elevation","Look up elevation for coordinates",{"type":"object","properties":{"lat":{"type":"number"},"lon":{"type":"number"}},"required":["lat","lon"]},geo_elevation),
        ("geo_timezone","Look up timezone for coordinates",{"type":"object","properties":{"lat":{"type":"number"},"lon":{"type":"number"}},"required":["lat","lon"]},geo_timezone),
        ("geo_sunrise_sunset","Get sunrise/sunset times for coordinates",{"type":"object","properties":{"lat":{"type":"number"},"lon":{"type":"number"},"date":{"type":"string"}},"required":["lat","lon"]},geo_sunrise_sunset),
        ("geo_map_url","Generate OpenStreetMap URL for coordinates",{"type":"object","properties":{"lat":{"type":"number"},"lon":{"type":"number"},"zoom":{"type":"integer"}},"required":["lat","lon"]},geo_map_url),
    ]
    tools_data.extend(geo_tools)

    # time (15)
    time_tools = [
        ("time_now","Get current UTC time",{"type":"object","properties":{},"required":[]},time_now),
        ("time_epoch","Get current Unix epoch timestamp",{"type":"object","properties":{},"required":[]},time_epoch),
        ("time_from_epoch","Convert Unix epoch to datetime string",{"type":"object","properties":{"epoch":{"type":"number"}},"required":["epoch"]},time_from_epoch),
        ("time_diff","Calculate time difference between two timestamps",{"type":"object","properties":{"t1":{"type":"string"},"t2":{"type":"string"},"fmt":{"type":"string"}},"required":["t1","t2"]},time_diff),
        ("time_add","Add days/hours/minutes to a date",{"type":"object","properties":{"date_str":{"type":"string"},"days":{"type":"integer"},"hours":{"type":"integer"},"minutes":{"type":"integer"},"fmt":{"type":"string"}},"required":["date_str"]},time_add),
        ("time_subtract","Subtract days/hours/minutes from a date",{"type":"object","properties":{"date_str":{"type":"string"},"days":{"type":"integer"},"hours":{"type":"integer"},"minutes":{"type":"integer"},"fmt":{"type":"string"}},"required":["date_str"]},time_subtract),
        ("time_weekday","Get day of week for a date",{"type":"object","properties":{"date_str":{"type":"string"},"fmt":{"type":"string"}},"required":["date_str"]},time_weekday),
        ("time_julian_day","Calculate Julian day number",{"type":"object","properties":{"year":{"type":"integer"},"month":{"type":"integer"},"day":{"type":"integer"}},"required":["year","month","day"]},time_julian_day),
        ("time_unix_timestamp","Get current Unix timestamp (int seconds)",{"type":"object","properties":{},"required":[]},time_unix_timestamp),
        ("time_iso_format","Convert date to ISO 8601 format",{"type":"object","properties":{"date_str":{"type":"string"},"input_fmt":{"type":"string"}},"required":["date_str"]},time_iso_format),
        ("time_days_between","Calculate days between two dates",{"type":"object","properties":{"d1":{"type":"string"},"d2":{"type":"string"},"fmt":{"type":"string"}},"required":["d1","d2"]},time_days_between),
        ("time_age","Calculate age from birthdate",{"type":"object","properties":{"birthdate":{"type":"string"},"fmt":{"type":"string"}},"required":["birthdate"]},time_age),
        ("time_next_weekday","Get date of next occurrence of a weekday",{"type":"object","properties":{"target":{"type":"string","description":"Weekday name"}},"required":["target"]},time_next_weekday),
        ("time_is_leap_year","Check if year is a leap year",{"type":"object","properties":{"year":{"type":"integer"}},"required":["year"]},time_is_leap_year),
        ("time_days_in_month","Get number of days in a month",{"type":"object","properties":{"year":{"type":"integer"},"month":{"type":"integer"}},"required":["year","month"]},time_days_in_month),
    ]
    tools_data.extend(time_tools)

    # color (10)
    color_tools = [
        ("color_palette","Generate a color palette from base color",{"type":"object","properties":{"base_color":{"type":"string"},"count":{"type":"integer"}},"required":[]},color_palette),
        ("color_complementary","Get complementary color",{"type":"object","properties":{"hex_color":{"type":"string"}},"required":["hex_color"]},color_complementary),
        ("color_analogous","Get analogous color scheme (5 colors)",{"type":"object","properties":{"hex_color":{"type":"string"}},"required":["hex_color"]},color_analogous),
        ("color_triadic","Get triadic color scheme (3 colors)",{"type":"object","properties":{"hex_color":{"type":"string"}},"required":["hex_color"]},color_triadic),
        ("color_tetradic","Get tetradic color scheme (4 colors)",{"type":"object","properties":{"hex_color":{"type":"string"}},"required":["hex_color"]},color_tetradic),
        ("color_shade","Darken a color by percentage",{"type":"object","properties":{"hex_color":{"type":"string"},"percent":{"type":"number"}},"required":["hex_color"]},color_shade),
        ("color_tint","Lighten a color by percentage",{"type":"object","properties":{"hex_color":{"type":"string"},"percent":{"type":"number"}},"required":["hex_color"]},color_tint),
        ("color_contrast_ratio","Calculate WCAG contrast ratio between two colors",{"type":"object","properties":{"fg":{"type":"string"},"bg":{"type":"string"}},"required":["fg"]},color_contrast_ratio),
        ("color_luminance","Calculate relative luminance of a color",{"type":"object","properties":{"hex_color":{"type":"string"}},"required":["hex_color"]},color_luminance),
        ("color_brightness","Calculate perceived brightness (0-255)",{"type":"object","properties":{"hex_color":{"type":"string"}},"required":["hex_color"]},color_brightness),
        ("color_is_dark","Check if a color is dark",{"type":"object","properties":{"hex_color":{"type":"string"}},"required":["hex_color"]},color_is_dark),
        ("color_random","Generate a random hex color",{"type":"object","properties":{},"required":[]},color_random),
    ]
    tools_data.extend(color_tools)

    # file ops (20)
    file_tools = [
        ("file_copy","Copy a file",{"type":"object","properties":{"src":{"type":"string"},"dst":{"type":"string"}},"required":["src","dst"]},file_copy),
        ("file_move","Move/rename a file",{"type":"object","properties":{"src":{"type":"string"},"dst":{"type":"string"}},"required":["src","dst"]},file_move),
        ("file_delete","Delete a file or empty directory",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_delete),
        ("file_rename","Rename a file",{"type":"object","properties":{"src":{"type":"string"},"dst":{"type":"string"}},"required":["src","dst"]},file_rename),
        ("dir_create","Create directory (including parents)",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},dir_create),
        ("dir_list","List contents of a directory",{"type":"object","properties":{"path":{"type":"string"}},"required":[]},dir_list),
        ("dir_tree","Show directory tree structure",{"type":"object","properties":{"path":{"type":"string"},"max_depth":{"type":"integer"}},"required":[]},dir_tree),
        ("file_size","Get file size in human-readable format",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_size),
        ("file_modified","Get file modification timestamp",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_modified),
        ("file_extension","Get file extension",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_extension),
        ("file_dirname","Get directory portion of path",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_dirname),
        ("file_basename","Get filename portion of path",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_basename),
        ("file_exists","Check if file exists",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_exists),
        ("file_is_file","Check if path is a file",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_is_file),
        ("file_is_dir","Check if path is a directory",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_is_dir),
        ("file_join","Join path components",{"type":"object","properties":{"parts":{"type":"array","items":{"type":"string"}}},"required":["parts"]},file_join),
        ("file_abspath","Get absolute path",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_abspath),
        ("file_read","Read a text file",{"type":"object","properties":{"path":{"type":"string"},"encoding":{"type":"string"}},"required":["path"]},file_read),
        ("file_write","Write content to a text file",{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"},"encoding":{"type":"string"}},"required":["path","content"]},file_write),
        ("file_touch","Create empty file (like Unix touch)",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_touch),
        ("file_append","Append content to a file",{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]},file_append),
        ("file_prepend","Prepend content to a file",{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]},file_prepend),
    ]
    tools_data.extend(file_tools)

    # HTTP (10)
    http_tools = [
        ("http_get","Make HTTP GET request",{"type":"object","properties":{"url":{"type":"string"},"headers_json":{"type":"string"}},"required":["url"]},http_get),
        ("http_post","Make HTTP POST request with JSON body",{"type":"object","properties":{"url":{"type":"string"},"data_json":{"type":"string"},"headers_json":{"type":"string"}},"required":["url"]},http_post),
        ("http_headers","Get HTTP response headers for a URL",{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]},http_headers),
        ("http_status","Get HTTP status code for a URL",{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]},http_status),
        ("http_download","Download a URL to a file",{"type":"object","properties":{"url":{"type":"string"},"output_path":{"type":"string"}},"required":["url"]},http_download),
        ("url_encode","URL-encode a string",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},url_encode),
        ("url_decode","URL-decode a string",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},url_decode),
        ("url_parse","Parse URL into components",{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]},url_parse),
        ("base64_encode","Base64 encode a string",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},base64_encode),
        ("base64_decode","Base64 decode a string",{"type":"object","properties":{"encoded":{"type":"string"}},"required":["encoded"]},base64_decode),
        ("http_put","Make HTTP PUT request with JSON body",{"type":"object","properties":{"url":{"type":"string"},"data_json":{"type":"string"},"headers_json":{"type":"string"}},"required":["url"]},http_put),
        ("http_patch","Make HTTP PATCH request with JSON body",{"type":"object","properties":{"url":{"type":"string"},"data_json":{"type":"string"},"headers_json":{"type":"string"}},"required":["url"]},http_patch),
        ("http_delete","Make HTTP DELETE request",{"type":"object","properties":{"url":{"type":"string"},"headers_json":{"type":"string"}},"required":["url"]},http_delete),
    ]
    tools_data.extend(http_tools)

    # format (15)
    format_tools = [
        ("json_prettify","Prettify/format JSON string with indentation",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},json_prettify),
        ("json_minify","Minify JSON string (remove whitespace)",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},json_minify),
        ("json_to_yaml","Convert JSON to YAML",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},json_to_yaml),
        ("yaml_to_json","Convert YAML to JSON",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},yaml_to_json),
        ("xml_to_json","Convert XML to JSON",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},xml_to_json),
        ("json_to_csv","Convert JSON array to CSV",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},json_to_csv),
        ("csv_to_json_str","Convert CSV string to JSON",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},csv_to_json_str),
        ("html_escape","HTML-escape special characters",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},html_escape),
        ("html_unescape","HTML-unescape special characters",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},html_unescape),
        ("slugify","Convert text to URL-friendly slug",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},slugify),
        ("trim_whitespace","Trim and collapse whitespace",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},trim_whitespace),
        ("tab_to_spaces","Convert tabs to spaces",{"type":"object","properties":{"text":{"type":"string"},"spaces":{"type":"integer"}},"required":["text"]},tab_to_spaces),
        ("spaces_to_tabs","Convert spaces to tabs",{"type":"object","properties":{"text":{"type":"string"},"spaces":{"type":"integer"}},"required":["text"]},spaces_to_tabs),
        ("indent_text","Indent each line of text",{"type":"object","properties":{"text":{"type":"string"},"level":{"type":"integer"},"char":{"type":"string"}},"required":["text"]},indent_text),
        ("wrap_text","Wrap text to specified width",{"type":"object","properties":{"text":{"type":"string"},"width":{"type":"integer"}},"required":["text"]},wrap_text),
        ("pretty_table","Pretty-print JSON as an ASCII table",{"type":"object","properties":{"data_json":{"type":"string"}},"required":["data_json"]},pretty_table),
        ("csv_to_markdown","Convert CSV string to Markdown table",{"type":"object","properties":{"data":{"type":"string"},"delimiter":{"type":"string"}},"required":["data"]},csv_to_markdown),
        ("json_to_markdown","Convert JSON to Markdown table",{"type":"object","properties":{"data_json":{"type":"string"}},"required":["data_json"]},json_to_markdown),
        # +30 premium media tools
        ("json_sort_keys","Sort JSON keys alphabetically",{"type":"object","properties":{"data":{"type":"string"}},"required":["data"]},json_sort_keys),
        ("html_to_text","Strip HTML tags to plain text",{"type":"object","properties":{"html":{"type":"string"}},"required":["html"]},html_to_text),
        ("text_to_html","Convert plain text to basic HTML",{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},text_to_html),
        ("csv_merge","Merge two CSV strings together",{"type":"object","properties":{"data1":{"type":"string"},"data2":{"type":"string"},"delimiter":{"type":"string"}},"required":["data1","data2"]},csv_merge),
        ("csv_filter","Filter CSV rows by column value",{"type":"object","properties":{"data":{"type":"string"},"column":{"type":"string"},"value":{"type":"string"},"delimiter":{"type":"string"}},"required":["data","column","value"]},csv_filter),
        ("csv_sort","Sort CSV by column",{"type":"object","properties":{"data":{"type":"string"},"column":{"type":"string"},"reverse":{"type":"boolean"},"delimiter":{"type":"string"}},"required":["data","column"]},csv_sort),
        ("csv_columns","Analyze CSV structure (columns, row count, sample)",{"type":"object","properties":{"data":{"type":"string"},"delimiter":{"type":"string"}},"required":["data"]},csv_columns),
        ("geo_reverse_code","Reverse geocode coordinates to address",{"type":"object","properties":{"lat":{"type":"number"},"lon":{"type":"number"}},"required":["lat","lon"]},geo_reverse_code),
        ("time_to_timezone","Convert epoch timestamp to timezone-aware datetime",{"type":"object","properties":{"epoch":{"type":"number"},"tz":{"type":"string"}},"required":["epoch"]},time_to_timezone),
        ("time_list_timezones","List available IANA timezones (first 50)",{"type":"object","properties":{},"required":[]},time_list_timezones),
        ("time_sleep_ms","Sleep for given milliseconds",{"type":"object","properties":{"ms":{"type":"integer"}},"required":[]},time_sleep_ms),
        ("file_mkstemp","Create temporary file and return path",{"type":"object","properties":{"suffix":{"type":"string"},"prefix":{"type":"string"}},"required":[]},file_mkstemp),
        ("file_chmod","Change file permission mode",{"type":"object","properties":{"path":{"type":"string"},"mode":{"type":"string"}},"required":["path"]},file_chmod),
        ("file_head","Read first N lines of a file",{"type":"object","properties":{"path":{"type":"string"},"n":{"type":"integer"}},"required":["path"]},file_head),
        ("file_tail","Read last N lines of a file",{"type":"object","properties":{"path":{"type":"string"},"n":{"type":"integer"}},"required":["path"]},file_tail),
        ("file_count_lines","Count lines in a file",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_count_lines),
        ("http_head","Fetch HTTP response headers only",{"type":"object","properties":{"url":{"type":"string"},"headers_json":{"type":"string"}},"required":["url"]},http_head),
        ("http_options","Discover allowed HTTP methods via OPTIONS",{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]},http_options),
        ("url_shorten","Shorten a URL via is.gd",{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]},url_shorten),
        ("base64_encode_file","Base64 encode file contents",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},base64_encode_file),
        ("base64_decode_to_file","Decode base64 string and write to file",{"type":"object","properties":{"encoded":{"type":"string"},"path":{"type":"string"}},"required":["encoded","path"]},base64_decode_to_file),
        ("file_is_text","Check if file appears to be text",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},file_is_text),
        ("color_name_to_hex","Convert named CSS color to hex",{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},color_name_to_hex),
        ("color_hex_to_name","Convert hex color to nearest named CSS color",{"type":"object","properties":{"hex_color":{"type":"string"}},"required":["hex_color"]},color_hex_to_name),
        ("color_mix","Mix two hex colors by given ratio",{"type":"object","properties":{"c1":{"type":"string"},"c2":{"type":"string"},"ratio":{"type":"number"}},"required":["c1","c2"]},color_mix),
        ("time_countdown","Countdown from N seconds (return after sleep)",{"type":"object","properties":{"seconds":{"type":"number"}},"required":["seconds"]},time_countdown),
        ("time_stopwatch","Return start and end timestamps for timing purposes",{"type":"object","properties":{"action":{"type":"string","enum":["start","stop"]}},"required":["action"]},time_stopwatch),
        ("geo_country_name","Get country name from ISO code",{"type":"object","properties":{"code":{"type":"string"}},"required":["code"]},geo_country_name),
        ("geo_ip_to_coords","Look up approximate coordinates for an IP",{"type":"object","properties":{"ip":{"type":"string"}},"required":["ip"]},geo_ip_to_coords),
    ]
    tools_data.extend(format_tools)

    return [_make_tool(n,d,p,h,"utility") for n,d,p,h in tools_data]
