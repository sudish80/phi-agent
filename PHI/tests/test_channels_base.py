import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.channels.base import (
    ChannelRegistry,
    BaseChannel,
    ChannelConfig,
    ChannelMessage,
    ChannelEvent,
    channel_registry,
)


@pytest.fixture
def registry():
    return ChannelRegistry()


@pytest.fixture
def mock_channel():
    ch = MagicMock(spec=BaseChannel)
    ch.name = "test_channel"
    ch.config = ChannelConfig(enabled=True)
    ch.start = AsyncMock()
    ch.stop = AsyncMock()
    return ch


@pytest.fixture
def disabled_channel():
    ch = MagicMock(spec=BaseChannel)
    ch.name = "disabled_channel"
    ch.config = ChannelConfig(enabled=False)
    ch.start = AsyncMock()
    ch.stop = AsyncMock()
    return ch


class TestChannelRegistry:
    def test_register_and_get(self, registry, mock_channel):
        registry.register(mock_channel)
        retrieved = registry.get("test_channel")
        assert retrieved is mock_channel

    def test_get_nonexistent(self, registry):
        assert registry.get("no_channel") is None

    def test_register_overwrites(self, registry, mock_channel):
        registry.register(mock_channel)
        ch2 = MagicMock(spec=BaseChannel)
        ch2.name = "test_channel"
        registry.register(ch2)
        assert registry.get("test_channel") is ch2

    def test_list_channels(self, registry, mock_channel):
        registry.register(mock_channel)
        channels = registry.list_channels()
        assert mock_channel in channels

    def test_list_channels_empty(self, registry):
        assert registry.list_channels() == []

    @pytest.mark.asyncio
    async def test_start_all_starts_enabled_channels(self, registry, mock_channel, disabled_channel):
        registry.register(mock_channel)
        registry.register(disabled_channel)
        await registry.start_all()
        mock_channel.start.assert_awaited_once()
        disabled_channel.start.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stop_all_stops_all_channels(self, registry, mock_channel, disabled_channel):
        registry.register(mock_channel)
        registry.register(disabled_channel)
        await registry.stop_all()
        mock_channel.stop.assert_awaited_once()
        disabled_channel.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_all_empty(self, registry):
        await registry.start_all()

    @pytest.mark.asyncio
    async def test_multiple_channels(self, registry):
        names = []
        for i in range(3):
            ch = MagicMock(spec=BaseChannel)
            ch.name = f"ch_{i}"
            ch.config = ChannelConfig(enabled=True)
            ch.start = AsyncMock()
            registry.register(ch)
            names.append(ch.name)
        assert len(registry.list_channels()) == 3
        for n in names:
            assert registry.get(n) is not None


class TestChannelMessage:
    def test_defaults(self):
        msg = ChannelMessage(id="msg_1", channel_id="ch_1", author_id="u_1")
        assert msg.id == "msg_1"
        assert msg.author_name == ""
        assert msg.content == ""
        assert msg.attachments == []
        assert msg.is_dm is True

    def test_full_constructor(self):
        msg = ChannelMessage(
            id="m1", channel_id="ch1", author_id="u1",
            author_name="Alice", content="Hello",
            attachments=["f1"], reply_to="m0",
            thread_id="th1", is_dm=False,
            metadata={"source": "web"},
        )
        assert msg.author_name == "Alice"
        assert msg.content == "Hello"
        assert msg.reply_to == "m0"
        assert msg.thread_id == "th1"
        assert msg.is_dm is False


class TestChannelEvent:
    def test_all_events_defined(self):
        expected = ["MESSAGE", "EDIT", "DELETE", "REACTION", "TYPING", "MEMBER_JOIN", "MEMBER_LEAVE"]
        for name in expected:
            assert hasattr(ChannelEvent, name)

    def test_event_values(self):
        assert ChannelEvent.MESSAGE.value == "message"
        assert ChannelEvent.EDIT.value == "edit"
        assert ChannelEvent.DELETE.value == "delete"
        assert ChannelEvent.REACTION.value == "reaction"


class TestChannelConfig:
    def test_defaults(self):
        cfg = ChannelConfig()
        assert cfg.enabled is True
        assert cfg.dm_policy == "open"
        assert cfg.allow_from == ["*"]
        assert cfg.deny_from == []
        assert cfg.command_prefix == "/"
        assert cfg.respond_to_mentions is True
        assert cfg.respond_to_dms is True

    def test_custom_config(self):
        cfg = ChannelConfig(enabled=False, dm_policy="closed", command_prefix="!")
        assert cfg.enabled is False
        assert cfg.dm_policy == "closed"
        assert cfg.command_prefix == "!"
