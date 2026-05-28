"""Travel Agent — AI-powered travel planning with itinerary generation.

Adapted from: github.com/vivekpathania/ai-experiments (travel-agent/)
Generates personalized travel itineraries using LLM + web search.
"""

import json
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


async def plan_trip(
    destination: str,
    origin: str = "",
    dates: str = "",
    duration_days: int = 3,
    travelers: str = "1 adult",
    budget: str = "moderate",
    interests: str = "",
    preferences: str = "",
    include_flights: bool = True,
    include_hotels: bool = True,
    include_activities: bool = True,
) -> str:
    """Generate a personalized travel itinerary using AI planning."""
    from backend.shared.llm_client import llm_client
    from backend.orchestrator.agent import agent

    prompt = f"""You are an expert travel planner. Create a detailed {duration_days}-day travel itinerary.

Destination: {destination}
Origin: {origin or 'Not specified'}
Dates: {dates or 'Not specified'}
Duration: {duration_days} days
Travelers: {travelers}
Budget: {budget}
Interests: {interests or 'General sightseeing'}
Preferences: {preferences or 'Balanced itinerary'}

Include sections:
1. **Trip Overview** — destination highlights, weather, local tips
2. **Day-by-Day Itinerary** — morning, afternoon, evening for each day
3. **Accommodation Recommendations** — 3 options (budget, mid-range, luxury)
4. **Dining Recommendations** — local cuisine, restaurants
5. **Activities & Attractions** — must-see with estimated costs
6. **Transportation** — how to get around
7. **Packing Tips** — weather-appropriate suggestions
8. **Estimated Budget Breakdown**
"""

    if include_flights:
        prompt += "\nInclude flight search suggestions from the origin."

    result = await llm_client.generate([
        {"role": "system", "content": "You are a professional travel planner AI."},
        {"role": "user", "content": prompt},
    ])

    itinerary = result.content if hasattr(result, "content") else str(result)

    if origin and include_flights:
        try:
            flight_info = await agent.tools.execute("search_web", {
                "query": f"flights from {origin} to {destination} {dates or duration_days} days"
            })
            itinerary += f"\n\n---\n**Flight Search Results:**\n{flight_info[:1000]}"
        except Exception as e:
            logger.warning(f"Flight search failed: {e}")

    return itinerary


async def get_destination_info(destination: str) -> str:
    """Get comprehensive information about a travel destination."""
    from backend.shared.llm_client import llm_client

    result = await llm_client.generate([
        {"role": "system", "content": "You are a travel destination expert."},
        {"role": "user", "content": f"""Provide comprehensive information about {destination} as a travel destination:

- Best time to visit
- Top attractions
- Local cuisine
- Culture and customs
- Transportation
- Safety tips
- Estimated daily budget
- Language and communication tips
- Visa requirements
- Hidden gems off the tourist path"""},
    ])
    return result.content if hasattr(result, "content") else str(result)
