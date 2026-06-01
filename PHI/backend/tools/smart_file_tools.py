"""Smart File Reading with Approval System - Wrappers for secure document access."""

import json
from backend.shared.smart_permissions import permission_manager
from backend.shared.audit_logging import log_file_access
from backend.shared.document_summary import get_file_summary
from typing import Dict, Optional

def pdf_read_smart(path: str, user_id: str = "default") -> Dict:
    """
    Smart PDF read with user approval workflow.
    Returns summary first, requires approval before full read.
    """
    
    # Check rate limit
    allowed, remaining = permission_manager.check_rate_limit(user_id, "pdf_read")
    if not allowed:
        log_file_access(user_id, path, "pdf_read", "pdf", status="rate_limited")
        return {
            "status": "rate_limited",
            "message": f"Rate limit exceeded. No reads allowed in current window.",
            "remaining": remaining
        }
    
    # Get summary
    summary = get_file_summary(path)
    
    if "error" in summary:
        log_file_access(user_id, path, "pdf_read", "pdf", status="error", error=summary["error"])
        return summary
    
    # Check permission
    has_perm = permission_manager.has_permission(user_id, "pdf_read", "all")
    
    log_file_access(
        user_id, 
        path, 
        "pdf_read_summary",
        "pdf",
        status="success",
        summary=json.dumps(summary),
        approved=0
    )
    
    return {
        "status": "awaiting_approval",
        "message": "Document summary ready. User approval needed to read full content.",
        "summary": summary,
        "requires_approval": not has_perm,
        "approval_token": f"pdf_read:{user_id}:{path}"
    }

def docx_read_smart(path: str, user_id: str = "default") -> Dict:
    """
    Smart DOCX read with user approval workflow.
    Returns summary first, requires approval before full read.
    """
    
    # Check rate limit
    allowed, remaining = permission_manager.check_rate_limit(user_id, "docx_read")
    if not allowed:
        log_file_access(user_id, path, "docx_read", "docx", status="rate_limited")
        return {
            "status": "rate_limited",
            "message": f"Rate limit exceeded. No reads allowed in current window.",
            "remaining": remaining
        }
    
    # Get summary
    summary = get_file_summary(path)
    
    if "error" in summary:
        log_file_access(user_id, path, "docx_read", "docx", status="error", error=summary["error"])
        return summary
    
    # Check permission
    has_perm = permission_manager.has_permission(user_id, "docx_read", "all")
    
    log_file_access(
        user_id,
        path,
        "docx_read_summary",
        "docx",
        status="success",
        summary=json.dumps(summary),
        approved=0
    )
    
    return {
        "status": "awaiting_approval",
        "message": "Document summary ready. User approval needed to read full content.",
        "summary": summary,
        "requires_approval": not has_perm,
        "approval_token": f"docx_read:{user_id}:{path}"
    }

def file_read_smart(path: str, user_id: str = "default") -> Dict:
    """
    Smart file read with approval workflow.
    """
    
    # Check rate limit
    allowed, remaining = permission_manager.check_rate_limit(user_id, "file_read")
    if not allowed:
        log_file_access(user_id, path, "file_read", status="rate_limited")
        return {
            "status": "rate_limited",
            "message": f"Rate limit exceeded. No reads allowed in current window.",
            "remaining": remaining
        }
    
    # Get summary
    summary = get_file_summary(path)
    
    if "error" in summary:
        log_file_access(user_id, path, "file_read", status="error", error=summary["error"])
        return summary
    
    # Check permission
    has_perm = permission_manager.has_permission(user_id, "file_read", "all")
    
    log_file_access(
        user_id,
        path,
        "file_read_summary",
        status="success",
        summary=json.dumps(summary),
        approved=0
    )
    
    return {
        "status": "awaiting_approval",
        "message": "File summary ready. User approval needed to read full content.",
        "summary": summary,
        "requires_approval": not has_perm,
        "approval_token": f"file_read:{user_id}:{path}"
    }

def approve_document_read(approval_token: str, user_id: str = "default") -> Dict:
    """User approves reading full document after viewing summary."""
    
    try:
        parts = approval_token.split(":")
        operation = parts[0]  # pdf_read, docx_read, file_read
        path = ":".join(parts[2:])  # Handle paths with colons
        
        # Grant temporary permission (1 hour)
        permission_manager.grant_permission(user_id, operation, "all", duration_hours=1)
        
        log_file_access(
            user_id,
            path,
            f"{operation}_approved",
            status="success",
            approved=1
        )
        
        return {
            "status": "approved",
            "message": f"Document read approved for 1 hour.",
            "next_action": f"Call {operation}('{path}') to read full content"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def deny_document_read(approval_token: str, user_id: str = "default") -> Dict:
    """User denies reading the document."""
    
    try:
        parts = approval_token.split(":")
        operation = parts[0]
        path = ":".join(parts[2:])
        
        # Explicitly deny
        permission_manager.deny_permission(user_id, operation, "all")
        
        log_file_access(
            user_id,
            path,
            f"{operation}_denied",
            status="denied",
            approved=0
        )
        
        return {
            "status": "denied",
            "message": "Document read denied by user.",
            "path": path
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_file_reading_status(user_id: str = "default") -> Dict:
    """Get current file reading status and rate limits."""
    return {
        "user_id": user_id,
        "rate_limits": permission_manager.get_rate_limit_status(user_id),
        "permissions": permission_manager.get_user_permissions(user_id)
    }

def toggle_file_reading(user_id: str = "default", enabled: bool = True) -> Dict:
    """Toggle file reading on/off for user."""
    if enabled:
        permission_manager.grant_permission(user_id, "file_read", "all", duration_hours=None)
        permission_manager.grant_permission(user_id, "pdf_read", "all", duration_hours=None)
        permission_manager.grant_permission(user_id, "docx_read", "all", duration_hours=None)
        return {"status": "enabled", "message": "File reading enabled"}
    else:
        permission_manager.deny_permission(user_id, "file_read", "all")
        permission_manager.deny_permission(user_id, "pdf_read", "all")
        permission_manager.deny_permission(user_id, "docx_read", "all")
        return {"status": "disabled", "message": "File reading disabled"}
