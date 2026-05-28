#!/usr/bin/env python3
"""Start J.A.R.V.I.S. Agent Server"""

import sys
import subprocess

print("[JARVIS] Starting J.A.R.V.I.S. Agent Server...")
print("=" * 70)
print("Server will run on http://localhost:8000")
print("Press Ctrl+C to stop")
print("=" * 70)
print()

try:
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "backend.orchestrator.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ])
except KeyboardInterrupt:
    print("\n\n[JARVIS] Server stopped")
except Exception as e:
    print(f"[ERROR] Error starting server: {e}")
    sys.exit(1)
