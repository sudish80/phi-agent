import asyncio
import pytest
from backend.orchestrator.engine.lane.manager import (
    CommandLane,
    LaneManager,
    LanePriority,
    LaneTask,
)


class TestCommandLane:
    @pytest.mark.asyncio
    async def test_enqueue_and_execute(self):
        lane = CommandLane("test")
        lane.start()
        results = []

        async def task():
            results.append("done")
            return "ok"

        await lane.enqueue(LaneTask(
            priority=LanePriority.NORMAL,
            enqueued_at=0,
            task_id="t1",
            coro=task,
        ))
        await asyncio.sleep(0.1)
        assert results == ["done"]
        await lane.stop()

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        lane = CommandLane("test-prio", max_concurrent=1)
        lane.start()
        order = []

        async def make_task(name):
            async def _inner():
                await asyncio.sleep(0.05)
                order.append(name)
                return name
            return _inner

        bg_task = await make_task("background")
        fg_task = await make_task("foreground")

        await lane.enqueue(LaneTask(LanePriority.BACKGROUND, 1, "bg", bg_task))
        await lane.enqueue(LaneTask(LanePriority.FOREGROUND, 2, "fg", fg_task))

        await asyncio.sleep(0.3)
        assert len(order) == 2
        await lane.stop()

    @pytest.mark.asyncio
    async def test_pending_count(self):
        lane = CommandLane("test-pending", max_concurrent=1)
        lane.start()

        async def slow():
            await asyncio.sleep(0.5)
            return None

        await lane.enqueue(LaneTask(LanePriority.NORMAL, 1, "s1", slow))
        await lane.enqueue(LaneTask(LanePriority.NORMAL, 2, "s2", slow))
        await asyncio.sleep(0.05)
        assert lane.pending >= 1
        await lane.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_worker(self):
        lane = CommandLane("test-stop")
        lane.start()
        assert lane._worker_task is not None
        await lane.stop()
        assert lane._worker_task is None

    @pytest.mark.asyncio
    async def test_max_concurrent_respected(self):
        lane = CommandLane("test-concurrent", max_concurrent=1)
        lane.start()
        running = []

        async def slow():
            running.append("start")
            await asyncio.sleep(0.3)
            running.append("end")

        await lane.enqueue(LaneTask(LanePriority.NORMAL, 1, "t1", slow))
        await lane.enqueue(LaneTask(LanePriority.NORMAL, 2, "t2", slow))
        await asyncio.sleep(0.1)
        assert lane.running <= 1
        await lane.stop()

    @pytest.mark.asyncio
    async def test_task_failure_does_not_crash_worker(self):
        lane = CommandLane("test-fail")
        lane.start()

        async def failing():
            raise RuntimeError("boom")

        results = []

        async def ok():
            results.append("ok")
            return "ok"

        await lane.enqueue(LaneTask(LanePriority.NORMAL, 1, "fail", failing))
        await lane.enqueue(LaneTask(LanePriority.NORMAL, 2, "ok", ok))
        await asyncio.sleep(0.2)
        assert results == ["ok"]
        await lane.stop()

    @pytest.mark.asyncio
    async def test_running_property(self):
        lane = CommandLane("test-running")
        lane.start()

        async def slow():
            await asyncio.sleep(0.5)

        await lane.enqueue(LaneTask(LanePriority.NORMAL, 1, "slow", slow))
        await asyncio.sleep(0.05)
        assert lane.running == 1
        await lane.stop()


class TestLaneManager:
    @pytest.mark.asyncio
    async def test_enqueue_foreground(self):
        mgr = LaneManager()
        mgr.start()
        results = []

        async def task():
            results.append("fg")

        await mgr.enqueue_foreground("sess1", "t1", task)
        await asyncio.sleep(0.2)
        assert results == ["fg"]
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_enqueue_background(self):
        mgr = LaneManager()
        mgr.start()
        results = []

        async def task():
            results.append("bg")

        await mgr.enqueue_background("sess2", "t2", task)
        await asyncio.sleep(0.2)
        assert results == ["bg"]
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_session_lane_is_reused(self):
        mgr = LaneManager()
        mgr.start()
        lane1 = await mgr.get_session_lane("common")
        lane2 = await mgr.get_session_lane("common")
        assert lane1 is lane2
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_different_sessions_different_lanes(self):
        mgr = LaneManager()
        mgr.start()
        lane1 = await mgr.get_session_lane("sess_a")
        lane2 = await mgr.get_session_lane("sess_b")
        assert lane1 is not lane2
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_enqueue_cron(self):
        mgr = LaneManager()
        mgr.start()
        results = []

        async def task():
            results.append("cron")

        await mgr.enqueue_cron("c1", task)
        await asyncio.sleep(0.2)
        assert results == ["cron"]
        await mgr.stop()
