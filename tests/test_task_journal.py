from concurrent.futures import ThreadPoolExecutor
import pytest
from knowledge.core.task_store import TaskStore, TaskCancelled


def test_replay_survives_reopen_and_multiple_subscribers(tmp_path):
    path = tmp_path / "tasks.sqlite"
    store = TaskStore(path)
    store.create("a")
    event = store.emit("a", "delta", {"text": "real event fixture"})
    store.status("a", "completed", {"answer": "verified test fixture"})
    replay = TaskStore(path)
    assert replay.events("a", event) == store.events("a", event)
    assert replay.events("a", event)[0]["event"] == "final"
    assert replay.events("a", event) == replay.events("a", event)


def test_cancel_and_failure_cannot_become_completed(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite")
    store.create("a")
    store.cancel("a")
    with pytest.raises(TaskCancelled):
        store.check("a")
    store.status("a", "completed")
    assert store.get("a")["status"] == "cancelled"
    store.status("a", "completed")
    assert len([e for e in store.events("a") if e["event"] == "final"]) == 1
    store.create("b")
    store.status("b", "failed")
    store.status("b", "completed")
    assert store.get("b")["status"] == "failed"


def test_restart_marks_pending_interrupted_and_concurrent_events_are_unique(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite")
    store.create("a")
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda x: store.emit("a", "progress", {"n": x}), range(40)))
    assert len(set(ids)) == 40
    assert store.recover(force=True) == ["a"]
    assert store.get("a")["status"] == "interrupted"


def test_live_worker_is_not_interrupted_by_another_server_start(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite")
    store.create("a")
    assert store.recover() == []
    assert store.get("a")["status"] == "queued"
    store.status("a", "interrupted")
    with pytest.raises(TaskCancelled):
        store.check("a")
