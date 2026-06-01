import pytest
from unittest.mock import patch, AsyncMock
from backend.orchestrator.engine.compaction.compactor import (
    Compactor,
    CompactionResult,
    COMPACT_TRIGGERS,
)


class TestCompactor:
    @pytest.fixture
    def compactor(self):
        return Compactor(max_context_tokens=1000, target_ratio=0.5)

    def test_should_compact_false_when_under_limit(self, compactor):
        messages = [{"role": "user", "content": "hi"}]
        assert compactor.should_compact(messages, 100) is False

    def test_should_compact_true_when_over_limit(self, compactor):
        messages = [{"role": "user", "content": "hi"}]
        assert compactor.should_compact(messages, 2000) is True

    @pytest.mark.asyncio
    async def test_compact_returns_error_when_few_messages(self, compactor):
        messages = [{"role": "user", "content": "hi"}]
        result = await compactor.compact(messages, "sess_1")
        assert result.success is False
        assert "Not enough messages" in result.error

    @pytest.mark.asyncio
    async def test_compact_success(self, compactor):
        messages = [
            {"role": "system", "content": "You are a bot"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I am fine"},
        ]
        with patch.object(compactor, "_summarize", new=AsyncMock(return_value="User greeted bot")) as mock_sum:
            result = await compactor.compact(messages, "sess_2")
            assert result.success is True
            assert result.summary == "User greeted bot"
            assert result.messages_removed > 0
            assert result.tokens_saved > 0
            mock_sum.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_compact_keeps_system_and_tail(self, compactor):
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
            {"role": "assistant", "content": "D"},
        ]
        with patch.object(compactor, "_summarize", new=AsyncMock(return_value="summary")):
            result = await compactor.compact(messages, "sess_3")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_compact_empty_summary_returns_error(self, compactor):
        messages = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
            {"role": "assistant", "content": "D"},
        ]
        with patch.object(compactor, "_summarize", new=AsyncMock(return_value="")):
            result = await compactor.compact(messages, "sess_4")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_compact_handles_exception_gracefully(self, compactor):
        messages = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
            {"role": "assistant", "content": "D"},
        ]
        with patch.object(compactor, "_summarize", new=AsyncMock(side_effect=RuntimeError("LLM failed"))):
            result = await compactor.compact(messages, "sess_5")
            assert result.success is False
            assert "LLM failed" in result.error

    @pytest.mark.asyncio
    async def test_summarize_calls_llm_client(self, compactor):
        messages = [{"role": "user", "content": "Hello world"}]
        with patch("backend.shared.llm_client.llm_client.generate", new=AsyncMock(return_value=type("R", (), {"content": "summary text"}))) as mock_gen:
            result = await compactor._summarize(messages, "gpt-4")
            assert result == "summary text"
            mock_gen.assert_awaited_once()

    def test_compaction_result_dataclass(self):
        r = CompactionResult(success=True, summary="done", tokens_saved=100, messages_removed=5)
        assert r.success is True
        assert r.summary == "done"

    def test_compact_triggers_defined(self):
        assert "overflow" in COMPACT_TRIGGERS
        assert "manual" in COMPACT_TRIGGERS
        assert "timeout" in COMPACT_TRIGGERS
        assert "auto" in COMPACT_TRIGGERS
