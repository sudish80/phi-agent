"""Action Service — executes commands (email, calendar, smart home, etc).

FastAPI endpoints:
  - POST /send-email
  - POST /create-event
  - POST /web-search
  - POST /control-light
  - POST /set-temperature
  - POST /open-app
  - POST /screenshot
  - GET /system-info
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.shared.config import settings
from backend.shared.redis_client import RedisPubSub
from backend.actions.email import send_email
from backend.actions.calendar import create_event
from backend.actions.web_search import search_web, get_weather
from backend.actions.home_assistant import control_light, set_temperature
from backend.actions.system_commands import open_application, take_screenshot, get_system_info

logger = logging.getLogger(__name__)

app = FastAPI(title="J.A.R.V.I.S. Action Service", version="1.0.0")
redis = RedisPubSub()

_static_dir = Path(__file__).resolve().parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
if any(_static_dir.iterdir()) is False:  # mount only if dir exists
    pass
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


class EmailRequest(BaseModel):
    to: str
    subject: str
    body: str


class CalendarRequest(BaseModel):
    summary: str
    start: str
    end: str
    description: str = ""


class SearchRequest(BaseModel):
    query: str


class LightRequest(BaseModel):
    room: str
    state: str = Field(..., pattern="^(on|off)$")


class TemperatureRequest(BaseModel):
    degrees: float = Field(..., ge=10, le=35)


class AppRequest(BaseModel):
    app_name: str


@app.on_event("startup")
async def startup():
    await redis.connect("action")

    async def handle_rpc(msg):
        method = msg.payload.get("method")
        params = msg.payload.get("params", {})
        response_channel = msg.payload.get("_response_channel")
        result = {"status": "error", "data": {}}

        try:
            if method == "send_email":
                await send_email(params["to"], params["subject"], params["body"])
                result = {"status": "ok", "data": {"sent": True}}
            elif method == "create_event":
                event_id = await create_event(
                    params["summary"], params["start"], params["end"],
                    params.get("description", ""),
                )
                result = {"status": "ok", "data": {"event_id": event_id}}
            elif method == "web_search":
                results = await search_web(params.get("query", ""))
                result = {"status": "ok", "data": {"results": results}}
            elif method == "get_weather":
                weather = await get_weather(params.get("location", ""))
                result = {"status": "ok", "data": {"weather": weather}}
            elif method == "control_light":
                success = await control_light(params["room"], params["state"])
                result = {"status": "ok", "data": {"success": success}}
            elif method == "set_temperature":
                success = await set_temperature(params["degrees"])
                result = {"status": "ok", "data": {"success": success}}
            elif method == "open_app":
                success = await open_application(params["app_name"])
                result = {"status": "ok", "data": {"success": success}}
            elif method == "get_system_info":
                info = await get_system_info()
                result = {"status": "ok", "data": info}
            elif method == "get_stock_price":
                from backend.actions.api_integrations import get_stock_price
                data = await get_stock_price(params.get("symbol", ""))
                result = {"status": "ok", "data": {"result": data}}
            elif method == "get_market_indices":
                from backend.actions.api_integrations import get_market_indices
                data = await get_market_indices()
                result = {"status": "ok", "data": {"result": data}}
            elif method == "get_news":
                from backend.actions.api_integrations import get_news
                data = await get_news(params.get("topic", "general"), params.get("count", 5))
                result = {"status": "ok", "data": {"result": data}}
            elif method == "get_crypto_price":
                from backend.actions.api_integrations import get_crypto_price
                data = await get_crypto_price(params.get("coin", "bitcoin"), params.get("currency", "USD"))
                result = {"status": "ok", "data": {"result": data}}
            elif method == "convert_currency":
                from backend.actions.api_integrations import get_currency_conversion
                data = await get_currency_conversion(params.get("amount", 1),
                                                     params.get("from_currency", "USD"),
                                                     params.get("to_currency", "EUR"))
                result = {"status": "ok", "data": {"result": data}}
            elif method == "get_movie_info":
                from backend.actions.api_integrations import get_movie_info
                data = await get_movie_info(params.get("title", ""))
                result = {"status": "ok", "data": {"result": data}}
            elif method == "get_joke":
                from backend.actions.api_integrations import get_joke
                data = await get_joke(params.get("joke_type", "any"))
                result = {"status": "ok", "data": {"result": data}}
        except Exception as e:
            logger.error(f"RPC {method} error: {e}")
            result = {"status": "error", "data": {}, "error": str(e)}

        if response_channel:
            await redis.publish(response_channel, result)

    redis.subscribe("rpc:action", handle_rpc)
    await redis.start_listening()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "action"}


@app.post("/send-email")
async def send_email_endpoint(request: EmailRequest):
    success = await send_email(request.to, request.subject, request.body)
    if not success:
        raise HTTPException(status_code=500, detail="Email send failed")
    return {"status": "sent", "to": request.to, "subject": request.subject}


@app.post("/create-event")
async def create_event_endpoint(request: CalendarRequest):
    event_id = await create_event(
        request.summary, request.start, request.end, request.description,
    )
    if not event_id:
        raise HTTPException(status_code=500, detail="Event creation failed")
    return {"status": "created", "event_id": event_id}


@app.post("/web-search")
async def web_search_endpoint(request: SearchRequest):
    results = await search_web(request.query)
    return {"results": results}


@app.get("/weather")
async def weather_endpoint(location: str = "London"):
    weather = await get_weather(location)
    return {"weather": weather}


@app.post("/control-light")
async def control_light_endpoint(request: LightRequest):
    success = await control_light(request.room, request.state)
    return {"status": "ok" if success else "failed"}


@app.post("/set-temperature")
async def set_temperature_endpoint(request: TemperatureRequest):
    success = await set_temperature(request.degrees)
    return {"status": "ok" if success else "failed"}


@app.post("/open-app")
async def open_app_endpoint(request: AppRequest):
    success = await open_application(request.app_name)
    return {"status": "ok" if success else "failed"}


@app.post("/screenshot")
async def screenshot_endpoint():
    path = await take_screenshot()
    if not path:
        raise HTTPException(status_code=500, detail="Screenshot failed")
    return {"path": path}


@app.get("/system-info")
async def system_info_endpoint():
    return await get_system_info()


@app.get("/status")
async def status():
    return await health()


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, settings.log_level))
    uvicorn.run("backend.actions.service:app", host="0.0.0.0", port=settings.action_port)
