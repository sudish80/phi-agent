"""Debug launcher — captures full output."""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("launcher")

try:
    logger.info("Starting uvicorn...")
    import uvicorn
    uvicorn.run(
        "backend.orchestrator.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
except Exception as e:
    logger.error(f"FATAL: {e}", exc_info=True)
    sys.exit(1)
