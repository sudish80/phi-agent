"""Model Catalog — registry of all supported models with capabilities."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ModelCapability:
    tool_calling: bool = True
    streaming: bool = True
    vision: bool = False
    audio: bool = False
    function_calling: bool = True
    max_context: int = 8192
    max_output: int = 4096
    supports_system_prompt: bool = True
    supports_temperature: bool = True
    supports_reasoning: bool = False


@dataclass
class ModelEntry:
    id: str
    provider: str
    name: str
    capability: ModelCapability = field(default_factory=ModelCapability)
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    is_default: bool = False


MODEL_CATALOG: Dict[str, ModelEntry] = {
    # OpenAI
    "gpt-4o": ModelEntry("gpt-4o", "openai", "GPT-4o",
        ModelCapability(max_context=128000, max_output=16384), 2.50, 10.00, True),
    "gpt-4o-mini": ModelEntry("gpt-4o-mini", "openai", "GPT-4o Mini",
        ModelCapability(max_context=128000, max_output=16384), 0.15, 0.60),
    "o1": ModelEntry("o1", "openai", "o1",
        ModelCapability(max_context=200000, vision=True, supports_reasoning=True), 15.00, 60.00),
    "o3-mini": ModelEntry("o3-mini", "openai", "o3 Mini",
        ModelCapability(max_context=200000, supports_reasoning=True), 1.10, 4.40),

    # Anthropic
    "claude-sonnet-4-20250514": ModelEntry("claude-sonnet-4-20250514", "anthropic", "Claude Sonnet 4",
        ModelCapability(max_context=200000, max_output=8192, vision=True), 3.00, 15.00),
    "claude-haiku-3-5": ModelEntry("claude-haiku-3-5", "anthropic", "Claude Haiku 3.5",
        ModelCapability(max_context=200000, max_output=8192, vision=True), 0.80, 4.00),

    # Google
    "gemini-2.5-pro": ModelEntry("gemini-2.5-pro", "google", "Gemini 2.5 Pro",
        ModelCapability(max_context=1000000, max_output=8192, vision=True, audio=True), 1.25, 10.00),

    # Local
    "llama-3-70b": ModelEntry("llama-3-70b", "local", "Llama 3 70B",
        ModelCapability(max_context=8192, max_output=4096), 0.0, 0.0),

    # NVIDIA
    "nvidia-nemotron": ModelEntry("nvidia-nemotron", "nvidia", "NVIDIA Nemotron",
        ModelCapability(max_context=128000, max_output=4096), 0.0, 0.0),
}


def get_model(model_id: str) -> Optional[ModelEntry]:
    return MODEL_CATALOG.get(model_id)


def get_default_model() -> ModelEntry:
    for m in MODEL_CATALOG.values():
        if m.is_default:
            return m
    return MODEL_CATALOG.get("gpt-4o", list(MODEL_CATALOG.values())[0])


def list_models_by_provider(provider: str) -> List[ModelEntry]:
    return [m for m in MODEL_CATALOG.values() if m.provider == provider]


def list_all_models() -> List[ModelEntry]:
    return list(MODEL_CATALOG.values())
