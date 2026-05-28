"""Self-healing watchdog — monitors J.A.R.V.I.S. server health, auto-restarts on failure.

Usage:
    python watchdog.py                    # Start watchdog (assumes server on port 8000)
    python watchdog.py --port 8000        # Custom port
    python watchdog.py --interval 10      # Check interval in seconds
    python watchdog.py --timeout 30       # Request timeout in seconds
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("watchdog")


class Watchdog:
    def __init__(self, port=8000, interval=10, timeout=30):
        self.port = port
        self.interval = interval
        self.timeout = timeout
        self.health_url = f"http://127.0.0.1:{port}/health"
        self.server_process = None
        self.consecutive_failures = 0
        self.max_failures = 3
        self.running = True

    def _find_server_pid(self):
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = proc.info.get("cmdline") or []
                cmd_str = " ".join(cmd).lower()
                if "uvicorn" in cmd_str and "main:app" in cmd_str:
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def _start_server(self):
        logger.info("Starting J.A.R.V.I.S. server...")
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "orchestrator.main:app",
             "--host", "0.0.0.0", "--port", str(self.port), "--reload"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.server_process = proc
        logger.info(f"Server started (PID {proc.pid})")
        return proc

    def _check_health(self):
        try:
            req = urllib.request.Request(self.health_url)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            logger.debug(f"Health check failed: {e}")
            return False

    def _stop_server(self):
        if self.server_process:
            logger.info(f"Stopping server (PID {self.server_process.pid})...")
            if sys.platform == "win32":
                self.server_process.terminate()
            else:
                os.kill(self.server_process.pid, signal.SIGTERM)
            try:
                self.server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                self.server_process.wait(timeout=5)
            self.server_process = None

    def _kill_stale_server(self):
        pid = self._find_server_pid()
        if pid:
            logger.info(f"Killing stale server (PID {pid})...")
            try:
                import psutil
                p = psutil.Process(pid)
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                logger.warning(f"Could not kill PID {pid}")

    def run(self):
        logger.info(f"Watchdog started — monitoring {self.health_url} every {self.interval}s")

        # Kill any stale instance and start fresh
        self._kill_stale_server()
        self._start_server()

        while self.running:
            time.sleep(self.interval)
            healthy = self._check_health()

            if healthy:
                self.consecutive_failures = 0
                logger.debug("Health check OK")
            else:
                self.consecutive_failures += 1
                logger.warning(f"Health check failed ({self.consecutive_failures}/{self.max_failures})")

            if self.consecutive_failures >= self.max_failures:
                logger.error(f"Server unhealthy after {self.max_failures} consecutive failures — restarting")
                self._stop_server()
                self.consecutive_failures = 0
                # Wait briefly before restart
                time.sleep(2)
                self._start_server()

    def stop(self):
        self.running = False
        self._stop_server()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Self-Healing Watchdog")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--interval", type=int, default=10, help="Health check interval in seconds (default: 10)")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds (default: 30)")
    args = parser.parse_args()

    wd = Watchdog(port=args.port, interval=args.interval, timeout=args.timeout)
    try:
        wd.run()
    except KeyboardInterrupt:
        logger.info("Watchdog stopping...")
        wd.stop()
