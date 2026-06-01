#!/usr/bin/env python
"""Test with all 134 filtered tools."""
import sys
import os
import asyncio
import aiohttp
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.shared.config import settings
from backend.orchestrator.agent import agent

async def test_nvidia_with_all_tools():
    """Test NVIDIA API with all agent tools."""
    print("\n=== Testing NVIDIA with ALL Agent Tools ===")
    
    # Get the same tools the agent uses
    all_tools = agent.tools.list_tools()
    key_categories = {"system", "web", "entertainment", "search", "ai", "communication", "fun", "automation", "audio"}
    filtered_tools = [t for t in all_tools if t.get("category") in key_categories]
    
    print(f"Filtered tools: {len(filtered_tools)}")
    
    # Convert to OpenAI format
    openai_tools = []
    for t in filtered_tools:
        params = t.get("parameters", {})
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", "")[:200],
                "parameters": {
                    "type": "object",
                    "properties": params.get("properties", {}),
                    "required": params.get("required", []),
                },
            },
        })
    
    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": [
            {"role": "user", "content": "What is my system info?"}
        ],
        "temperature": 0.7,
        "max_tokens": 256,
        "tools": openai_tools,
    }
    
    print(f"Payload size: {len(json.dumps(payload))} bytes")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                print(f"Status: {resp.status}")
                data = await resp.json()
                if resp.status == 200:
                    msg = data['choices'][0]['message']
                    print(f"Success! Tool called: {msg.get('tool_calls', [])}")
                else:
                    print(f"Error: {data}")
    except Exception as e:
        print(f"Exception: {e}")

asyncio.run(test_nvidia_with_all_tools())
