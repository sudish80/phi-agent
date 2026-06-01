#!/usr/bin/env python
"""Comprehensive agent tool execution test."""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.agent import agent

async def test_scenario(message: str, description: str):
    """Test a scenario."""
    print(f"\n{'='*60}")
    print(f"Test: {description}")
    print(f"Message: {message}")
    print('='*60)
    
    try:
        result = await agent.process(
            message=message,
            session_id=f"test-{hash(message) % 10000}",
            emotion="neutral"
        )
        
        print(f"[OK] Reply: {result.get('reply')[:150]}")
        print(f"[OK] Tools called: {result.get('actions_taken', [])}")
        print(f"[OK] Processing time: {result.get('processing_time_ms', 0):.0f}ms")
        
        if result.get('actions_taken'):
            print("[SUCCESS] Agent executed tools!")
        else:
            print("[WARN] No tools executed")
        
        return result.get('actions_taken', [])
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return []

async def main():
    print("\n" + "="*60)
    print("COMPREHENSIVE AGENT TOOL EXECUTION TEST")
    print("="*60)
    
    scenarios = [
        ("what is my system info?", "System information retrieval"),
        ("open youtube", "URL opening"),
        ("how much disk space do I have?", "Disk usage check"),
    ]
    
    results = []
    for message, description in scenarios:
        tools = await test_scenario(message, description)
        results.append((description, tools))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for description, tools in results:
        status = "[OK]" if tools else "[WARN]"
        print(f"{status} {description}: {tools if tools else 'No tools'}")
    
    total_scenarios = len(results)
    successful = sum(1 for _, tools in results if tools)
    print(f"\n[SUCCESS] {successful}/{total_scenarios} scenarios executed tools successfully")

asyncio.run(main())
