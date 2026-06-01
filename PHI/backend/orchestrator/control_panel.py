"""Control Panel and API Endpoints - Manages user sessions, modes, approvals, and visualization."""

from fastapi import APIRouter, HTTPException, Header, Request
from backend.shared.auth_manager import auth_manager
from backend.shared.mode_manager import mode_manager
from backend.shared.voice_control import voice_processor
from backend.shared.smart_permissions import permission_manager
from backend.shared.audit_logging import get_audit_log, get_user_stats
from backend.shared.browser_manager import browser_manager, URLValidator, FileTypeValidator
from backend.shared.download_manager import download_manager
from backend.shared.subscription_tracker import subscription_manager
from backend.shared.commit_tracker import commit_tracker
from backend.shared.monitoring_service import monitoring_service, notification_manager, reminder_manager
from backend.shared.weather_tracker import weather_tracker
from backend.shared.stocks_tracker import stock_tracker
from backend.shared.news_tracker import news_tracker
from backend.shared.browser_automation import browser, permission_gate
from backend.shared.download_engine import download_engine
from backend.shared.file_converter import file_converter
from pydantic import BaseModel
from typing import Optional
import logging
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control", tags=["control"])

# Request/Response models
class SignupRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class SetModeRequest(BaseModel):
    mode: str
    duration_minutes: Optional[int] = None

class ApprovalRequest(BaseModel):
    approval_token: str

class VoiceCommandRequest(BaseModel):
    command: str
    type: str = "voice"  # voice or text

class ZoomRequest(BaseModel):
    zoom_level: int

class OpenWebsiteRequest(BaseModel):
    url: str

class QueueDownloadRequest(BaseModel):
    url: str
    filename: Optional[str] = None
    path: Optional[str] = None

class DownloadActionRequest(BaseModel):
    download_id: int
    action: str  # pause, resume, cancel

class SubscribeChannelRequest(BaseModel):
    channel_identifier: str
    platform: str = "youtube"

class AddRepositoryRequest(BaseModel):
    repo_name: str
    repo_path: str
    repo_url: Optional[str] = None

class AddTeamMemberRequest(BaseModel):
    member_name: str
    member_email: str
    github_username: Optional[str] = None

class SubscribeWeatherRequest(BaseModel):
    city: str
    country_code: Optional[str] = None
    alert_level: str = 'HIGH'

class SubscribeStockRequest(BaseModel):
    symbol: str
    alert_threshold: float = 2.0

class SubscribeNewsRequest(BaseModel):
    topic: str
    keywords: Optional[list] = None

class UnsubscribeWeatherRequest(BaseModel):
    city: str

class UnsubscribeStockRequest(BaseModel):
    symbol: str

class UnsubscribeNewsRequest(BaseModel):
    topic: str

# ===================== BROWSER AUTOMATION MODELS =====================

class BrowserNavigateRequest(BaseModel):
    url: str
    wait_until: str = 'domcontentloaded'
    require_approval: bool = True

class BrowserClickRequest(BaseModel):
    selector: str
    require_approval: bool = True

class BrowserTypeRequest(BaseModel):
    selector: str
    text: str

class BrowserFillFormRequest(BaseModel):
    fields: dict

class BrowserLoginRequest(BaseModel):
    url: str
    username_selector: str
    password_selector: str
    username: str
    password: str
    submit_selector: Optional[str] = None
    save_session: bool = True
    require_approval: bool = True

class BrowserSelectRequest(BaseModel):
    selector: str
    value: str

class BrowserScrollRequest(BaseModel):
    direction: str = 'down'
    amount: int = 500

class ApprovalRequest(BaseModel):
    token: str
    approve: bool = True

class SetBandwidthRequest(BaseModel):
    mbps: float

class SetConcurrencyRequest(BaseModel):
    max_concurrent: int

class FileConvertRequest(BaseModel):
    file_path: str
    url: Optional[str] = None

# ===================== BROWSER AUTOMATION ENDPOINTS =====================

@router.post("/browser/navigate")
async def browser_navigate(req: BrowserNavigateRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    if req.require_approval:
        approval = permission_gate.request_approval(user_id, "navigate", req.url)
        if not permission_gate.wait_for_approval(user_id, approval['token']):
            raise HTTPException(status_code=403, detail="Navigation denied by user")
    result = await browser.navigate(user_id, req.url, req.wait_until)
    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result['message'])
    return result

@router.post("/browser/click")
async def browser_click(req: BrowserClickRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    if req.require_approval:
        approval = permission_gate.request_approval(user_id, "click", req.selector)
        if not permission_gate.wait_for_approval(user_id, approval['token']):
            raise HTTPException(status_code=403, detail="Click denied by user")
    result = await browser.click(user_id, req.selector)
    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result['message'])
    return result

@router.post("/browser/type")
async def browser_type(req: BrowserTypeRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = await browser.type_text(user_id, req.selector, req.text)
    return result

@router.post("/browser/fill-form")
async def browser_fill_form(req: BrowserFillFormRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = await browser.fill_form(user_id, req.fields)
    return result

@router.post("/browser/login")
async def browser_login(req: BrowserLoginRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    if req.require_approval:
        approval = permission_gate.request_approval(user_id, "login", req.url)
        if not permission_gate.wait_for_approval(user_id, approval['token']):
            raise HTTPException(status_code=403, detail="Login denied by user")
    result = await browser.login(user_id, req.url, req.username_selector, req.password_selector, req.username, req.password, req.submit_selector, req.save_session)
    return result

@router.post("/browser/screenshot")
async def browser_screenshot(full_page: bool = True, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    approval = permission_gate.request_approval(user_id, "screenshot", "current page")
    if not permission_gate.wait_for_approval(user_id, approval['token']):
        raise HTTPException(status_code=403, detail="Screenshot denied by user")
    result = await browser.take_screenshot(user_id, full_page)
    return result

@router.get("/browser/content")
async def browser_content(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = await browser.get_page_content(user_id)
    return result

@router.post("/browser/select")
async def browser_select(req: BrowserSelectRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = await browser.select_option(user_id, req.selector, req.value)
    return result

@router.post("/browser/scroll")
async def browser_scroll(req: BrowserScrollRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = await browser.scroll(user_id, req.direction, req.amount)
    return result

@router.post("/browser/back")
async def browser_back(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = await browser.go_back(user_id)
    return result

@router.post("/browser/forward")
async def browser_forward(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = await browser.go_forward(user_id)
    return result

@router.get("/browser/cookies")
async def browser_cookies(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = await browser.get_cookies(user_id)
    return result

@router.post("/browser/session/save")
async def browser_save_session(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    success = await browser.save_session(user_id)
    return {'success': success}

@router.post("/browser/session/load")
async def browser_load_session(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    success = await browser.load_session(user_id)
    return {'success': success}

@router.get("/browser/actions")
async def browser_action_history(limit: int = 50, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    history = browser.get_action_history(user_id, limit)
    return {'actions': history, 'count': len(history)}

# ===================== APPROVAL ENDPOINTS =====================

@router.post("/approve")
async def approve_action(req: ApprovalRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    if req.approve:
        success = permission_gate.approve(user_id, req.token)
    else:
        success = permission_gate.deny(user_id, req.token)
    return {'success': success, 'action': 'approved' if req.approve else 'denied'}

@router.get("/approve/pending")
async def get_pending_approvals(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    pending = permission_gate.get_pending(user_id)
    return {'pending': pending, 'count': len(pending)}

# ===================== REAL DOWNLOAD ENGINE ENDPOINTS =====================

@router.post("/downloads/real/queue")
async def real_download_queue(req: QueueDownloadRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = download_engine.queue_download(user_id, req.url, req.filename, req.path)
    return result

@router.get("/downloads/real/list")
async def real_download_list(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    downloads = download_engine.list_downloads(user_id)
    return {'downloads': downloads, 'count': len(downloads)}

@router.get("/downloads/real/{download_id}")
async def real_download_status(download_id: int, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = download_engine.get_status(download_id)
    return result

@router.post("/downloads/real/pause")
async def real_download_pause(req: DownloadActionRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = download_engine.pause(req.download_id)
    return result

@router.post("/downloads/real/resume")
async def real_download_resume(req: DownloadActionRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = download_engine.resume(req.download_id)
    return result

@router.post("/downloads/real/cancel")
async def real_download_cancel(req: DownloadActionRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = download_engine.cancel(req.download_id)
    return result

@router.get("/downloads/real/stats")
async def real_download_stats(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    stats = download_engine.get_stats()
    return stats

@router.post("/downloads/real/bandwidth")
async def set_bandwidth(req: SetBandwidthRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    download_engine.set_bandwidth(req.mbps)
    return {'success': True, 'max_bandwidth_mbps': req.mbps}

@router.post("/downloads/real/concurrency")
async def set_concurrency(req: SetConcurrencyRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    download_engine.set_concurrency(req.max_concurrent)
    return {'success': True, 'max_concurrent': req.max_concurrent}

# ===================== FILE CONVERTER ENDPOINTS =====================

@router.post("/convert/file")
async def convert_file(req: FileConvertRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    result = file_converter.convert(req.file_path, user_id)
    return result

@router.post("/convert/url")
async def convert_url(req: FileConvertRequest, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    if not req.url:
        raise HTTPException(status_code=400, detail="URL required")
    result = file_converter.convert_url(req.url, user_id)
    return result

@router.get("/convert/formats")
async def get_convert_formats(authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    formats = file_converter.get_supported_formats()
    return {'formats': formats, 'count': len(formats)}

@router.get("/convert/history")
async def get_convert_history(limit: int = 20, authorization: Optional[str] = Header(None)):
    user_id, username, token = verify_token(authorization)
    history = file_converter.list_conversions(user_id, limit)
    return {'conversions': history, 'count': len(history)}

# Helper function for auth verification
def verify_token(authorization: Optional[str] = Header(None)) -> tuple:
    """Verify bearer token and return (user_id, username)."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization.replace("Bearer ", "").strip()
    is_valid, user_id, username = auth_manager.verify_session(token)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user_id, username, token

# ===================== AUTH ENDPOINTS =====================

@router.post("/signup")
async def signup(req: SignupRequest):
    """Register new user."""
    success, message, user_data = auth_manager.signup(req.username, req.email, req.password)
    
    if success:
        return {"success": True, "message": message, "user": user_data}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """User login."""
    ip_address = request.client.host
    success, message, session_data = auth_manager.login(req.username, req.password, ip_address)
    
    if success:
        return {"success": True, "message": message, "session": session_data}
    else:
        raise HTTPException(status_code=401, detail=message)

@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """User logout."""
    user_id, username, token = verify_token(authorization)
    auth_manager.logout(token)
    return {"success": True, "message": "Logged out successfully"}

# ===================== MODE ENDPOINTS =====================

@router.get("/modes")
async def list_modes(authorization: Optional[str] = Header(None)):
    """List available modes."""
    user_id, username, token = verify_token(authorization)
    modes = mode_manager.list_available_modes()
    current = mode_manager.get_current_mode(user_id)
    
    return {
        "available_modes": modes,
        "current_mode": current
    }

@router.post("/modes/set")
async def set_mode(req: SetModeRequest, authorization: Optional[str] = Header(None)):
    """Set user mode."""
    user_id, username, token = verify_token(authorization)
    success, message = mode_manager.set_mode(user_id, req.mode, req.duration_minutes)
    
    if success:
        return {
            "success": True,
            "message": message,
            "current_mode": mode_manager.get_current_mode(user_id)
        }
    else:
        raise HTTPException(status_code=400, detail=message)

@router.post("/modes/exit")
async def exit_mode(authorization: Optional[str] = Header(None)):
    """Exit special mode."""
    user_id, username, token = verify_token(authorization)
    success, message = mode_manager.exit_mode(user_id)
    
    if success:
        return {
            "success": True,
            "message": message,
            "current_mode": mode_manager.get_current_mode(user_id)
        }
    else:
        raise HTTPException(status_code=400, detail=message)

# ===================== DOCUMENT APPROVAL ENDPOINTS =====================

@router.post("/documents/summary")
async def get_document_summary(req: dict, authorization: Optional[str] = Header(None)):
    """Get document summary for approval."""
    user_id, username, token = verify_token(authorization)
    file_path = req.get('path', '')
    
    if not file_path:
        raise HTTPException(status_code=400, detail="No file path provided")
    
    summary = get_file_summary(file_path)
    
    if "error" in summary:
        raise HTTPException(status_code=400, detail=summary["error"])
    
    return summary

@router.post("/documents/approve")
async def approve_document(req: ApprovalRequest, authorization: Optional[str] = Header(None)):
    """Approve document for full reading."""
    user_id, username, token = verify_token(authorization)
    
    if not req.approval_token:
        raise HTTPException(status_code=400, detail="No approval token provided")
    
    # Process approval
    permission_manager.grant_permission(str(user_id), "file_read", "all", duration_hours=1)
    voice_processor.clear_pending_approval(req.approval_token)
    
    return {
        "success": True,
        "message": "Document approved for reading",
        "approval_token": req.approval_token
    }

@router.post("/documents/deny")
async def deny_document(req: ApprovalRequest, authorization: Optional[str] = Header(None)):
    """Deny document reading."""
    user_id, username, token = verify_token(authorization)
    
    if not req.approval_token:
        raise HTTPException(status_code=400, detail="No approval token provided")
    
    voice_processor.clear_pending_approval(req.approval_token)
    
    return {
        "success": True,
        "message": "Document reading denied",
        "approval_token": req.approval_token
    }

# ===================== WEB BROWSING ENDPOINTS =====================

@router.post("/browser/open")
async def open_website(req: OpenWebsiteRequest, authorization: Optional[str] = Header(None), request: Request = None):
    """Open a website and log the visit."""
    user_id, username, token = verify_token(authorization)
    ip_address = request.client.host if request else "local"
    
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="No URL provided")
    
    # Validate URL
    is_valid, msg = URLValidator.is_valid_url(req.url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {msg}")
    
    result = browser_manager.open_website(user_id, req.url, ip_address)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.get("/browser/history")
async def get_browser_history(hours: int = 24, limit: int = 50, authorization: Optional[str] = Header(None)):
    """Get user's browser history."""
    user_id, username, token = verify_token(authorization)
    history = browser_manager.get_browser_history(user_id, hours, limit)
    
    return {
        "user_id": user_id,
        "hours": hours,
        "count": len(history),
        "history": history
    }

# ===================== DOWNLOAD ENDPOINTS =====================

@router.post("/downloads/queue")
async def queue_download(req: QueueDownloadRequest, authorization: Optional[str] = Header(None)):
    """Queue a file for download."""
    user_id, username, token = verify_token(authorization)
    
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="No URL provided")
    
    # Queue the download
    success, message, result = browser_manager.queue_download(user_id, req.url, req.filename, req.path)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Add to download manager
    if result:
        download_manager.add_download(
            result["download_id"],
            user_id,
            result["url"],
            result["path"],
            result["filename"]
        )
    
    return {
        "success": True,
        "message": message,
        "download": result
    }

@router.get("/downloads/list")
async def list_downloads(status: Optional[str] = None, limit: int = 50, authorization: Optional[str] = Header(None)):
    """Get user's downloads."""
    user_id, username, token = verify_token(authorization)
    downloads = browser_manager.get_downloads(user_id, status, limit)
    
    return {
        "user_id": user_id,
        "status_filter": status,
        "count": len(downloads),
        "downloads": downloads
    }

@router.get("/downloads/status/{download_id}")
async def get_download_status(download_id: int, authorization: Optional[str] = Header(None)):
    """Get status of a specific download."""
    user_id, username, token = verify_token(authorization)
    
    status = download_manager.get_download_status(download_id)
    
    if status.get("status") == "error":
        raise HTTPException(status_code=404, detail="Download not found")
    
    return status

@router.post("/downloads/action")
async def download_action(req: DownloadActionRequest, authorization: Optional[str] = Header(None)):
    """Perform action on download (pause, resume, cancel)."""
    user_id, username, token = verify_token(authorization)
    
    action = req.action.lower()
    
    if action == "pause":
        result = download_manager.pause_download(req.download_id)
    elif action == "resume":
        result = download_manager.resume_download(req.download_id)
    elif action == "cancel":
        result = download_manager.cancel_download(req.download_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result

@router.get("/downloads/queue")
async def get_download_queue(authorization: Optional[str] = Header(None)):
    """Get download queue information."""
    user_id, username, token = verify_token(authorization)
    queue_info = download_manager.get_queue_info()
    
    return queue_info

@router.get("/downloads/stats")
async def get_download_stats(hours: int = 24, authorization: Optional[str] = Header(None)):
    """Get download statistics."""
    user_id, username, token = verify_token(authorization)
    stats = browser_manager.get_download_stats(user_id, hours)
    
    return {
        "user_id": user_id,
        "hours": hours,
        "stats": stats
    }

@router.get("/browser/safe-types")
async def get_safe_file_types(authorization: Optional[str] = Header(None)):
    """Get list of safe file types for download."""
    user_id, username, token = verify_token(authorization)
    safe_types = FileTypeValidator.list_safe_types()
    
    return {
        "safe_file_types": safe_types,
        "dangerous_types": FileTypeValidator.DANGEROUS_TYPES
    }

@router.get("/browser/safe-types")
async def get_safe_file_types(authorization: Optional[str] = Header(None)):
    """Get list of safe file types for download."""
    user_id, username, token = verify_token(authorization)
    safe_types = FileTypeValidator.list_safe_types()
    
    return {
        "safe_file_types": safe_types,
        "dangerous_types": FileTypeValidator.DANGEROUS_TYPES
    }

# ===================== VIDEO SUBSCRIPTION ENDPOINTS =====================

@router.post("/subscriptions/subscribe")
async def subscribe_channel(req: SubscribeChannelRequest, authorization: Optional[str] = Header(None)):
    """Subscribe to a video channel."""
    user_id, username, token = verify_token(authorization)
    
    success, message, result = subscription_manager.subscribe_to_channel(
        user_id, req.channel_identifier, req.platform
    )
    
    if success:
        return {"success": True, "message": message, "subscription": result}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/subscriptions/list")
async def list_subscriptions(authorization: Optional[str] = Header(None)):
    """Get user's channel subscriptions."""
    user_id, username, token = verify_token(authorization)
    subs = subscription_manager.get_user_subscriptions(user_id)
    
    return {
        "user_id": user_id,
        "subscriptions": subs,
        "count": len(subs)
    }

@router.post("/subscriptions/unsubscribe")
async def unsubscribe_channel(channel_id: str, authorization: Optional[str] = Header(None)):
    """Unsubscribe from a channel."""
    user_id, username, token = verify_token(authorization)
    success, message = subscription_manager.unsubscribe_from_channel(user_id, channel_id)
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/videos/recent")
async def get_recent_videos(hours: int = 24, limit: int = 20, authorization: Optional[str] = Header(None)):
    """Get recent uploads from subscribed channels."""
    user_id, username, token = verify_token(authorization)
    videos = subscription_manager.get_recent_uploads(user_id, hours, limit)
    
    return {
        "user_id": user_id,
        "hours": hours,
        "videos": videos,
        "count": len(videos)
    }

@router.get("/videos/unwatched")
async def get_unwatched_videos(authorization: Optional[str] = Header(None)):
    """Get unwatched videos."""
    user_id, username, token = verify_token(authorization)
    videos = subscription_manager.get_unwatched_videos(user_id)
    
    return {
        "user_id": user_id,
        "unwatched_videos": videos,
        "count": len(videos)
    }

@router.post("/videos/mark-watched")
async def mark_video_watched(video_id: str, authorization: Optional[str] = Header(None)):
    """Mark video as watched."""
    user_id, username, token = verify_token(authorization)
    success = subscription_manager.mark_video_watched(user_id, video_id)
    
    if success:
        return {"success": True, "message": "Video marked as watched"}
    else:
        raise HTTPException(status_code=400, detail="Failed to mark video watched")

# ===================== GIT COMMIT ENDPOINTS =====================

@router.post("/repos/add")
async def add_repository(req: AddRepositoryRequest, authorization: Optional[str] = Header(None)):
    """Add a git repository to monitor."""
    user_id, username, token = verify_token(authorization)
    success, message = commit_tracker.add_repository(
        user_id, req.repo_name, req.repo_path, req.repo_url
    )
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/repos/list")
async def list_repositories(authorization: Optional[str] = Header(None)):
    """Get tracked repositories."""
    user_id, username, token = verify_token(authorization)
    repos = commit_tracker.get_repositories(user_id)
    
    return {
        "user_id": user_id,
        "repositories": repos,
        "count": len(repos)
    }

@router.post("/team/add-member")
async def add_team_member(req: AddTeamMemberRequest, authorization: Optional[str] = Header(None)):
    """Add a team member to track."""
    user_id, username, token = verify_token(authorization)
    success, message = commit_tracker.add_team_member(
        user_id, req.member_name, req.member_email, req.github_username
    )
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/team/members")
async def list_team_members(authorization: Optional[str] = Header(None)):
    """Get tracked team members."""
    user_id, username, token = verify_token(authorization)
    members = commit_tracker.get_team_members(user_id)
    
    return {
        "user_id": user_id,
        "team_members": members,
        "count": len(members)
    }

@router.get("/commits/recent")
async def get_recent_commits(days: int = 7, limit: int = 20, authorization: Optional[str] = Header(None)):
    """Get recent commits from team members."""
    user_id, username, token = verify_token(authorization)
    commits = commit_tracker.get_recent_commits(user_id, days, limit)
    
    return {
        "user_id": user_id,
        "days": days,
        "commits": commits,
        "count": len(commits)
    }

@router.get("/commits/team-activity")
async def get_team_activity(days: int = 7, authorization: Optional[str] = Header(None)):
    """Get team activity summary."""
    user_id, username, token = verify_token(authorization)
    activity = commit_tracker.get_team_activity(user_id, days)
    
    return {
        "user_id": user_id,
        "days": days,
        "activity": activity
    }

@router.get("/commits/member/{member_name}")
async def get_member_commits(member_name: str, days: int = 7, limit: int = 20, authorization: Optional[str] = Header(None)):
    """Get commits from a specific team member."""
    user_id, username, token = verify_token(authorization)
    commits = commit_tracker.get_member_commits(user_id, member_name, days, limit)
    
    return {
        "member_name": member_name,
        "commits": commits,
        "count": len(commits)
    }

# ===================== NOTIFICATIONS & REMINDERS =====================

@router.get("/notifications")
async def get_notifications(unread_only: bool = False, limit: int = 50, authorization: Optional[str] = Header(None)):
    """Get user notifications."""
    user_id, username, token = verify_token(authorization)
    notifications = notification_manager.get_notifications(user_id, unread_only, limit)
    
    return {
        "user_id": user_id,
        "notifications": notifications,
        "count": len(notifications),
        "unread_count": notification_manager.get_unread_count(user_id)
    }

@router.post("/notifications/mark-read")
async def mark_notification_read(notification_id: int, authorization: Optional[str] = Header(None)):
    """Mark notification as read."""
    user_id, username, token = verify_token(authorization)
    success = notification_manager.mark_notification_read(notification_id)
    
    if success:
        return {"success": True, "message": "Notification marked as read"}
    else:
        raise HTTPException(status_code=400, detail="Failed to mark notification read")

@router.get("/reminders")
async def get_reminders(authorization: Optional[str] = Header(None)):
    """Get pending reminders."""
    user_id, username, token = verify_token(authorization)
    reminders = reminder_manager.get_pending_reminders(user_id)
    
    return {
        "user_id": user_id,
        "reminders": reminders,
        "count": len(reminders)
    }

@router.post("/reminders/complete")
async def complete_reminder(reminder_id: int, authorization: Optional[str] = Header(None)):
    """Mark reminder as complete."""
    user_id, username, token = verify_token(authorization)
    success = reminder_manager.complete_reminder(reminder_id)
    
    if success:
        return {"success": True, "message": "Reminder marked as complete"}
    else:
        raise HTTPException(status_code=400, detail="Failed to complete reminder")

@router.get("/summary")
async def get_activity_summary(authorization: Optional[str] = Header(None)):
    """Get complete activity summary for user."""
    user_id, username, token = verify_token(authorization)
    summary = monitoring_service.get_user_summary(user_id)
    
    return summary

# ===================== WEATHER MONITORING ENDPOINTS =====================

@router.post("/weather/subscribe")
async def subscribe_weather(req: SubscribeWeatherRequest, authorization: Optional[str] = Header(None)):
    """Subscribe to weather alerts for a location."""
    user_id, username, token = verify_token(authorization)
    success, message = weather_tracker.subscribe_to_location(
        user_id, req.city, req.country_code, req.alert_level
    )
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/weather/list")
async def list_weather_subscriptions(authorization: Optional[str] = Header(None)):
    """List weather subscriptions."""
    user_id, username, token = verify_token(authorization)
    subs = weather_tracker.get_subscriptions(user_id)
    return {
        "user_id": user_id,
        "subscriptions": subs,
        "count": len(subs)
    }

@router.post("/weather/unsubscribe")
async def unsubscribe_weather_endpoint(req: UnsubscribeWeatherRequest, authorization: Optional[str] = Header(None)):
    """Unsubscribe from weather alerts."""
    user_id, username, token = verify_token(authorization)
    success, message = weather_tracker.unsubscribe(user_id, req.city)
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

# ===================== STOCK MONITORING ENDPOINTS =====================

@router.post("/stocks/subscribe")
async def subscribe_stock(req: SubscribeStockRequest, authorization: Optional[str] = Header(None)):
    """Subscribe to stock price alerts."""
    user_id, username, token = verify_token(authorization)
    success, message = stock_tracker.subscribe_to_stock(
        user_id, req.symbol, req.alert_threshold
    )
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/stocks/list")
async def list_stock_subscriptions(authorization: Optional[str] = Header(None)):
    """List stock subscriptions."""
    user_id, username, token = verify_token(authorization)
    subs = stock_tracker.get_subscriptions(user_id)
    return {
        "user_id": user_id,
        "subscriptions": subs,
        "count": len(subs)
    }

@router.post("/stocks/unsubscribe")
async def unsubscribe_stock_endpoint(req: UnsubscribeStockRequest, authorization: Optional[str] = Header(None)):
    """Unsubscribe from stock alerts."""
    user_id, username, token = verify_token(authorization)
    success, message = stock_tracker.unsubscribe(user_id, req.symbol)
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/stocks/popular")
async def get_popular_stocks_list(limit: int = 10, authorization: Optional[str] = Header(None)):
    """Get popular/active stocks list."""
    user_id, username, token = verify_token(authorization)
    stocks = stock_tracker.get_popular_stocks(limit)
    return {
        "stocks": stocks,
        "count": len(stocks)
    }

# ===================== NEWS MONITORING ENDPOINTS =====================

@router.post("/news/subscribe")
async def subscribe_news(req: SubscribeNewsRequest, authorization: Optional[str] = Header(None)):
    """Subscribe to news topics."""
    user_id, username, token = verify_token(authorization)
    success, message = news_tracker.subscribe_to_topic(
        user_id, req.topic, req.keywords
    )
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/news/list")
async def list_news_subscriptions(authorization: Optional[str] = Header(None)):
    """List news subscriptions."""
    user_id, username, token = verify_token(authorization)
    subs = news_tracker.get_subscriptions(user_id)
    return {
        "user_id": user_id,
        "subscriptions": subs,
        "count": len(subs)
    }

@router.post("/news/unsubscribe")
async def unsubscribe_news_endpoint(req: UnsubscribeNewsRequest, authorization: Optional[str] = Header(None)):
    """Unsubscribe from news topic."""
    user_id, username, token = verify_token(authorization)
    success, message = news_tracker.unsubscribe(user_id, req.topic)
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)

@router.get("/news/breaking")
async def get_breaking_news_list(limit: int = 10, authorization: Optional[str] = Header(None)):
    """Get breaking news headlines."""
    user_id, username, token = verify_token(authorization)
    news = news_tracker.get_breaking_news(limit)
    return {
        "news": news,
        "count": len(news)
    }

# ===================== VOICE COMMAND ENDPOINTS =====================

@router.post("/voice/command")
async def process_voice_command(req: VoiceCommandRequest, authorization: Optional[str] = Header(None)):
    """Process voice command."""
    user_id, username, token = verify_token(authorization)
    
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="No command provided")
    
    if req.type == 'voice':
        result = voice_processor.process_voice_command(req.command, str(user_id))
    else:
        result = voice_processor.process_text_command(req.command, str(user_id))
    
    return result

# ===================== CONTROL ENDPOINTS =====================

@router.post("/exit-all")
async def exit_all_systems(authorization: Optional[str] = Header(None)):
    """Exit all systems and logout."""
    user_id, username, token = verify_token(authorization)
    
    # Exit any special mode
    mode_manager.exit_mode(user_id)
    
    # Logout
    auth_manager.logout(token)
    
    return {
        "success": True,
        "message": "All systems exited and logged out",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/zoom")
async def set_zoom(req: ZoomRequest, authorization: Optional[str] = Header(None)):
    """Set zoom level."""
    user_id, username, token = verify_token(authorization)
    
    if req.zoom_level < 50 or req.zoom_level > 300:
        raise HTTPException(status_code=400, detail="Zoom level must be between 50 and 300")
    
    return {
        "success": True,
        "zoom_level": req.zoom_level,
        "message": f"Zoom set to {req.zoom_level}%"
    }

# ===================== ANALYTICS & VISUALIZATION =====================

@router.get("/stats")
async def get_stats(hours: int = 24, authorization: Optional[str] = Header(None)):
    """Get user statistics."""
    user_id, username, token = verify_token(authorization)
    stats = get_user_stats(str(user_id), hours)
    
    return {
        "user_id": user_id,
        "username": username,
        "stats": stats
    }

@router.get("/audit-log")
async def get_audit(hours: int = 24, limit: int = 50, authorization: Optional[str] = Header(None)):
    """Get audit log for user."""
    user_id, username, token = verify_token(authorization)
    logs = get_audit_log(str(user_id), hours, limit)
    
    return {
        "user_id": user_id,
        "logs": logs
    }

@router.get("/permissions")
async def get_permissions(authorization: Optional[str] = Header(None)):
    """Get user permissions."""
    user_id, username, token = verify_token(authorization)
    permissions = permission_manager.get_user_permissions(str(user_id))
    rate_limits = permission_manager.get_rate_limit_status(str(user_id))
    
    return {
        "permissions": permissions,
        "rate_limits": rate_limits
    }

def register_control_blueprint(app):
    """Register control panel router with FastAPI app."""
    app.include_router(router)
    logger.info("Control panel router registered")
