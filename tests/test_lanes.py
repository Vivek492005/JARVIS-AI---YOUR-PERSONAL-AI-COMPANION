"""Tests for Task 2.3: lane queue (jarvis.core.lanes)."""

import threading
import time

import pytest

from jarvis.core.errors import LaneCancelled
from jarvis.core.events import Interrupt, reset_bus
from jarvis.core.lanes import CancelToken, LaneQueue, Priority


@pytest.fixture()
def lane():
    reset_bus()
    q = LaneQueue()
    q.start()
    yield q
    q.stop()
    reset_bus()


def _wait_for(pred, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_serial_execution_no_overlap(lane):
    """Two commands run strictly serially — never in parallel."""
    events = []
    lock = threading.Lock()

    def task(name, dur=0.15):
        def fn(token):
            with lock:
                events.append(("start", name))
            time.sleep(dur)
            with lock:
                events.append(("end", name))
        return fn

    lane.submit(task("a"), name="a")
    lane.submit(task("b"), name="b")
    assert _wait_for(lambda: len(events) == 4)
    assert events == [("start", "a"), ("end", "a"), ("start", "b"), ("end", "b")]


def test_priority_ordering(lane):
    """Higher priority jumps the queue even when submitted later."""
    order = []

    lane.submit(lambda tok: order.append("bg"), priority=Priority.BACKGROUND, name="bg")
    # Give the worker a moment to pick up bg, then queue a TASK behind it.
    time.sleep(0.05)
    lane.submit(lambda tok: order.append("task"), priority=Priority.TASK, name="task")
    lane.submit(lambda tok: order.append("bg2"), priority=Priority.BACKGROUND, name="bg2")
    assert _wait_for(lambda: len(order) == 3)
    # bg started first (already running), but task must precede bg2.
    assert order.index("task") < order.index("bg2")


def test_interrupt_cancels_running_task_fast(lane):
    """Plan done-when: Interrupt cancels the current action < 250 ms."""
    stopped = threading.Event()

    def long_task(token):
        t0 = time.time()
        while not token.cancelled:
            time.sleep(0.005)
        stopped.set()
        return time.time() - t0

    lane.submit(long_task, name="long")
    time.sleep(0.1)  # let it start
    t0 = time.time()
    lane.interrupt(reason="user barge-in")
    assert stopped.wait(timeout=2.0)
    assert time.time() - t0 < 0.25


def test_interrupt_flushes_task_and_background_but_keeps_confirm(lane):
    ran = []
    gate = threading.Event()

    def blocker(token):
        gate.wait(timeout=5)

    lane.submit(blocker, name="blocker")
    time.sleep(0.05)
    lane.submit(lambda tok: ran.append("task"), priority=Priority.TASK, name="t")
    lane.submit(lambda tok: ran.append("bg"), priority=Priority.BACKGROUND, name="b")
    lane.submit(lambda tok: ran.append("confirm"), priority=Priority.CONFIRM, name="c")
    lane.interrupt(reason="test")
    gate.set()
    assert _wait_for(lambda: ran == ["confirm"])
    assert lane.qsize() == 0


def test_cancel_token_check_raises():
    tok = CancelToken()
    tok.check()  # not cancelled: no raise
    tok.cancel()
    assert tok.cancelled
    with pytest.raises(LaneCancelled):
        tok.check()


def test_crashing_task_does_not_kill_worker(lane):
    done = threading.Event()

    def bad(token):
        raise RuntimeError("boom")

    def good(token):
        done.set()

    lane.submit(bad, name="bad")
    lane.submit(good, name="good")
    assert done.wait(timeout=5.0)


def test_on_done_callback(lane):
    results = []
    done = threading.Event()

    def on_done(result, exc):
        results.append((result, exc))
        done.set()

    lane.submit(lambda tok: 42, name="t", on_done=on_done)
    assert done.wait(timeout=5.0)
    assert results[0] == (42, None)


def test_interrupt_emits_event_and_fires_hooks(lane):
    from jarvis.core.events import get_bus
    seen = []
    get_bus().on(Interrupt, seen.append)
    hooks = []
    lane.on_interrupt(lambda: hooks.append(1))
    lane.interrupt(reason="stop")
    assert hooks == [1]
    assert len(seen) == 1
    assert seen[0].reason == "stop"


def test_pre_cancelled_item_is_skipped(lane):
    ran = []
    tok = lane.submit(lambda t: ran.append(1), name="t")
    tok.cancel()
    time.sleep(0.3)
    assert ran == []
