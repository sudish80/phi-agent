"""Home Assistant integration via MQTT and REST API."""

import asyncio
import json
import logging
from typing import Optional

import aiohttp

from backend.shared.config import settings

logger = logging.getLogger(__name__)


class MQTTClient:
    """Async MQTT client for smart home control."""

    def __init__(self):
        self._client = None
        self._connected = False

    async def connect(self):
        try:
            import aiomqtt
            self._client = aiomqtt.Client(
                hostname=settings.mqtt_broker,
                port=settings.mqtt_port,
                username=settings.mqtt_username,
                password=settings.mqtt_password,
            )
            await self._client.__aenter__()
            self._connected = True
            logger.info(f"MQTT connected to {settings.mqtt_broker}")
        except Exception as e:
            logger.warning(f"MQTT unavailable: {e}")
            self._connected = False

    async def publish(self, topic: str, payload: dict):
        if not self._connected:
            return
        try:
            await self._client.publish(topic, json.dumps(payload), qos=1)
            logger.debug(f"MQTT publish {topic}: {payload}")
        except Exception as e:
            logger.error(f"MQTT publish error: {e}")

    async def disconnect(self):
        if self._client:
            await self._client.__aexit__(None, None, None)


mqtt = MQTTClient()


async def control_light(room: str, state: str) -> bool:
    """Turn a light on or off in a given room."""
    if mqtt._connected:
        topic = f"home/{room.lower().replace(' ', '_')}/light"
        await mqtt.publish(topic, {"state": state})
        logger.info(f"MQTT: Light in {room} turned {state}")
        return True

    try:
        ha_url = "http://homeassistant.local:8123"
        token = settings.mqtt_password or ""

        entity_id = f"light.{room.lower().replace(' ', '_')}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id}

        async with aiohttp.ClientSession() as session:
            service = "turn_on" if state == "on" else "turn_off"
            url = f"{ha_url}/api/services/light/{service}"
            async with session.post(url, headers=headers, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    logger.info(f"HA REST: Light in {room} turned {state}")
                    return True
                logger.warning(f"HA REST error: {resp.status}")
                return False
    except Exception as e:
        logger.error(f"Home Assistant error: {e}")
        return False


async def set_temperature(degrees: float) -> bool:
    """Set thermostat temperature."""
    if mqtt._connected:
        topic = "home/thermostat/set"
        await mqtt.publish(topic, {"temperature": degrees})
        return True

    try:
        ha_url = "http://homeassistant.local:8123"
        token = settings.mqtt_password or ""
        entity_id = "climate.thermostat"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": entity_id, "temperature": degrees}

        async with aiohttp.ClientSession() as session:
            url = f"{ha_url}/api/services/climate/set_temperature"
            async with session.post(url, headers=headers, json=payload, timeout=10) as resp:
                return resp.status == 200
    except Exception as e:
        logger.error(f"Thermostat error: {e}")
        return False


async def discover_entities() -> list:
    """Auto-discover Home Assistant entities."""
    try:
        ha_url = "http://homeassistant.local:8123"
        token = settings.mqtt_password or ""
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ha_url}/api/states", headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    states = await resp.json()
                    return [{"entity_id": s["entity_id"], "state": s["state"]}
                            for s in states]
                return []
    except Exception as e:
        logger.error(f"HA discovery error: {e}")
        return []
