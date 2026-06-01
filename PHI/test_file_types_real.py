#!/usr/bin/env python
"""Test agent file reading with different file types."""
import sys
import os
import asyncio
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator.agent import agent

async def test_file_reading():
    """Test reading different file types."""
    print("\n" + "="*70)
    print("TESTING FILE TYPE READING CAPABILITIES")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test 1: Text file (should work)
        print("\n[TEST 1] TEXT FILE (.txt)")
        print("-"*70)
        txt_file = os.path.join(tmpdir, "test.txt")
        with open(txt_file, "w") as f:
            f.write("This is a text file with important data:\nAPI_KEY=sk-123456789\nPASSWORD=secret123")
        
        result = await agent.process(
            message=f"Read the file at {txt_file}",
            session_id="test-txt",
            emotion="neutral"
        )
        tools = result.get('actions_taken', [])
        reply = result.get('reply', '')[:200]
        print(f"Tools called: {tools}")
        print(f"Reply: {reply}")
        
        # Test 2: JSON file (should work)
        print("\n[TEST 2] JSON FILE (.json)")
        print("-"*70)
        json_file = os.path.join(tmpdir, "config.json")
        with open(json_file, "w") as f:
            f.write('{"database": {"host": "localhost", "user": "admin", "pass": "password123"}}')
        
        result = await agent.process(
            message=f"Read the config file at {json_file}",
            session_id="test-json",
            emotion="neutral"
        )
        tools = result.get('actions_taken', [])
        reply = result.get('reply', '')[:200]
        print(f"Tools called: {tools}")
        print(f"Reply: {reply}")
        
        # Test 3: Python file (should work)
        print("\n[TEST 3] PYTHON FILE (.py)")
        print("-"*70)
        py_file = os.path.join(tmpdir, "script.py")
        with open(py_file, "w") as f:
            f.write('import os\ndb_password = "secret123"\ndef login(): pass')
        
        result = await agent.process(
            message=f"Read the Python file at {py_file}",
            session_id="test-py",
            emotion="neutral"
        )
        tools = result.get('actions_taken', [])
        reply = result.get('reply', '')[:200]
        print(f"Tools called: {tools}")
        print(f"Reply: {reply}")
        
        # Test 4: Binary file (image)
        print("\n[TEST 4] BINARY FILE (.exe or .bin)")
        print("-"*70)
        bin_file = os.path.join(tmpdir, "app.exe")
        with open(bin_file, "wb") as f:
            # Write some fake binary data
            f.write(b'\x4D\x5A\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00')
        
        result = await agent.process(
            message=f"Read the binary file at {bin_file}",
            session_id="test-bin",
            emotion="neutral"
        )
        tools = result.get('actions_taken', [])
        reply = result.get('reply', '')[:200]
        print(f"Tools called: {tools}")
        print(f"Reply (first 100 chars): {reply[:100]}...")
        print(f"NOTE: Binary data is UNREADABLE when using file_read")

asyncio.run(test_file_reading())
