"""Launcher for the full PHI Agent server."""
import uvicorn
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

if __name__ == "__main__":
    uvicorn.run(
        "backend.orchestrator.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
