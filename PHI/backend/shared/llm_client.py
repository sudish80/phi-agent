"""Unified multi-LLM client supporting local, OpenAI, Claude, DeepSeek, OpenRouter.

Provides a single async interface for all LLM providers with:
- Automatic failover between providers
- Streaming support
- Token counting and cost tracking
- Structured output parsing
- Retry with exponential backoff
"""

import json
import os
import re
import time
import copy
import logging
import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

import aiohttp
import tiktoken

from .config import settings

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    OPENROUTER = "openrouter"
    NVIDIA = "nvidia"
    LOCAL = "local"
    OLLAMA = "ollama"


class LLMRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class LLMMessage:
    role: LLMRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: float = 60.0
    max_retries: int = 3
    stream: bool = False
    base_url: Optional[str] = None
    api_key: Optional[str] = None


@dataclass
class LLMResponse:
    content: str
    provider: LLMProvider
    model: str
    usage: Dict[str, int] = field(default_factory=lambda: {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
    })
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    raw: Optional[Dict] = None


# ============================================================
# Token counting
# ============================================================

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens using tiktoken if available."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        return len(text) // 4


def estimate_cost(usage: Dict[str, int], provider: LLMProvider, model: str) -> float:
    """Estimate API cost based on token usage."""
    rates = {
        LLMProvider.OPENAI: {
            "gpt-4": (0.03, 0.06),
            "gpt-4-turbo": (0.01, 0.03),
            "gpt-3.5-turbo": (0.001, 0.002),
        },
        LLMProvider.ANTHROPIC: {
            "claude-3-opus": (0.015, 0.075),
            "claude-3-sonnet": (0.003, 0.015),
            "claude-3-haiku": (0.00025, 0.00125),
        },
        LLMProvider.DEEPSEEK: {
            "deepseek-chat": (0.00014, 0.00028),
        },
        LLMProvider.OPENROUTER: {},  # varies by model
        LLMProvider.LOCAL: {"default": (0, 0)},
        LLMProvider.OLLAMA: {"default": (0, 0)},
    }
    provider_rates = rates.get(provider, {})
    model_rates = provider_rates.get(model, provider_rates.get(model.split("/")[-1], (0, 0)))
    if not model_rates:
        model_rates = provider_rates.get(list(provider_rates.keys())[0], (0, 0))

    prompt_cost = usage.get("prompt_tokens", 0) * model_rates[0] / 1000
    completion_cost = usage.get("completion_tokens", 0) * model_rates[1] / 1000
    return prompt_cost + completion_cost


# ============================================================
# Provider Implementations
# ============================================================

class BaseLLMProvider(ABC):
    """Abstract base for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def generate(self, messages: List[LLMMessage], tools: List[Dict] = None) -> LLMResponse:
        ...

    @abstractmethod
    async def generate_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        ...

    def _format_messages(self, messages: List[LLMMessage]) -> List[Dict]:
        return [
            {"role": m.role.value, "content": m.content}
            for m in messages
        ]


class OpenAIProvider(BaseLLMProvider):
    """OpenAI / Azure OpenAI provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or settings.openai_api_key
        self.base_url = config.base_url or "https://api.openai.com/v1"

    async def generate(self, messages: List[LLMMessage], tools: List[Dict] = None) -> LLMResponse:
        start = time.time()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }
        if tools:
            payload["tools"] = tools

        async with aiohttp.ClientSession() as session:
            for attempt in range(self.config.max_retries):
                try:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                    ) as resp:
                        if resp.status == 429:
                            wait = 2 ** attempt
                            logger.warning(f"Rate limited, retrying in {wait}s")
                            await asyncio.sleep(wait)
                            continue
                        resp.raise_for_status()
                        data = await resp.json()
                        choice = data["choices"][0]
                        return LLMResponse(
                            content=choice["message"]["content"] or "",
                            provider=LLMProvider.OPENAI,
                            model=self.config.model,
                            usage={
                                "prompt_tokens": data["usage"]["prompt_tokens"],
                                "completion_tokens": data["usage"]["completion_tokens"],
                                "total_tokens": data["usage"]["total_tokens"],
                            },
                            latency_ms=(time.time() - start) * 1000,
                            finish_reason=choice["finish_reason"],
                            raw=data,
                        )
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt == self.config.max_retries - 1:
                        raise
                    logger.warning(f"OpenAI attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)

        raise RuntimeError("OpenAI generation failed after retries")

    async def generate_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as resp:
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"]
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError):
                            continue


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or settings.anthropic_api_key
        self.base_url = config.base_url or "https://api.anthropic.com/v1"

    async def generate(self, messages: List[LLMMessage], tools: List[Dict] = None) -> LLMResponse:
        start = time.time()
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        system_msg = None
        formatted = []
        for m in messages:
            if m.role == LLMRole.SYSTEM:
                system_msg = m.content
            else:
                formatted.append({"role": m.role.value, "content": m.content})

        payload = {
            "model": self.config.model,
            "messages": formatted,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if system_msg:
            payload["system"] = system_msg

        async with aiohttp.ClientSession() as session:
            for attempt in range(self.config.max_retries):
                try:
                    async with session.post(
                        f"{self.base_url}/messages",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        content = ""
                        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                        for block in data.get("content", []):
                            if block.get("type") == "text":
                                content += block["text"]
                        if "usage" in data:
                            usage = {
                                "prompt_tokens": data["usage"].get("input_tokens", 0),
                                "completion_tokens": data["usage"].get("output_tokens", 0),
                                "total_tokens": data["usage"].get("input_tokens", 0) +
                                               data["usage"].get("output_tokens", 0),
                            }
                        return LLMResponse(
                            content=content,
                            provider=LLMProvider.ANTHROPIC,
                            model=self.config.model,
                            usage=usage,
                            latency_ms=(time.time() - start) * 1000,
                            finish_reason=data.get("stop_reason", "stop"),
                            raw=data,
                        )
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt == self.config.max_retries - 1:
                        raise
                    logger.warning(f"Anthropic attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)

        raise RuntimeError("Anthropic generation failed after retries")

    async def generate_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        formatted = [{"role": m.role.value, "content": m.content}
                     for m in messages if m.role != LLMRole.SYSTEM]
        payload = {
            "model": self.config.model,
            "messages": formatted,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }
        system_msg = next((m.content for m in messages if m.role == LLMRole.SYSTEM), None)
        if system_msg:
            payload["system"] = system_msg

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as resp:
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data["type"] == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield delta.get("text", "")
                        except (json.JSONDecodeError, KeyError):
                            pass


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or settings.openai_api_key
        self.base_url = "https://api.deepseek.com/v1"

    async def generate(self, messages: List[LLMMessage], tools: List[Dict] = None) -> LLMResponse:
        # DeepSeek uses OpenAI-compatible API
        openai_config = copy.deepcopy(self.config)
        openai_config.base_url = self.base_url
        openai_config.api_key = self.api_key
        openai_config.model = self.config.model or "deepseek-chat"
        provider = OpenAIProvider(openai_config)
        resp = await provider.generate(messages, tools)
        resp.provider = LLMProvider.DEEPSEEK
        return resp

    async def generate_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        openai_config = copy.deepcopy(self.config)
        openai_config.base_url = self.base_url
        openai_config.api_key = self.api_key
        openai_config.model = self.config.model or "deepseek-chat"
        provider = OpenAIProvider(openai_config)
        async for chunk in provider.generate_stream(messages):
            yield chunk


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter multi-model provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or settings.openrouter_api_key or settings.openai_api_key
        self.base_url = "https://openrouter.ai/api/v1"

    async def generate(self, messages: List[LLMMessage], tools: List[Dict] = None) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/jarvis",
            "X-Title": "J.A.R.V.I.S.",
        }
        payload = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        async with aiohttp.ClientSession() as session:
            for attempt in range(self.config.max_retries):
                try:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        choice = data["choices"][0]
                        return LLMResponse(
                            content=choice["message"]["content"] or "",
                            provider=LLMProvider.OPENROUTER,
                            model=data.get("model", self.config.model),
                            usage={
                                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                                "total_tokens": data.get("usage", {}).get("total_tokens", 0),
                            },
                            latency_ms=0,
                            finish_reason=choice.get("finish_reason", "stop"),
                            raw=data,
                        )
                except Exception as e:
                    if attempt == self.config.max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)

    async def generate_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as resp:
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"]
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError):
                            continue


class NVIDIAProvider(BaseLLMProvider):
    """NVIDIA NIM / API Catalog provider (OpenAI-compatible)."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or settings.nvidia_api_key
        self.base_url = config.base_url or "https://integrate.api.nvidia.com/v1"

    async def generate(self, messages: List[LLMMessage], tools: List[Dict] = None) -> LLMResponse:
        start = time.time()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        async with aiohttp.ClientSession() as session:
            for attempt in range(self.config.max_retries):
                try:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        choice = data["choices"][0]
                        return LLMResponse(
                            content=choice["message"]["content"] or "",
                            provider=LLMProvider.NVIDIA,
                            model=data.get("model", self.config.model),
                            usage={
                                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                                "total_tokens": data.get("usage", {}).get("total_tokens", 0),
                            },
                            latency_ms=(time.time() - start) * 1000,
                            finish_reason=choice.get("finish_reason", "stop"),
                            raw=data,
                        )
                except Exception as e:
                    if attempt == self.config.max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)

    async def generate_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as resp:
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"]
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError):
                            continue


class LocalProvider(BaseLLMProvider):
    """Local LLM provider (Ollama, llama.cpp, vLLM, etc.)."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or settings.local_llm_url

    async def generate(self, messages: List[LLMMessage], tools: List[Dict] = None) -> LLMResponse:
        start = time.time()
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.config.model or settings.local_llm_model,
            "messages": self._format_messages(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }

        async with aiohttp.ClientSession() as session:
            for attempt in range(self.config.max_retries):
                try:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        choice = data["choices"][0] if "choices" in data else {"message": {"content": ""}, "finish_reason": "stop"}
                        return LLMResponse(
                            content=choice.get("message", {}).get("content", ""),
                            provider=LLMProvider.LOCAL,
                            model=self.config.model or "local",
                            usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                            latency_ms=(time.time() - start) * 1000,
                            finish_reason=choice.get("finish_reason", "stop"),
                            raw=data,
                        )
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt == self.config.max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)

        raise RuntimeError("Local LLM generation failed")

    async def generate_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.config.model or settings.local_llm_model,
            "messages": self._format_messages(messages),
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as resp:
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"]
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass


class OllamaProvider(LocalProvider):
    """Ollama-specific provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434/v1"

    async def generate(self, messages: List[LLMMessage], tools: List[Dict] = None) -> LLMResponse:
        start = time.time()
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.config.model or "llama3",
            "messages": self._format_messages(messages),
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
            "stream": False,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url.replace('/v1', '')}/api/chat",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return LLMResponse(
                        content=data.get("message", {}).get("content", ""),
                        provider=LLMProvider.OLLAMA,
                        model=data.get("model", "llama3"),
                        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        latency_ms=(time.time() - start) * 1000,
                        finish_reason="stop",
                        raw=data,
                    )
            except Exception as e:
                logger.error(f"Ollama error: {e}")
                raise


# ============================================================
# Unified LLM Client
# ============================================================

_provider_cache: Dict[str, BaseLLMProvider] = {}


def _get_provider(config: LLMConfig) -> BaseLLMProvider:
    """Get or create a provider instance."""
    key = f"{config.provider.value}:{config.model}"
    if key not in _provider_cache:
        providers = {
            LLMProvider.OPENAI: OpenAIProvider,
            LLMProvider.ANTHROPIC: AnthropicProvider,
            LLMProvider.DEEPSEEK: DeepSeekProvider,
            LLMProvider.OPENROUTER: OpenRouterProvider,
            LLMProvider.NVIDIA: NVIDIAProvider,
            LLMProvider.LOCAL: LocalProvider,
            LLMProvider.OLLAMA: OllamaProvider,
        }
        provider_cls = providers.get(config.provider, OpenAIProvider)
        _provider_cache[key] = provider_cls(config)
    return _provider_cache[key]


class LLMClient:
    """Unified LLM client with multi-provider support and auto-failover."""

    def __init__(self):
        self._providers: List[LLMConfig] = self._build_provider_chain()
        self._token_tracker: Dict[str, int] = {"total_prompt": 0, "total_completion": 0}

    def _build_provider_chain(self) -> List[LLMConfig]:
        """Build provider chain based on configured credentials.
        
        The user's preferred LLM_PROVIDER is tried first, then other providers
        that have API keys, falling back to local LLM.
        """
        all_providers = [
            (LLMProvider.OPENAI, settings.openai_api_key),
            (LLMProvider.ANTHROPIC, settings.anthropic_api_key),
            (LLMProvider.OPENROUTER, settings.openrouter_api_key),
            (LLMProvider.NVIDIA, settings.nvidia_api_key),
        ]

        preferred = getattr(LLMProvider, settings.llm_provider.upper(), None)
        ordered = []
        if preferred:
            ordered.append(preferred)
        ordered.extend([p for p, _ in all_providers if p != preferred])

        chain = []
        tried_preferred = False
        for provider in ordered:
            api_key = dict(all_providers).get(provider)
            if api_key:
                cfg = LLMConfig(provider=provider, model=settings.llm_model)
                if provider == preferred and not tried_preferred:
                    tried_preferred = True
                chain.append(cfg)
                logger.info(f"{provider.value.capitalize()} configured (has API key)")

        # Always add local as last resort
        chain.append(LLMConfig(
            provider=LLMProvider.LOCAL,
            model=settings.local_llm_model,
            base_url=settings.local_llm_url,
        ))
        logger.info("Local LLM available (always accessible)")

        if not chain or (len(chain) == 1 and chain[0].provider == LLMProvider.LOCAL):
            logger.warning("No cloud API keys configured. Will use local LLM only.")

        logger.info(f"Provider chain: {[p.provider.value for p in chain]}")
        return chain

    async def generate(self, messages: List[Union[Dict, LLMMessage]],
                       tools: List[Dict] = None,
                       config: Optional[LLMConfig] = None,
                       allow_failover: bool = True) -> LLMResponse:
        """Generate response with automatic failover between providers.

        Args:
            messages: List of message dicts or LLMMessage objects
            tools: Optional list of tool definitions
            config: Optional override config
            allow_failover: If True, falls back to next provider on failure
        """
        msg_objects = []
        for m in messages:
            if isinstance(m, dict):
                msg_objects.append(LLMMessage(
                    role=LLMRole(m.get("role", "user")),
                    content=m.get("content", ""),
                ))
            else:
                msg_objects.append(m)

        providers = [config] if config else self._providers

        last_error = None
        for i, provider_config in enumerate(providers):
            try:
                provider = _get_provider(provider_config)
                resp = await provider.generate(msg_objects, tools)

                self._token_tracker["total_prompt"] += resp.usage.get("prompt_tokens", 0)
                self._token_tracker["total_completion"] += resp.usage.get("completion_tokens", 0)

                return resp
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider_config.provider.value} "
                               f"({provider_config.model}) failed: {e}")
                if not allow_failover or i == len(providers) - 1:
                    raise

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    async def generate_stream(self, messages: List[Union[Dict, LLMMessage]],
                              config: Optional[LLMConfig] = None) -> AsyncGenerator[str, None]:
        msg_objects = []
        for m in messages:
            if isinstance(m, dict):
                msg_objects.append(LLMMessage(
                    role=LLMRole(m.get("role", "user")),
                    content=m.get("content", ""),
                ))
            else:
                msg_objects.append(m)

        provider_config = config or self._providers[0]
        provider = _get_provider(provider_config)
        async for chunk in provider.generate_stream(msg_objects):
            yield chunk

    def get_usage_stats(self) -> Dict:
        return dict(self._token_tracker)

    def reset_usage_stats(self):
        self._token_tracker = {"total_prompt": 0, "total_completion": 0}


# Global LLM client instance
llm_client = LLMClient()
