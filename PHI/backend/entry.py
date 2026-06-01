"""System-wide entry point — wires all PHI AI agent subsystems into the FastAPI app.

Usage in backend/orchestrator/main.py lifespan handler:

    from backend.entry import register_all_subsystems, shutdown_all_subsystems
"""

import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def register_all_subsystems(app: FastAPI) -> None:
    """Register all subsystem routers and initialize their components."""

    # ── 1. Include subsystem routers ─────────────────────────────

    try:
        from backend.integration.routes import router as integration_router
        app.include_router(integration_router)
        logger.info("Integration router registered")
    except Exception as e:
        logger.warning("Integration router registration failed: %s", e)

    try:
        from backend.canvas.routes import router as canvas_router
        app.include_router(canvas_router)
        logger.info("Canvas router registered")
    except Exception as e:
        logger.warning("Canvas router registration failed: %s", e)

    try:
        from backend.calling.routes import router as calling_router
        app.include_router(calling_router)
        logger.info("Calling router registered")
    except Exception as e:
        logger.warning("Calling router registration failed: %s", e)

    try:
        from backend.system.routes import router as system_router
        app.include_router(system_router)
        logger.info("System router registered")
    except Exception as e:
        logger.warning("System router registration failed: %s", e)

    # ── 2. Initialize integration subsystems ─────────────────────

    try:
        from backend.integration.routes import init_subsystems
        await init_subsystems()
        logger.info("Integration subsystems initialized")
    except Exception as e:
        logger.warning("Integration subsystems init failed: %s", e)

    # ── 3. Initialize Canvas stores ──────────────────────────────

    try:
        from backend.canvas.thread_store import thread_store
        await thread_store.ensure_schema()
        logger.info("ThreadStore schema ensured")
    except Exception as e:
        logger.warning("ThreadStore init failed: %s", e)

    try:
        from backend.canvas.canvas_store import canvas_store
        await canvas_store.ensure_schema()
        logger.info("CanvasStore schema ensured")
    except Exception as e:
        logger.warning("CanvasStore init failed: %s", e)

    # ── 4. Initialize system HealthChecker ───────────────────────

    try:
        from backend.system.health import health_checker
        from backend.system.config import system_config
        health_checker.start_background(interval=system_config.health_check_interval)
        logger.info("HealthChecker background task started")
    except Exception as e:
        logger.warning("HealthChecker init failed: %s", e)

    # ── 5. Initialize system BackupManager ───────────────────────

    try:
        from backend.system.backup import backup_manager
        from backend.system.config import system_config
        backup_manager.start_background(interval_hours=system_config.backup_auto_interval_hours)
        logger.info("BackupManager auto-backup scheduler started")
    except Exception as e:
        logger.warning("BackupManager init failed: %s", e)

    # ── 6. Initialize system AlertManager ────────────────────────

    try:
        from backend.system.alerting import alert_manager
        await alert_manager.send_alert("info", "system", "All subsystems registered and initialized")
        alert_manager.start_background(after_seconds=3600)
        logger.info("AlertManager ready")
    except Exception as e:
        logger.warning("AlertManager init failed: %s", e)

    # ── 7. Start CronScheduler ───────────────────────────────────

    try:
        from backend.system.cron import cron_scheduler
        cron_scheduler.start()
        logger.info("CronScheduler started")
    except Exception as e:
        logger.warning("CronScheduler start failed: %s", e)

    logger.info("All subsystems registered and initialized")


async def shutdown_all_subsystems() -> None:
    """Gracefully shut down all subsystems in reverse dependency order."""

    # ── 1. Stop CronScheduler ────────────────────────────────────

    try:
        from backend.system.cron import cron_scheduler
        await cron_scheduler.stop()
        logger.info("CronScheduler stopped")
    except Exception as e:
        logger.warning("CronScheduler stop failed: %s", e)

    # ── 2. Stop auto-backup background task ──────────────────────

    try:
        from backend.system.backup import backup_manager
        backup_manager.stop_background()
        logger.info("BackupManager stopped")
    except Exception as e:
        logger.warning("BackupManager stop failed: %s", e)

    # ── 3. Stop health check background task ─────────────────────

    try:
        from backend.system.health import health_checker
        health_checker.stop_background()
        logger.info("HealthChecker stopped")
    except Exception as e:
        logger.warning("HealthChecker stop failed: %s", e)

    # ── 4. Stop alert auto-resolve background task ───────────────

    try:
        from backend.system.alerting import alert_manager
        alert_manager.stop_background()
        logger.info("AlertManager background stopped")
    except Exception as e:
        logger.warning("AlertManager stop failed: %s", e)

    # ── 5. Shutdown MCP runtime ──────────────────────────────────

    try:
        from backend.mcp.runtime import mcp_runtime
        await mcp_runtime.shutdown()
        logger.info("MCP runtime shutdown")
    except Exception as e:
        logger.warning("MCP runtime shutdown failed: %s", e)

    # ── 6. Stop all channels ─────────────────────────────────────

    try:
        from backend.channels.base import channel_registry
        await channel_registry.stop_all()
        logger.info("All channels stopped")
    except Exception as e:
        logger.warning("Channel stop failed: %s", e)

    # ── 7. Stop gateway server ───────────────────────────────────

    try:
        from backend.gateway.server import gateway_server
        await gateway_server.stop()
        logger.info("Gateway server stopped")
    except Exception as e:
        logger.warning("Gateway server stop failed: %s", e)

    logger.info("All subsystems shut down")
