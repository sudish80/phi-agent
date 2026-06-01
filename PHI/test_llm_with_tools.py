#!/usr/bin/env python
"""Test LLM APIs with tools parameter."""
import sys
import os
import asyncio
import aiohttp
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.shared.config import settings

async def test_nvidia_with_tools():
    """Test NVIDIA API with tools."""
    print("\n=== Testing NVIDIA API with Tools ===")
    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
    }
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "system_info",
                "description": "Get system information",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
    ]
    
    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant with access to tools."},
            {"role": "user", "content": "What is my system info?"}
        ],
        "temperature": 0.7,
        "max_tokens": 256,
        "tools": tools,
    }
    
    print(f"Sending request with {len(tools)} tool(s)...")
    
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
                    print(f"Success! Tool calls: {data['choices'][0]['message'].get('tool_calls', [])}")
                else:
                    print(f"Error response: {json.dumps(data, indent=2)[:500]}")
    except Exception as e:
        print(f"Error: {e}")

async def test_openrouter_with_tools():
    """Test OpenRouter API with tools."""
    print("\n=== Testing OpenRouter API with Tools ===")
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/jarvis",
        "X-Title": "J.A.R.V.I.S.",
    }
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "system_info",
                "description": "Get system information",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
    ]
    
    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant with access to tools."},
            {"role": "user", "content": "What is my system info?"}
        ],
        "temperature": 0.7,
        "max_tokens": 256,
        "tools": tools,
    }
    
    print(f"Sending request with {len(tools)} tool(s)...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                print(f"Status: {resp.status}")
                data = await resp.json()
                if resp.status == 200:
                    print(f"Success! Tool calls: {data['choices'][0]['message'].get('tool_calls', [])}")
                else:
                    print(f"Error response: {json.dumps(data, indent=2)[:1000]}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    await test_nvidia_with_tools()
    await test_openrouter_with_tools()

asyncio.run(main())
