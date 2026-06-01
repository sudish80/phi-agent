#!/usr/bin/env python
"""Test with many tools to find what causes 400 error."""
import sys
import os
import asyncio
import aiohttp
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.shared.config import settings
from backend.orchestrator.agent import agent

async def test_nvidia_with_many_tools():
    """Test NVIDIA API with many tools like the agent does."""
    print("\n=== Testing NVIDIA with Agent's Tool List ===")
    
    # Get the same tools the agent uses
    all_tools = agent.tools.list_tools()
    key_categories = {"system", "web", "entertainment", "search", "ai", "communication", "fun", "automation", "audio"}
    filtered_tools = [t for t in all_tools if t.get("category") in key_categories]
    
    print(f"Total tools: {len(all_tools)}")
    print(f"Filtered tools (key categories): {len(filtered_tools)}")
    
    # Convert to OpenAI format
    openai_tools = []
    for t in filtered_tools[:50]:  # Start with first 50
        params = t.get("parameters", {})
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", "")[:200],  # Truncate long descriptions
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
            {
                "role": "system", 
                "content": "You are a helpful AI. Available tools: " + ", ".join([t["name"] for t in filtered_tools[:10]])
            },
            {"role": "user", "content": "What is my system info?"}
        ],
        "temperature": 0.7,
        "max_tokens": 256,
        "tools": openai_tools,
    }
    
    print(f"\nSending request with {len(openai_tools)} OpenAI tools...")
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
                    print(f"Tool calls: {msg.get('tool_calls', [])}")
                    print(f"Content: {msg.get('content', '')[:100]}")
                else:
                    print(f"Error: {json.dumps(data, indent=2)[:800]}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_nvidia_with_many_tools())
