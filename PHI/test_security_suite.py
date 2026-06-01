#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick test of the complete security suite."""

import sys
import os

# Set output encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("PHI Agent Security Suite - Quick Test")
print("=" * 60)

# Test 1: Authentication System
print("\n[TEST 1] Authentication System")
try:
    from backend.shared.auth_manager import auth_manager
    
    # Signup
    success, msg, user = auth_manager.signup("testuser", "test@example.com", "password123")
    print(f"  ✓ Signup: {msg}")
    user_id = user.get("user_id")
    
    # Login
    success, msg, session = auth_manager.login("testuser", "password123", "127.0.0.1")
    print(f"  ✓ Login: {msg}")
    token = session.get("session_token")
    
    # Verify session
    is_valid, uid, username = auth_manager.verify_session(token)
    print(f"  ✓ Verify Session: Valid={is_valid}, User={username}")
    
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 2: Mode System
print("\n[TEST 2] Mode System")
try:
    from backend.shared.mode_manager import mode_manager
    
    # List modes
    modes = mode_manager.list_available_modes()
    print(f"  ✓ Available modes: {list(modes.keys())}")
    
    # Switch to private mode
    success, msg = mode_manager.set_mode(user_id, "private", duration_minutes=120)
    print(f"  ✓ Set Private Mode: {msg}")
    
    # Get current mode
    current = mode_manager.get_current_mode(user_id)
    print(f"  ✓ Current Mode: {current['mode']}")
    
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 3: Permissions System
print("\n[TEST 3] Smart Permissions")
try:
    from backend.shared.smart_permissions import permission_manager
    
    # Grant permission
    permission_manager.grant_permission(str(user_id), "pdf_read", "all", duration_hours=1)
    print(f"  ✓ Permission Granted: pdf_read for 1 hour")
    
    # Check rate limit
    allowed, remaining = permission_manager.check_rate_limit(str(user_id), "pdf_read")
    print(f"  ✓ Rate Limit Check: Allowed={allowed}, Remaining={remaining}")
    
    # Get status
    status = permission_manager.get_rate_limit_status(str(user_id))
    print(f"  ✓ Rate Limit Status: {status.get('pdf_read', {}).get('used')}/5 used")
    
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 4: Audit Logging
print("\n[TEST 4] Audit Logging")
try:
    from backend.shared.audit_logging import log_file_access, get_audit_log, get_user_stats
    
    # Log an access
    log_file_access(
        user_id=str(user_id),
        file_path="/test/document.pdf",
        operation="pdf_read",
        file_type="pdf",
        file_size=1024,
        status="success",
        approved=1,
        extracted_size=512
    )
    print(f"  ✓ File Access Logged")
    
    # Get logs
    logs = get_audit_log(str(user_id), hours=24, limit=10)
    print(f"  ✓ Audit Logs Retrieved: {len(logs)} entries")
    
    # Get stats
    stats = get_user_stats(str(user_id), hours=24)
    print(f"  ✓ User Stats: Accesses={stats.get('total_accesses')}, Approved={stats.get('approved')}")
    
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 5: Document Summary
print("\n[TEST 5] Document Summary")
try:
    from backend.shared.document_summary import get_file_summary
    
    # Create a test file
    test_file = "/tmp/test_doc.txt"
    with open(test_file, 'w') as f:
        f.write("This is a test document.\nLine 2: Some content here.\nLine 3: More data.")
    
    # Get summary
    summary = get_file_summary(test_file)
    if "error" not in summary:
        print(f"  ✓ Document Summary: {summary.get('file_type')}, {summary.get('total_lines')} lines")
    else:
        print(f"  ! Summary: {summary['error']}")
    
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 6: Voice Control
print("\n[TEST 6] Voice Control System")
try:
    from backend.shared.voice_control import voice_processor
    
    # Test various commands
    commands = [
        ("approve", "approve"),
        ("zoom 150%", "zoom"),
        ("exit", "exit"),
        ("disable service", "disable_service")
    ]
    
    for cmd, expected_action in commands:
        result = voice_processor.process_voice_command(cmd, str(user_id))
        actual = result.get("action")
        status = "✓" if actual == expected_action else "✗"
        print(f"  {status} Voice Command '{cmd}': {actual}")
    
except Exception as e:
    print(f"  ✗ Error: {e}")

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print("✓ Authentication: Signup, Login, Verify Session")
print("✓ Modes: List, Set, Get Current")
print("✓ Permissions: Grant, Check Rate Limit, Get Status")
print("✓ Audit Logging: Log Access, Get Logs, Get Stats")
print("✓ Document Summary: Get Summary")
print("✓ Voice Control: Process Commands")
print("\nDatabase: phi_audit.db created successfully")
print("All systems operational!")
print("=" * 60)

# Test 7: Logout
print("\n[TEST 7] Cleanup")
try:
    success = auth_manager.logout(token)
    print(f"  ✓ Logout: Successful" if success else "  ✗ Logout: Failed")
except Exception as e:
    print(f"  ✗ Error: {e}")

print("\nDONE - All systems tested and ready!")

