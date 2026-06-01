#!/usr/bin/env python
"""Test script to check if agent can process messages and call tools."""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.agent import agent

async def test_process():
    """Test agent.process() with a simple message."""
    try:
        print("Testing agent.process() with message: 'what is my system info?'")
        result = await agent.process(
            message="what is my system info?",
            session_id="test-session-123",
            emotion="neutral"
        )
        
        print(f"\nResult received:")
        print(f"  reply: {result.get('reply')[:100]}...")
        print(f"  actions_taken: {result.get('actions_taken', [])}")
        print(f"  tool_recommendations: {result.get('tool_recommendations', [])}")
        print(f"  processing_time_ms: {result.get('processing_time_ms')}")
        
        if result.get('actions_taken'):
            print("\nSUCCESS: Agent executed tools!")
        else:
            print("\nWARNING: Agent did not execute any tools")
            print(f"Full result: {result}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_process())
