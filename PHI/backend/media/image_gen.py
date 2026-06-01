import logging
import uuid
from abc import ABC, abstractmethod
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


class ImageGenerator(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def generate_image(self, prompt: str, size: str = "1024x1024") -> str:
        ...

    def get_name(self) -> str:
        return self.name


class DummyImageGenerator(ImageGenerator):
    def __init__(self):
        super().__init__("dummy")

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> str:
        logger.info("Dummy image generation for prompt: '%s' (size: %s)", prompt, size)
        image_id = uuid.uuid4().hex[:12]
        return f"https://placehold.co/{size.replace('x', 'x')}/EEE/31343C?text={prompt[:50].replace(' ', '+')}&id={image_id}"


class ImageGenRegistry:
    def __init__(self):
        self._generators: dict[str, ImageGenerator] = {}
        self._lock = Lock()
        self._register_defaults()

    def _register_defaults(self):
        self.register(DummyImageGenerator())

    def register(self, generator: ImageGenerator, overwrite: bool = False):
        with self._lock:
            if generator.name in self._generators and not overwrite:
                raise ValueError(f"Generator '{generator.name}' already registered")
            self._generators[generator.name] = generator
            logger.info("Registered image generator '%s'", generator.name)

    def unregister(self, name: str):
        with self._lock:
            self._generators.pop(name, None)
            logger.info("Unregistered image generator '%s'", name)

    def get(self, name: str = "dummy") -> Optional[ImageGenerator]:
        with self._lock:
            return self._generators.get(name)

    def list_generators(self) -> list[str]:
        with self._lock:
            return list(self._generators.keys())


_registry = ImageGenRegistry()


async def generate_image(prompt: str, size: str = "1024x1024", generator: str = "dummy") -> str:
    gen = _registry.get(generator)
    if gen is None:
        raise ValueError(f"Unknown image generator '{generator}'. Available: {_registry.list_generators()}")
    return await gen.generate_image(prompt, size)


def get_image_gen_registry() -> ImageGenRegistry:
    return _registry
