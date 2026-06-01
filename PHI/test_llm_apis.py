#!/usr/bin/env python
"""Test LLM API requests directly to debug 400 errors."""
import sys
import os
import asyncio
import aiohttp
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.shared.config import settings

async def test_nvidia_api():
    """Test NVIDIA API directly."""
    print("\n=== Testing NVIDIA API ===")
    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello"}
        ],
        "temperature": 0.7,
        "max_tokens": 256,
    }
    
    print(f"API Key: {settings.nvidia_api_key[:20]}...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                print(f"Status: {resp.status}")
                data = await resp.text()
                print(f"Response: {data[:500]}")
    except Exception as e:
        print(f"Error: {e}")

async def test_openrouter_api():
    """Test OpenRouter API directly."""
    print("\n=== Testing OpenRouter API ===")
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/jarvis",
        "X-Title": "J.A.R.V.I.S.",
    }
    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello"}
        ],
        "temperature": 0.7,
        "max_tokens": 256,
    }
    
    print(f"API Key: {settings.openrouter_api_key[:20]}...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                print(f"Status: {resp.status}")
                data = await resp.text()
                print(f"Response: {data[:500]}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    await test_nvidia_api()
    await test_openrouter_api()

asyncio.run(main())
