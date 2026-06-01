import json
import pytest
from backend.gateway.protocol import (
    GatewayOp,
    GatewayPayload,
    MessageCreateData,
    GatewayConfig,
)


class TestGatewayOp:
    def test_all_ops_defined(self):
        expected = [
            "HELLO", "HEARTBEAT", "HEARTBEAT_ACK",
            "MESSAGE_CREATE", "MESSAGE_UPDATE", "MESSAGE_DELETE",
            "TYPING_START", "TYPING_STOP",
            "TOOL_CALL", "TOOL_RESULT",
            "ERROR", "RECONNECT", "INVALID_SESSION",
        ]
        for name in expected:
            assert hasattr(GatewayOp, name)

    def test_op_values(self):
        assert GatewayOp.HELLO.value == "hello"
        assert GatewayOp.HEARTBEAT.value == "heartbeat"
        assert GatewayOp.MESSAGE_CREATE.value == "message_create"
        assert GatewayOp.TOOL_CALL.value == "tool_call"
        assert GatewayOp.ERROR.value == "error"
        assert GatewayOp.RECONNECT.value == "reconnect"


class TestGatewayPayload:
    def test_to_json(self):
        payload = GatewayPayload(
            op=GatewayOp.MESSAGE_CREATE,
            data={"content": "hello"},
            seq=1,
            session_id="sess_1",
        )
        raw = payload.to_json()
        obj = json.loads(raw)
        assert obj["op"] == "message_create"
        assert obj["d"] == {"content": "hello"}
        assert obj["seq"] == 1
        assert obj["session_id"] == "sess_1"

    def test_from_json(self):
        raw = json.dumps({
            "op": "heartbeat",
            "d": {"ts": 123},
            "seq": 5,
            "session_id": "s_abc",
        })
        payload = GatewayPayload.from_json(raw)
        assert payload.op == GatewayOp.HEARTBEAT
        assert payload.data == {"ts": 123}
        assert payload.seq == 5
        assert payload.session_id == "s_abc"

    def test_roundtrip(self):
        original = GatewayPayload(
            op=GatewayOp.TOOL_RESULT,
            data={"tool": "search", "result": "ok"},
            seq=42,
            session_id="test_sess",
        )
        raw = original.to_json()
        restored = GatewayPayload.from_json(raw)
        assert restored.op == original.op
        assert restored.data == original.data
        assert restored.seq == original.seq
        assert restored.session_id == original.session_id

    def test_from_json_missing_fields_uses_defaults(self):
        raw = json.dumps({"op": "error"})
        payload = GatewayPayload.from_json(raw)
        assert payload.op == GatewayOp.ERROR
        assert payload.data == {}
        assert payload.seq == 0
        assert payload.session_id == ""

    def test_default_data_is_empty_dict(self):
        payload = GatewayPayload(op=GatewayOp.HELLO)
        assert payload.data == {}

    def test_default_seq_is_zero(self):
        payload = GatewayPayload(op=GatewayOp.HELLO)
        assert payload.seq == 0


class TestMessageCreateData:
    def test_defaults(self):
        msg = MessageCreateData(content="test")
        assert msg.content == "test"
        assert msg.channel_id == ""
        assert msg.author_id == ""
        assert msg.attachments == []
        assert msg.session_id == ""

    def test_full_constructor(self):
        msg = MessageCreateData(
            content="hello world",
            channel_id="ch_1",
            author_id="user_1",
            attachments=["img.png"],
            session_id="sess_1",
        )
        assert msg.content == "hello world"
        assert msg.channel_id == "ch_1"
        assert msg.author_id == "user_1"
        assert msg.attachments == ["img.png"]
        assert msg.session_id == "sess_1"

    def test_attachments_mutable(self):
        msg = MessageCreateData(content="x")
        msg.attachments.append("file.pdf")
        assert "file.pdf" in msg.attachments


class TestGatewayConfig:
    def test_defaults(self):
        cfg = GatewayConfig()
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8765
        assert cfg.max_payload_size == 409600
        assert cfg.heartbeat_interval == 30.0
        assert cfg.reconnect_delay == 5.0

    def test_custom_values(self):
        cfg = GatewayConfig(host="0.0.0.0", port=9000, heartbeat_interval=15.0)
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 9000
        assert cfg.heartbeat_interval == 15.0
