"""Replayable SSE. A disconnect never removes another subscriber's events."""

import asyncio
import json
from knowledge.core.task_store import get_store, TERMINAL


class SSEEvent:
    PROGRESS = "progress"
    DELTA = "delta"
    FINAL = "final"


def create_sse_queue(task_id):
    return get_store().get(task_id)


def remove_sse_queue(task_id):
    # Compatibility: journal retention is an administrative operation.
    return None


def get_sse_queue(task_id):
    return get_store().get(task_id)


def push_sse_event(task_id, event, data):
    if task_id:
        get_store().emit(task_id, event, data)


def _sse_pack(event, data, event_id=None):
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return (
        prefix
        + f"event: {event}\ndata: "
        + json.dumps(data, ensure_ascii=False)
        + "\n\n"
    )


async def sse_generator(task_id, request, after=0):
    last_heartbeat = 0.0
    while not await request.is_disconnected():
        events = await asyncio.to_thread(get_store().events, task_id, after)
        for row in events:
            after = row["seq"]
            payload = {
                **row["data"],
                "task_id": task_id,
                "event_id": after,
                "timestamp": row["created"],
            }
            yield _sse_pack(row["event"], payload, after)
            if row["event"] == "final":
                return
        if (
            not events
            and (await asyncio.to_thread(get_store().get, task_id))["status"]
            in TERMINAL
        ):
            return
        now = asyncio.get_running_loop().time()
        if now - last_heartbeat >= 10:
            yield ": heartbeat\n\n"
            last_heartbeat = now
        await asyncio.sleep(0.2)
