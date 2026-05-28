"""Net tools — ping, DNS, whois, geo IP lookup."""

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def ping_host(host: str, count: int = 4) -> str:
    try:
        param = "-n" if sys.platform == "win32" else "-c"
        result = subprocess.run(
            ["ping", param, str(count), host],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout[:2000] if result.stdout else result.stderr[:2000]
    except subprocess.TimeoutExpired:
        return f"Ping to {host} timed out"
    except FileNotFoundError:
        return "Error: ping command not found"
    except Exception as e:
        return f"Ping error: {e}"


def dns_lookup(host: str, record_type: str = "A") -> str:
    try:
        import socket
        if record_type.upper() == "A":
            result = socket.getaddrinfo(host, 80)
            ips = set(r[4][0] for r in result)
            return f"DNS A records for {host}:\n" + "\n".join(f"  {ip}" for ip in ips)
        else:
            return f"DNS lookup for {record_type} records not yet supported via stdlib"
    except socket.gaierror as e:
        return f"DNS error for {host}: {e}"
    except Exception as e:
        return f"DNS lookup error: {e}"


def whois_lookup(domain: str) -> str:
    try:
        import socket
        whois_server = "whois.iana.org"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((whois_server, 43))
        sock.send(f"{domain}\r\n".encode())
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        sock.close()
        result = data.decode("utf-8", errors="replace")
        return result[:2000] if result else f"No WHOIS data for {domain}"
    except ImportError:
        return "Error: whois lookup requires socket (stdlib)"
    except Exception as e:
        return f"WHOIS error: {e}"


def geoip_lookup(ip_or_host: str) -> str:
    try:
        import urllib.request, json
        url = f"http://ip-api.com/json/{ip_or_host}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("status") == "fail":
            return f"GeoIP lookup failed: {data.get('message', 'unknown')}"
        return "\n".join(f"{k}: {v}" for k, v in data.items() if v)
    except Exception as e:
        return f"GeoIP error: {e}"
