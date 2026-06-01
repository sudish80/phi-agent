import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CompanionProfile:
    name: str
    system_prompt_modifier: str = ""
    voice_tone: str = "neutral"
    response_style: str = "balanced"
    memory_priority: int = 5

    def modify_prompt(self, base_prompt: str) -> str:
        if self.system_prompt_modifier:
            return f"{base_prompt}\n\n{self.system_prompt_modifier}"
        return base_prompt

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "system_prompt_modifier": self.system_prompt_modifier,
            "voice_tone": self.voice_tone,
            "response_style": self.response_style,
            "memory_priority": self.memory_priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CompanionProfile":
        return cls(
            name=data.get("name", "custom"),
            system_prompt_modifier=data.get("system_prompt_modifier", ""),
            voice_tone=data.get("voice_tone", "neutral"),
            response_style=data.get("response_style", "balanced"),
            memory_priority=data.get("memory_priority", 5),
        )


class ProfileRegistry:
    def __init__(self):
        self._profiles: dict[str, CompanionProfile] = {}
        self._load_builtins()

    def _load_builtins(self):
        self._profiles["assistant"] = CompanionProfile(
            name="assistant",
            system_prompt_modifier="You are a helpful AI assistant. Be concise, accurate, and professional.",
            voice_tone="professional",
            response_style="concise",
            memory_priority=5,
        )
        self._profiles["friend"] = CompanionProfile(
            name="friend",
            system_prompt_modifier="You are a friendly companion. Be warm, casual, and supportive. Use conversational language.",
            voice_tone="warm",
            response_style="conversational",
            memory_priority=8,
        )
        self._profiles["mentor"] = CompanionProfile(
            name="mentor",
            system_prompt_modifier="You are a knowledgeable mentor. Guide the user with explanations, ask probing questions, and encourage growth.",
            voice_tone="encouraging",
            response_style="explanatory",
            memory_priority=6,
        )
        self._profiles["tutor"] = CompanionProfile(
            name="tutor",
            system_prompt_modifier="You are a patient tutor. Break down complex topics, provide examples, and check understanding.",
            voice_tone="patient",
            response_style="structured",
            memory_priority=7,
        )

    def register(self, profile: CompanionProfile, overwrite: bool = False):
        if profile.name in self._profiles and not overwrite:
            raise ValueError(f"Profile '{profile.name}' already exists. Use overwrite=True to replace.")
        self._profiles[profile.name] = profile
        logger.info("Registered profile '%s'", profile.name)

    def get(self, name: str) -> Optional[CompanionProfile]:
        return self._profiles.get(name)

    def list_profiles(self) -> list[dict]:
        return [p.to_dict() for p in self._profiles.values()]

    def unregister(self, name: str):
        if name in ("assistant", "friend", "mentor", "tutor"):
            raise ValueError(f"Cannot unregister built-in profile '{name}'")
        self._profiles.pop(name, None)
        logger.info("Unregistered profile '%s'", name)


_registry = ProfileRegistry()


def get_profile(name: str) -> Optional[CompanionProfile]:
    return _registry.get(name)


def list_profiles() -> list[dict]:
    return _registry.list_profiles()


def register_profile(profile: CompanionProfile, overwrite: bool = False):
    _registry.register(profile, overwrite=overwrite)
