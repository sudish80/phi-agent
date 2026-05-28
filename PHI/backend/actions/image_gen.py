"""Image generation module for J.A.R.V.I.S.

Generates images via OpenAI DALL-E or Stable Diffusion.
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from backend.shared.config import settings

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent / "static" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
_BASE_URL = f"http://localhost:{settings.action_port}/static/images"


async def generate_image_dalle(prompt: str, size: str = "1024x1024",
                               quality: str = "standard") -> str:
    """Generate an image using OpenAI DALL-E 3."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return "DALL-E requires openai package"

    api_key = settings.openai_api_key
    if not api_key:
        return "OpenAI API key not configured. Set OPENAI_API_KEY in .env"

    try:
        client = AsyncOpenAI(api_key=api_key)
        resp = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )
        image_url = resp.data[0].url
        revised = resp.data[0].revised_prompt

        result = f"Image generated: {image_url}"
        if revised:
            result += f"\n(Revised prompt: {revised})"
        return result
    except Exception as e:
        return f"DALL-E error: {e}"


async def generate_image_stable_diffusion(prompt: str,
                                          negative_prompt: str = "") -> str:
    """Generate an image using Stable Diffusion (HuggingFace or local API)."""
    import aiohttp

    api_url = settings.local_llm_url.replace(":8080", ":7860") + "/sdapi/v1/txt2img"
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "prompt": prompt,
                "negative_prompt": negative_prompt or "",
                "steps": 20,
                "width": 512,
                "height": 512,
            }
            async with session.post(api_url, json=payload, timeout=120) as resp:
                if resp.status != 200:
                    return f"Stable Diffusion error: HTTP {resp.status}"
                data = await resp.json()
                import base64
                img_data = base64.b64decode(data["images"][0])
                filename = f"sd_{uuid.uuid4().hex[:8]}.png"
                path = OUTPUT_DIR / filename
                with open(path, "wb") as f:
                    f.write(img_data)
                return f"Image saved: {_BASE_URL}/{filename}"
    except Exception as e:
        return f"Stable Diffusion error: {e}"
