"""Web search and weather via SerpAPI / OpenWeatherMap."""

import asyncio
import logging
from typing import List, Dict, Optional

import aiohttp

from backend.shared.config import settings

logger = logging.getLogger(__name__)


async def search_web(query: str, num_results: int = 5) -> List[Dict]:
    """Search the web using SerpAPI or fallback to DuckDuckGo."""
    if settings.serpapi_api_key:
        return await _search_serpapi(query, num_results)
    return await _search_duckduckgo(query, num_results)


async def _search_serpapi(query: str, num: int) -> List[Dict]:
    url = "https://serpapi.com/search"
    params = {"q": query, "api_key": settings.serpapi_api_key, "num": num}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, timeout=15) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = []
                for r in data.get("organic_results", [])[:num]:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("link", ""),
                        "snippet": r.get("snippet", ""),
                    })
                return results
        except Exception as e:
            logger.error(f"SerpAPI error: {e}")
            return []


async def _search_duckduckgo(query: str, num: int) -> List[Dict]:
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, timeout=15) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = []
                abstract = data.get("AbstractText", "")
                if abstract:
                    results.append({
                        "title": data.get("Heading", "Result"),
                        "url": data.get("AbstractURL", ""),
                        "snippet": abstract,
                    })
                for topic in data.get("RelatedTopics", [])[:num]:
                    if "Text" in topic:
                        results.append({
                            "title": topic.get("Text", "")[:50],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                        })
                return results
        except Exception as e:
            logger.error(f"DuckDuckGo error: {e}")
            return []


async def get_weather(location: str) -> str:
    """Get current weather for a location."""
    api_key = settings.weather_api_key
    if api_key:
        return await _get_weather_openweather(location, api_key)
    return await _get_weather_wttrin(location)


async def _get_weather_openweather(location: str, api_key: str) -> str:
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": location, "appid": api_key, "units": "metric"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return f"Weather unavailable for {location}"
                data = await resp.json()
                temp = data["main"]["temp"]
                feels_like = data["main"]["feels_like"]
                humidity = data["main"]["humidity"]
                desc = data["weather"][0]["description"]
                wind = data["wind"]["speed"]

                return (f"Weather in {location}: {desc}, "
                        f"{temp:.1f}°C (feels like {feels_like:.1f}°C), "
                        f"humidity {humidity}%, wind {wind} m/s")
        except Exception as e:
            logger.error(f"OpenWeather error: {e}")
            return f"Could not get weather: {e}"


async def _get_weather_wttrin(location: str) -> str:
    url = f"https://wttr.in/{location}?format=%C+%t+%w+%h"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return f"Weather in {location}: {text.strip()}"
                return f"Weather unavailable for {location}"
        except Exception as e:
            return f"Could not get weather: {e}"
