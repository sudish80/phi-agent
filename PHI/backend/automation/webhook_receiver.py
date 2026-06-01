"""Webhook receiver — handle incoming webhooks from external services."""

import json
import logging
import hashlib
import hmac
from typing import Any, Callable, Dict, Optional, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

WebhookHandler = Callable[..., Awaitable[str]]


@dataclass
class WebhookRoute:
    path: str
    secret: str = ""
    handler: Optional[WebhookHandler] = None


class WebhookReceiver:
    """Receives webhooks and routes them to configured handlers."""

    def __init__(self):
        self._routes: Dict[str, WebhookRoute] = {}

    def register(self, path: str, handler: WebhookHandler, secret: str = "") -> None:
        self._routes[path] = WebhookRoute(path=path, secret=secret, handler=handler)

    def verify_signature(self, path: str, payload: bytes, signature: str) -> bool:
        route = self._routes.get(path)
        if not route or not route.secret:
            return True
        expected = hmac.new(route.secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def dispatch(self, path: str, payload: Dict[str, Any],
                       headers: Optional[Dict[str, str]] = None) -> str:
        route = self._routes.get(path)
        if not route or not route.handler:
            return "Not found"
        sig = (headers or {}).get("X-Hub-Signature-256", "")
        if not self.verify_signature(path, json.dumps(payload).encode(), sig):
            return "Invalid signature"
        return await route.handler(payload, headers or {})

    async def handle_github_push(self, payload: Dict[str, Any],
                                  headers: Dict[str, str]) -> str:
        repo = payload.get("repository", {}).get("full_name", "unknown")
        ref = payload.get("ref", "")
        logger.info("GitHub push: %s %s", repo, ref)
        return f"Received push to {repo} ({ref})"

    async def handle_slack_command(self, payload: Dict[str, Any],
                                    headers: Dict[str, str]) -> str:
        command = payload.get("command", "")
        text = payload.get("text", "")
        user = payload.get("user_name", "")
        logger.info("Slash command from %s: %s %s", user, command, text)
        return f"Processing /{command} {text}"


webhook_receiver = WebhookReceiver()
webhook_receiver.register("/github/push", webhook_receiver.handle_github_push)
webhook_receiver.register("/slack/command", webhook_receiver.handle_slack_command)
