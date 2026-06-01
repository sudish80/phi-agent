#!/usr/bin/env python
"""Test if agent can actually execute computer control tools."""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.agent import agent

async def test_computer_control():
    """Test computer control capabilities."""
    print("\n" + "="*60)
    print("TESTING AGENT COMPUTER CONTROL")
    print("="*60)
    
    tests = [
        ("What's the current mouse position?", "Get mouse position"),
        ("List all running processes", "Process enumeration"),
        ("Get my keyboard shortcuts", "Discover keyboard shortcuts"),
    ]
    
    for message, description in tests:
        print(f"\nTest: {description}")
        print(f"Message: {message}")
        
        try:
            result = await agent.process(
                message=message,
                session_id=f"test-{hash(message) % 10000}",
                emotion="neutral"
            )
            
            tools_called = result.get('actions_taken', [])
            reply = result.get('reply', '')[:200]
            
            if tools_called:
                print(f"[SUCCESS] Tools called: {tools_called}")
                print(f"Reply: {reply}...")
            else:
                print(f"[INFO] No tools called")
                print(f"Reply: {reply}...")
                
        except Exception as e:
            print(f"[ERROR] {e}")

asyncio.run(test_computer_control())
