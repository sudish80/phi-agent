import os
import uuid
import tempfile
import pytest
from unittest.mock import patch
from backend.media.image_gen import (
    DummyImageGenerator,
    ImageGenRegistry,
    ImageGenerator,
    generate_image,
    get_image_gen_registry,
)
from backend.media.audio import (
    DummyAudioProcessor,
    AudioRegistry,
    AudioProcessor,
    text_to_speech,
    speech_to_text,
    get_audio_registry,
)


class TestDummyImageGenerator:
    @pytest.fixture
    def gen(self):
        return DummyImageGenerator()

    def test_name(self, gen):
        assert gen.get_name() == "dummy"

    @pytest.mark.asyncio
    async def test_generate_image_returns_url(self, gen):
        url = await gen.generate_image("a cute cat", "512x512")
        assert url.startswith("https://placehold.co/512x512")
        assert "a+cute+cat" in url

    @pytest.mark.asyncio
    async def test_generate_image_default_size(self, gen):
        url = await gen.generate_image("hello")
        assert "1024x1024" in url

    @pytest.mark.asyncio
    async def test_generate_image_has_unique_id(self, gen):
        url1 = await gen.generate_image("test")
        url2 = await gen.generate_image("test")
        assert url1 != url2

    def test_is_image_generator(self, gen):
        assert isinstance(gen, ImageGenerator)


class TestImageGenRegistry:
    @pytest.fixture
    def registry(self):
        r = ImageGenRegistry()
        return r

    def test_defaults_include_dummy(self, registry):
        names = registry.list_generators()
        assert "dummy" in names

    def test_register_new_generator(self, registry):
        gen = DummyImageGenerator()
        registry.register(gen, overwrite=True)
        assert registry.get("dummy") is gen

    def test_duplicate_raises(self, registry):
        gen = DummyImageGenerator()
        with pytest.raises(ValueError):
            registry.register(gen)

    def test_unregister(self, registry):
        registry.unregister("dummy")
        assert registry.get("dummy") is None

    def test_get_nonexistent(self, registry):
        assert registry.get("nope") is None

    @pytest.mark.asyncio
    async def test_generate_image_function(self):
        url = await generate_image("test", "256x256")
        assert "256x256" in url

    @pytest.mark.asyncio
    async def test_generate_image_unknown_generator(self):
        with pytest.raises(ValueError):
            await generate_image("test", generator="nonexistent")


class TestDummyAudioProcessor:
    @pytest.fixture
    def processor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = DummyAudioProcessor(audio_dir=tmpdir)
            yield p

    def test_name(self, processor):
        assert processor.get_name() == "dummy"

    def test_text_to_speech_creates_file(self, processor):
        path = processor.text_to_speech("Hello world")
        assert os.path.exists(path)
        with open(path, "r") as f:
            content = f.read()
        assert content == "DUMMY_TTS:Hello world"

    def test_text_to_speech_custom_path(self, processor):
        custom = os.path.join(processor.audio_dir, "custom.wav")
        path = processor.text_to_speech("Hi", output_path=custom)
        assert path == custom
        assert os.path.exists(custom)

    def test_speech_to_text_returns_text(self, processor):
        path = processor.text_to_speech("Testing STT")
        result = processor.speech_to_text(path)
        assert result == "Testing STT"

    def test_speech_to_text_nonexistent_file(self, processor):
        with pytest.raises(FileNotFoundError):
            processor.speech_to_text("/nonexistent/file.wav")

    def test_speech_to_text_fallback_for_non_tts_file(self, processor):
        path = os.path.join(processor.audio_dir, "raw.txt")
        with open(path, "w") as f:
            f.write("Some random audio content")
        result = processor.speech_to_text(path)
        assert "raw" in result

    def test_is_audio_processor(self, processor):
        assert isinstance(processor, AudioProcessor)


class TestAudioRegistry:
    @pytest.fixture
    def registry(self):
        r = AudioRegistry()
        return r

    def test_defaults_include_dummy(self, registry):
        names = registry.list_processors()
        assert "dummy" in names

    def test_register_new_processor(self, registry):
        with tempfile.TemporaryDirectory() as tmpdir:
            proc = DummyAudioProcessor(audio_dir=tmpdir)
            registry.register(proc, overwrite=True)
            assert registry.get("dummy") is proc

    def test_duplicate_raises(self, registry):
        proc = DummyAudioProcessor(audio_dir=tempfile.mkdtemp())
        with pytest.raises(ValueError):
            registry.register(proc)

    def test_unregister(self, registry):
        registry.unregister("dummy")
        assert registry.get("dummy") is None

    def test_text_to_speech_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.media.audio.DEFAULT_AUDIO_DIR", tmpdir):
                path = text_to_speech("functional test")
                assert os.path.exists(path)

    def test_speech_to_text_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("backend.media.audio.DEFAULT_AUDIO_DIR", tmpdir):
                path = text_to_speech("round trip")
                result = speech_to_text(path)
                assert result == "round trip"

    def test_unknown_processor_raises(self):
        with pytest.raises(ValueError):
            text_to_speech("hello", processor="nonexistent")
