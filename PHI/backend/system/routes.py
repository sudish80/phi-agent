"""FastAPI routes for system management: health checks, backup/recovery,
configuration, alerts, and comprehensive status."""

import logging
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Query

from backend.system.health import HealthChecker, CheckStatus
from backend.system.backup import BackupManager
from backend.system.config import SystemConfig, load_from_env, save_to_env, system_config
from backend.system.alerting import AlertManager, AlertSeverity

logger = logging.getLogger(__name__)

router = APIRouter()

health_checker = HealthChecker()
backup_manager = BackupManager()
alert_manager = AlertManager()

SECRET_KEYS = {"openai_api_key", "anthropic_api_key", "nvidia_api_key",
               "google_api_key", "jwt_secret"}


def _redact_secrets(cfg: Dict[str, Any]) -> Dict[str, Any]:
    redacted = {}
    for k, v in cfg.items():
        if k in SECRET_KEYS and v:
            redacted[k] = v[:8] + "****" if len(v) > 8 else "****"
        else:
            redacted[k] = v
    return redacted


@router.get("/api/system/health")
async def full_health_check():
    results = await health_checker.full_check()
    return {
        "status": "ok",
        "checks": [
            {
                "name": r.name,
                "status": r.status.value,
                "detail": r.detail,
                "duration_ms": round(r.duration_ms, 2),
            }
            for r in results
        ],
    }


@router.get("/api/system/health/{component}")
async def component_health_check(component: str):
    result = await health_checker.run_check(component)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown health component: {component}")
    return {
        "name": result.name,
        "status": result.status.value,
        "detail": result.detail,
        "duration_ms": round(result.duration_ms, 2),
    }


@router.get("/api/system/health/summary")
async def health_summary():
    return health_checker.summary()


@router.post("/api/system/backup")
async def create_backup(payload: Optional[Dict[str, str]] = None):
    label = (payload or {}).get("label", "")
    backup_id = await backup_manager.create_backup(label=label)
    return {"backup_id": backup_id, "status": "created"}


@router.get("/api/system/backups")
async def list_backups():
    records = backup_manager.list_backups()
    return {
        "backups": [
            {
                "id": r.id,
                "timestamp": r.timestamp,
                "label": r.label,
                "size_bytes": r.size_bytes,
                "size_mb": round(r.size_bytes / (1024 * 1024), 2),
                "file_count": r.file_count,
            }
            for r in records
        ],
        "total": len(records),
    }


@router.post("/api/system/backups/{backup_id}/restore")
async def restore_backup(backup_id: str, payload: Optional[Dict[str, Any]] = None):
    dry_run = (payload or {}).get("dry_run", False)
    try:
        result = backup_manager.restore_backup(backup_id, dry_run=dry_run)
        return {"status": "restored" if not dry_run else "dry_run", **result}
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Restore failed for %s", backup_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/system/backups/{backup_id}")
async def delete_backup(backup_id: str):
    success = backup_manager.delete_backup(backup_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Backup {backup_id} not found")
    return {"status": "deleted", "backup_id": backup_id}


@router.get("/api/system/config")
async def get_config():
    return _redact_secrets(system_config.to_dict())


@router.put("/api/system/config")
async def update_config(payload: Dict[str, Any]):
    global system_config
    updated = system_config.to_dict()
    for k, v in payload.items():
        if k in SECRET_KEYS and v and v.endswith("****"):
            continue
        if k in updated:
            updated[k] = v
    system_config = SystemConfig.from_dict(updated)
    save_to_env(system_config)
    return {"status": "updated", "config": _redact_secrets(system_config.to_dict())}


@router.get("/api/system/alerts")
async def get_alerts(
    severity: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    since: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    sev = AlertSeverity(severity) if severity else None
    alerts = alert_manager.get_alerts(
        severity=sev, source=source, since=since,
        resolved=resolved, limit=limit,
    )
    return {
        "alerts": [a.to_dict() for a in alerts],
        "total": len(alerts),
        "unresolved": len(alert_manager.get_unresolved()),
    }


@router.post("/api/system/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    success = alert_manager.acknowledge(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"status": "acknowledged", "alert_id": alert_id}


@router.post("/api/system/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    success = alert_manager.resolve(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"status": "resolved", "alert_id": alert_id}


@router.post("/api/system/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str):
    success = alert_manager.dismiss(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"status": "dismissed", "alert_id": alert_id}


@router.get("/api/system/status")
async def comprehensive_status():
    health_results = await health_checker.full_check()
    health_summary_data = health_checker.summary()
    alerts = alert_manager.get_unresolved()
    backups = backup_manager.list_backups()
    return {
        "status": health_summary_data["status"],
        "uptime": None,
        "health": {
            "summary": health_summary_data,
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "detail": r.detail,
                    "duration_ms": round(r.duration_ms, 2),
                }
                for r in health_results
            ],
        },
        "config": _redact_secrets(system_config.to_dict()),
        "alerts": {
            "unresolved_count": len(alerts),
            "unresolved": [a.to_dict() for a in alerts[:20]],
        },
        "backups": {
            "total": len(backups),
            "latest": backups[0].to_dict() if backups else None,
        },
    }
