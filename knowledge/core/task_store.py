"""Single-process durable task journal. Interrupted work is never resumed as success."""

import json
import sqlite3
import threading
import time
import os
from pathlib import Path
from contextlib import contextmanager
from knowledge.core.paths import get_local_base_dir

TERMINAL = {"completed", "failed", "cancelled", "interrupted"}


class TaskCancelled(RuntimeError):
    pass


class TaskStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL,
                    status TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                    cancel INTEGER NOT NULL DEFAULT 0, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                    event TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS events_task ON events(task_id,seq);
            """)

    @contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()

    def create(self, task_id: str, owner: str = "local", kind: str = "import"):
        with self.connection() as db:
            db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?)",
                (
                    task_id,
                    owner,
                    kind,
                    "queued",
                    time.time(),
                    time.time(),
                    0,
                    json.dumps(
                        {
                            "running_list": [],
                            "done_list": [],
                            "durations": {},
                            "results": {},
                            "_runner_pid": os.getpid(),
                        }
                    ),
                ),
            )
        self.emit(task_id, "progress", {"status": "queued"})

    def get(self, task_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown task")
        result = dict(row)
        result.update(json.loads(result.pop("payload")))
        return result

    def mutate(self, task_id: str, operation):
        with self.connection() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError("Unknown task")
            payload = json.loads(row["payload"])
            operation(payload)
            db.execute(
                "UPDATE tasks SET payload=?,updated=? WHERE id=?",
                (json.dumps(payload, ensure_ascii=False), time.time(), task_id),
            )

    def emit(self, task_id: str, event: str, data: dict) -> int:
        with self.connection() as db:
            cur = db.execute(
                "INSERT INTO events(task_id,event,data,created) VALUES(?,?,?,?)",
                (task_id, event, json.dumps(data, ensure_ascii=False), time.time()),
            )
            return cur.lastrowid

    def events(self, task_id: str, after: int = 0) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM events WHERE task_id=? AND seq>? ORDER BY seq LIMIT 200",
                (task_id, after),
            ).fetchall()
        return [{**dict(row), "data": json.loads(row["data"])} for row in rows]

    def status(self, task_id: str, status: str, details: dict | None = None):
        with self.connection() as db:
            row = db.execute(
                "SELECT status,cancel FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Unknown task")
            if row["status"] in TERMINAL:
                return
            if (
                status == "completed"
                and row["cancel"]
                and not (details or {}).get("committed")
            ):
                status = "cancelled"
            db.execute(
                "UPDATE tasks SET status=?,updated=? WHERE id=?",
                (status, time.time(), task_id),
            )
            # Reentrant lock + same transaction: status and terminal event commit together.
            data = {"status": status, **(details or {})}
            event = "final" if status in TERMINAL else "progress"
            db.execute(
                "INSERT INTO events(task_id,event,data,created) VALUES(?,?,?,?)",
                (task_id, event, json.dumps(data, ensure_ascii=False), time.time()),
            )

    def cancel(self, task_id: str):
        with self.connection() as db:
            db.execute(
                "UPDATE tasks SET cancel=1 WHERE id=? AND status NOT IN (?,?,?,?)",
                (task_id, *sorted(TERMINAL)),
            )
        self.emit(task_id, "progress", {"cancel_requested": True})

    def check(self, task_id: str):
        if not task_id:
            return
        task = self.get(task_id)
        if task["status"] in TERMINAL:
            raise TaskCancelled("Task has already reached a terminal state")
        if task["cancel"]:
            raise TaskCancelled("Task cancellation requested")
        if time.time() - task["created"] > (1800 if task["kind"] == "import" else 300):
            raise TimeoutError("Task deadline exceeded")

    def recover(self, force=False):
        with self.connection() as db:
            rows = list(
                db.execute(
                    "SELECT id,payload FROM tasks WHERE status IN ('queued','processing')"
                )
            )
        ids = [
            row["id"]
            for row in rows
            if force or not process_alive(json.loads(row["payload"]).get("_runner_pid"))
        ]
        for task_id in ids:
            self.status(
                task_id, "interrupted", {"error": "进程已重启，请重新提交任务。"}
            )
        return ids


def process_alive(pid):
    if not isinstance(pid, int) or pid < 1:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            kernel.GetExitCodeProcess.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
            ]
            return (
                bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code)))
                and code.value == 259
            )
        finally:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


_store = None
_lock = threading.Lock()


def get_store() -> TaskStore:
    global _store
    with _lock:
        if _store is None:
            _store = TaskStore(Path(get_local_base_dir()) / "tasks.sqlite3")
        return _store
