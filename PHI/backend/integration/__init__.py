"""Integration module — wires new subsystems into the FastAPI app."""

from backend.integration.routes import router, init_subsystems

__all__ = ["router", "init_subsystems"]
