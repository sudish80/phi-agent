#!/usr/bin/env python
"""Test file read/write/delete operations."""
import sys
import os
import asyncio
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.agent import agent

async def test_file_operations():
    """Test file read/write/delete."""
    print("\n" + "="*70)
    print("TESTING FILE OPERATIONS")
    print("="*70)
    
    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")
        
        # Test 1: WRITE
        print("\n[TEST 1] FILE WRITE")
        print("-"*70)
        result = await agent.process(
            message=f"Write 'Hello World' to {test_file}",
            session_id="test-write",
            emotion="neutral"
        )
        tools = result.get('actions_taken', [])
        reply = result.get('reply', '')[:150]
        print(f"Tools called: {tools}")
        print(f"Reply: {reply}")
        
        # Test 2: READ
        print("\n[TEST 2] FILE READ")
        print("-"*70)
        result = await agent.process(
            message=f"Read the file at {test_file}",
            session_id="test-read",
            emotion="neutral"
        )
        tools = result.get('actions_taken', [])
        reply = result.get('reply', '')[:150]
        print(f"Tools called: {tools}")
        print(f"Reply: {reply}")
        
        # Test 3: DELETE
        print("\n[TEST 3] FILE DELETE")
        print("-"*70)
        result = await agent.process(
            message=f"Delete the file at {test_file}",
            session_id="test-delete",
            emotion="neutral"
        )
        tools = result.get('actions_taken', [])
        reply = result.get('reply', '')[:150]
        print(f"Tools called: {tools}")
        print(f"Reply: {reply}")
        
        # Verify deletion
        exists = os.path.exists(test_file)
        print(f"File exists after deletion: {exists}")

asyncio.run(test_file_operations())
