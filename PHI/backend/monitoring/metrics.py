import asyncio
import json
import logging
import time
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)


class Counter:
    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self._value = 0
        self._lock = Lock()

    def inc(self, amount: float = 1):
        with self._lock:
            self._value += amount

    def get(self) -> float:
        with self._lock:
            return self._value

    def reset(self):
        with self._lock:
            self._value = 0


class Gauge:
    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self._value = 0.0
        self._lock = Lock()

    def set(self, value: float):
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1):
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1):
        with self._lock:
            self._value -= amount

    def get(self) -> float:
        with self._lock:
            return self._value


class Histogram:
    def __init__(self, name: str, help_text: str = "", buckets=None):
        self.name = name
        self.help_text = help_text
        self.buckets = sorted(buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0])
        self._counts = {b: 0 for b in self.buckets}
        self._counts["+Inf"] = 0
        self._sum = 0.0
        self._total_count = 0
        self._lock = Lock()

    def observe(self, value: float):
        with self._lock:
            self._sum += value
            self._total_count += 1
            for b in self.buckets:
                if value <= b:
                    self._counts[b] += 1
            self._counts["+Inf"] += 1

    def get(self) -> dict:
        with self._lock:
            return {
                "buckets": dict(self._counts),
                "sum": self._sum,
                "count": self._total_count,
            }


class MetricsCollector:
    def __init__(self):
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = Lock()

    def counter(self, name: str, help_text: str = "") -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, help_text)
            return self._counters[name]

    def gauge(self, name: str, help_text: str = "") -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, help_text)
            return self._gauges[name]

    def histogram(self, name: str, help_text: str = "", buckets=None) -> Histogram:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, help_text, buckets)
            return self._histograms[name]

    def render_prometheus(self) -> str:
        lines = []
        for c in self._counters.values():
            lines.append(f"# HELP {c.name} {c.help_text}")
            lines.append(f"# TYPE {c.name} counter")
            lines.append(f"{c.name} {c.get()}")
        for g in self._gauges.values():
            lines.append(f"# HELP {g.name} {g.help_text}")
            lines.append(f"# TYPE {g.name} gauge")
            lines.append(f"{g.name} {g.get()}")
        for h in self._histograms.values():
            lines.append(f"# HELP {h.name} {h.help_text}")
            lines.append(f"# TYPE {h.name} histogram")
            data = h.get()
            for bucket, count in data["buckets"].items():
                lines.append(f'{h.name}_bucket{{le="{bucket}"}} {count}')
            lines.append(f"{h.name}_sum {data['sum']}")
            lines.append(f"{h.name}_count {data['count']}")
        return "\n".join(lines)

    def render_json(self) -> str:
        payload = {
            "counters": {n: c.get() for n, c in self._counters.items()},
            "gauges": {n: g.get() for n, g in self._gauges.items()},
            "histograms": {n: h.get() for n, h in self._histograms.items()},
        }
        return json.dumps(payload, indent=2)


class MetricsManager:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.collector = MetricsCollector()
                    cls._instance._setup_defaults()
        return cls._instance

    def _setup_defaults(self):
        self.collector.counter("tool_calls_total", "Total number of tool calls")
        self.collector.histogram("tool_call_duration_seconds", "Tool call duration in seconds")
        self.collector.counter("messages_total", "Total number of messages processed")
        self.collector.gauge("active_sessions", "Number of currently active sessions")
        self.collector.counter("errors_total", "Total number of errors encountered")

    @property
    def tool_calls_total(self) -> Counter:
        return self.collector._counters["tool_calls_total"]

    @property
    def tool_call_duration_seconds(self) -> Histogram:
        return self.collector._histograms["tool_call_duration_seconds"]

    @property
    def messages_total(self) -> Counter:
        return self.collector._counters["messages_total"]

    @property
    def active_sessions(self) -> Gauge:
        return self.collector._gauges["active_sessions"]

    @property
    def errors_total(self) -> Counter:
        return self.collector._counters["errors_total"]

    def render_prometheus(self) -> str:
        return self.collector.render_prometheus()

    def render_json(self) -> str:
        return self.collector.render_json()


class MetricsServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 9100, manager: MetricsManager = None):
        self.host = host
        self.port = port
        self.manager = manager or MetricsManager()
        self._site = None

    async def _handle_metrics(self, request):
        content = self.manager.render_prometheus()
        return aiohttp.web.Response(text=content, content_type="text/plain; version=0.0.4")

    async def _handle_health(self, request):
        return aiohttp.web.json_response({"status": "ok"})

    async def start(self):
        import aiohttp.web

        app = aiohttp.web.Application()
        app.router.add_get("/metrics", self._handle_metrics)
        app.router.add_get("/health", self._handle_health)
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()
        self._site = aiohttp.web.TCPSite(runner, self.host, self.port)
        await self._site.start()
        logger.info("Metrics server started on %s:%s", self.host, self.port)

    async def stop(self):
        if self._site:
            await self._site.stop()
            logger.info("Metrics server stopped")
