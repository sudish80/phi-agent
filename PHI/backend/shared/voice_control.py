"""Voice Control System - Process voice commands for approvals/denials."""

import json
import logging
from typing import Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class VoiceCommandProcessor:
    """Process voice commands for document approvals and control."""
    
    APPROVAL_KEYWORDS = ["approve", "yes", "okay", "ok", "allow", "proceed", "go ahead", "sure"]
    DENIAL_KEYWORDS = ["deny", "no", "reject", "don't", "cancel", "stop", "nope", "blocked"]
    
    EXIT_KEYWORDS = ["exit", "quit", "close", "stop all", "end session", "logout"]
    ZOOM_KEYWORDS = ["zoom", "magnify", "enlarge", "bigger", "increase scale"]
    RESET_ZOOM_KEYWORDS = ["reset zoom", "normal size", "original size", "zoom out"]
    
    def __init__(self):
        self.pending_approvals = {}
        self.last_command_time = {}
    
    def process_voice_command(self, command: str, user_id: str) -> Dict:
        """Process voice command and return action."""
        command_lower = command.lower().strip()
        
        # Check for approval
        if any(keyword in command_lower for keyword in self.APPROVAL_KEYWORDS):
            return {
                "status": "success",
                "action": "approve",
                "command": command,
                "message": "Document read approved",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Check for denial
        if any(keyword in command_lower for keyword in self.DENIAL_KEYWORDS):
            return {
                "status": "success",
                "action": "deny",
                "command": command,
                "message": "Document read denied",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Check for exit
        if any(keyword in command_lower for keyword in self.EXIT_KEYWORDS):
            return {
                "status": "success",
                "action": "exit",
                "command": command,
                "message": "Exiting all systems",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Check for zoom
        if any(keyword in command_lower for keyword in self.ZOOM_KEYWORDS):
            # Extract zoom level if specified (e.g., "zoom 150%")
            zoom_level = 150
            parts = command_lower.split()
            for i, part in enumerate(parts):
                if "zoom" in part and i + 1 < len(parts):
                    try:
                        zoom_level = int(part.replace("%", ""))
                    except:
                        pass
            
            return {
                "status": "success",
                "action": "zoom",
                "command": command,
                "zoom_level": zoom_level,
                "message": f"Zooming to {zoom_level}%",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Check for reset zoom
        if any(keyword in command_lower for keyword in self.RESET_ZOOM_KEYWORDS):
            return {
                "status": "success",
                "action": "reset_zoom",
                "command": command,
                "zoom_level": 100,
                "message": "Zoom reset to 100%",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Check for specific file operations
        if "read" in command_lower and "document" in command_lower:
            return {
                "status": "success",
                "action": "read_document",
                "command": command,
                "message": "Ready to read document after summary",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        if "show" in command_lower and "summary" in command_lower:
            return {
                "status": "success",
                "action": "show_summary",
                "command": command,
                "message": "Displaying document summary",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        if "disable" in command_lower or "turn off" in command_lower:
            return {
                "status": "success",
                "action": "disable_service",
                "command": command,
                "message": "Service disabled by voice command",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        if "enable" in command_lower or "turn on" in command_lower:
            return {
                "status": "success",
                "action": "enable_service",
                "command": command,
                "message": "Service enabled by voice command",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return {
            "status": "unknown",
            "action": "no_action",
            "command": command,
            "message": "Voice command not recognized",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def process_text_command(self, command: str, user_id: str) -> Dict:
        """Process text command (manual button click equivalent)."""
        command_lower = command.lower().strip()
        
        return self.process_voice_command(command, user_id)
    
    def register_pending_approval(self, token: str, details: Dict) -> bool:
        """Register document for approval."""
        self.pending_approvals[token] = {
            "details": details,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        logger.info(f"Pending approval registered: {token}")
        return True
    
    def get_pending_approvals(self, user_id: str) -> Dict:
        """Get all pending approvals for user."""
        return self.pending_approvals
    
    def clear_pending_approval(self, token: str) -> bool:
        """Clear pending approval."""
        if token in self.pending_approvals:
            del self.pending_approvals[token]
            return True
        return False

# Global instance
voice_processor = VoiceCommandProcessor()
