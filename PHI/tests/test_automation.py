import json
import tempfile
import time
import pytest
from unittest.mock import AsyncMock, patch
from backend.automation.tasks import TaskQueue, Task, TaskStatus, task_queue
from backend.automation.schedule import (
    ScheduleManager,
    ScheduleEntry,
    get_schedule_manager,
)
from backend.automation.webhook_receiver import WebhookReceiver, webhook_receiver


class TestTaskQueue:
    @pytest.fixture
    def queue(self):
        return TaskQueue()

    def test_create_task(self, queue):
        task = queue.create_task("Test Task", "echo", {"msg": "hello"})
        assert task.name == "Test Task"
        assert task.workflow == "echo"
        assert task.params == {"msg": "hello"}
        assert task.status == TaskStatus.PENDING
        assert task.id is not None

    def test_create_task_generates_id(self, queue):
        task = queue.create_task("T", "w")
        assert len(task.id) == 12

    def test_get_task(self, queue):
        created = queue.create_task("Get Me", "wf")
        retrieved = queue.get_task(created.id)
        assert retrieved is created

    def test_get_nonexistent(self, queue):
        assert queue.get_task("nope") is None

    @pytest.mark.asyncio
    async def test_execute_task_success(self, queue):
        async def handler(params):
            return f"processed {params['x']}"

        queue.register_handler("multiply", handler)
        task = queue.create_task("Multiply", "multiply", {"x": 42})
        await queue.execute_task(task.id)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "processed 42"

    @pytest.mark.asyncio
    async def test_execute_task_no_handler(self, queue):
        task = queue.create_task("Orphan", "no_handler")
        await queue.execute_task(task.id)
        assert task.status == TaskStatus.FAILED
        assert "No handler" in task.error

    @pytest.mark.asyncio
    async def test_execute_task_handler_fails(self, queue):
        async def failing(params):
            raise ValueError("oops")

        queue.register_handler("risky", failing)
        task = queue.create_task("Risky", "risky")
        await queue.execute_task(task.id)
        assert task.status == TaskStatus.FAILED
        assert "oops" in task.error

    @pytest.mark.asyncio
    async def test_execute_nonexistent_task(self, queue):
        await queue.execute_task("ghost")

    def test_list_tasks(self, queue):
        t1 = queue.create_task("A", "wf1")
        t2 = queue.create_task("B", "wf2")
        tasks = queue.list_tasks()
        assert len(tasks) >= 2

    def test_list_tasks_limited(self, queue):
        for i in range(5):
            queue.create_task(f"T{i}", "wf")
        tasks = queue.list_tasks(limit=3)
        assert len(tasks) == 3

    def test_list_tasks_ordered_by_newest_first(self, queue):
        t1 = queue.create_task("Old", "wf")
        time.sleep(0.01)
        t2 = queue.create_task("New", "wf")
        tasks = queue.list_tasks()
        assert tasks[0].id == t2.id


class TestScheduleManager:
    @pytest.fixture
    def manager(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            path = f.name
        mgr = ScheduleManager(storage_path=path)
        yield mgr

    def test_add_schedule_generates_id(self, manager):
        entry = ScheduleEntry(time="14:00", action="remind")
        eid = manager.add_schedule(entry)
        assert eid.startswith("schedule_")

    def test_add_schedule_keeps_given_id(self, manager):
        entry = ScheduleEntry(id="my_id", time="10:00", action="ping")
        eid = manager.add_schedule(entry)
        assert eid == "my_id"

    def test_remove_schedule(self, manager):
        eid = manager.add_schedule(ScheduleEntry(time="12:00", action="x"))
        assert manager.remove_schedule(eid) is True
        assert manager.get_schedule(eid) is None

    def test_remove_nonexistent(self, manager):
        assert manager.remove_schedule("ghost") is False

    def test_get_schedule(self, manager):
        eid = manager.add_schedule(ScheduleEntry(time="09:00", action="alarm"))
        entry = manager.get_schedule(eid)
        assert entry.action == "alarm"

    def test_list_schedules(self, manager):
        manager.add_schedule(ScheduleEntry(time="08:00", action="a"))
        manager.add_schedule(ScheduleEntry(time="09:00", action="b"))
        assert len(manager.list_schedules()) == 2

    def test_list_schedules_active_only(self, manager):
        manager.add_schedule(ScheduleEntry(time="08:00", action="active"))
        inactive_id = manager.add_schedule(ScheduleEntry(time="09:00", action="inactive"))
        manager.toggle_active(inactive_id, False)
        entries = manager.list_schedules(active_only=True)
        assert len(entries) == 1

    def test_check_due_returns_matching(self, manager):
        entry = ScheduleEntry(time="00:00", action="daily")
        manager.add_schedule(entry)
        due = manager.check_due()
        assert isinstance(due, list)

    def test_toggle_active(self, manager):
        eid = manager.add_schedule(ScheduleEntry(time="15:00", action="x"))
        assert manager.toggle_active(eid, False) is True
        entry = manager.get_schedule(eid)
        assert entry.active is False

    def test_toggle_active_nonexistent(self, manager):
        assert manager.toggle_active("ghost", False) is False

    def test_is_due_inactive(self):
        entry = ScheduleEntry(id="x", time="00:00", action="x", active=False)
        assert entry.is_due() is False

    def test_persist_entries(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            path = f.name
        mgr1 = ScheduleManager(storage_path=path)
        eid = mgr1.add_schedule(ScheduleEntry(time="16:00", action="persist_test"))
        mgr2 = ScheduleManager(storage_path=path)
        assert mgr2.get_schedule(eid) is not None
        assert mgr2.get_schedule(eid).action == "persist_test"


class TestWebhookReceiver:
    @pytest.fixture
    def receiver(self):
        r = WebhookReceiver()
        return r

    @pytest.mark.asyncio
    async def test_dispatch_routes_to_handler(self, receiver):
        async def my_handler(payload, headers):
            return f"Handled: {payload['event']}"

        receiver.register("/my/route", my_handler)
        result = await receiver.dispatch("/my/route", {"event": "test"})
        assert result == "Handled: test"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_route(self, receiver):
        result = await receiver.dispatch("/unknown", {})
        assert result == "Not found"

    @pytest.mark.asyncio
    async def test_signature_verification_passes(self, receiver):
        async def handler(payload, headers):
            return "ok"

        receiver.register("/secure", handler, secret="mysecret")
        payload = {"msg": "hello"}
        body = json.dumps(payload).encode()
        import hmac, hashlib
        sig = hmac.new(b"mysecret", body, hashlib.sha256).hexdigest()
        result = await receiver.dispatch("/secure", payload, {"X-Hub-Signature-256": sig})
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_signature_verification_fails(self, receiver):
        async def handler(payload, headers):
            return "ok"

        receiver.register("/secure", handler, secret="mysecret")
        result = await receiver.dispatch("/secure", {"msg": "hello"}, {"X-Hub-Signature-256": "wrongsig"})
        assert result == "Invalid signature"

    @pytest.mark.asyncio
    async def test_no_secret_skips_verification(self, receiver):
        async def handler(payload, headers):
            return "ok"

        receiver.register("/open", handler)
        result = await receiver.dispatch("/open", {"msg": "hi"}, {"X-Hub-Signature-256": "anything"})
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_handle_github_push(self, receiver):
        payload = {"repository": {"full_name": "test/repo"}, "ref": "refs/heads/main"}
        result = await receiver.handle_github_push(payload, {})
        assert "test/repo" in result
        assert "main" in result

    @pytest.mark.asyncio
    async def test_handle_slack_command(self, receiver):
        payload = {"command": "/weather", "text": "London", "user_name": "alice"}
        result = await receiver.handle_slack_command(payload, {})
        assert "/weather" in result
        assert "London" in result

    def test_verify_signature_no_route_returns_true(self, receiver):
        assert receiver.verify_signature("/no-route", b"payload", "sig") is True
