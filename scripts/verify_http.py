"""Real local HTTP, SSE replay and session concurrency; uses the configured key in memory."""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHOPKEEPER_ENV_FILE", str(ROOT / ".env.local"))
from knowledge.core.configuration import required
import httpx


def events(text):
    result = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        values = dict(
            line.split(": ", 1) for line in block.splitlines() if ": " in line
        )
        if "id" in values:
            result.append(
                {
                    "id": int(values["id"]),
                    "event": values["event"],
                    "data": json.loads(values["data"]),
                }
            )
    return result


async def main():
    checks = {}
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
        timeout=180,
        headers={"Authorization": "Bearer " + required("APP_API_TOKEN")},
    ) as client:

        async def read(path):
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

        documents = (await read("/documents"))["items"]
        doc = next(d for d in documents if d["file_title"] == "掌柜智库 图文表格手册")
        session = "http-" + uuid.uuid4().hex
        body = {
            "query": "单个上传文件大小上限是多少？",
            "is_stream": True,
            "session_id": session,
            "selected_document_ids": [doc["document_id"]],
        }
        started = time.monotonic()
        response = await client.post("/query", json=body)
        response.raise_for_status()
        task = response.json()["task_id"]
        duplicate = await client.post("/query", json=body)
        checks["same_session_lock"] = {
            "pass": duplicate.status_code == 409,
            "http_status": duplicate.status_code,
        }
        streams = await asyncio.gather(
            client.get("/stream/" + task), client.get("/stream/" + task)
        )
        parsed = [events(r.text) for r in streams]
        status = await read("/status/" + task)
        checks["real_query"] = {
            "pass": status["status"] == "completed",
            "task_id": task,
            "seconds": round(time.monotonic() - started, 3),
        }
        checks["two_subscribers"] = {
            "pass": parsed[0] == parsed[1]
            and sum(e["event"] == "final" for e in parsed[0]) == 1,
            "events": len(parsed[0]),
        }
        cursor = parsed[0][len(parsed[0]) // 2]["id"]
        replay = events(
            (
                await client.get(
                    "/stream/" + task, headers={"Last-Event-ID": str(cursor)}
                )
            ).text
        )
        checks["reconnect"] = {
            "pass": replay == [e for e in parsed[0] if e["id"] > cursor],
            "replayed_events": len(replay),
        }
        history = await read("/history/" + session)
        checks["history_atomic_turn"] = {
            "pass": len(history["items"]) == 2,
            "messages": len(history["items"]),
        }
        citation = status["results"]["query"]["citations"][0]
        source = await read(citation["source_url"])
        checks["source"] = {
            "pass": all(q in source["chunk"]["content"] for q in citation["quotes"]),
            "chunk_id": citation["chunk_id"],
        }
        anonymous = await client.get(
            citation["source_url"], headers={"Authorization": ""}
        )
        checks["private_source"] = {
            "pass": anonymous.status_code == 401,
            "http_status": anonymous.status_code,
        }
        body.update(
            query="资料中没有的超级管理员密码是什么？",
            session_id="http-negative-" + uuid.uuid4().hex,
            is_stream=False,
        )
        negative = await client.post("/query", json=body)
        negative.raise_for_status()
        checks["unsupported_question"] = {
            "pass": negative.json()["answer_kind"] == "no_evidence",
            "task_id": negative.json()["task_id"],
        }
        body.update(
            query="请解释上传、检索和引用校验流程。",
            session_id="http-cancel-" + uuid.uuid4().hex,
            is_stream=True,
        )
        cancel_task = (await client.post("/query", json=body)).json()["task_id"]
        await client.post("/tasks/" + cancel_task + "/cancel")
        await client.get("/stream/" + cancel_task)
        cancelled = await read("/status/" + cancel_task)
        checks["cancellation"] = {
            "pass": cancelled["status"] == "cancelled",
            "task_id": cancel_task,
            "status": cancelled["status"],
        }
        body.update(
            query="这个怎么用？",
            session_id="http-clarify-" + uuid.uuid4().hex,
            is_stream=False,
            selected_document_ids=[],
        )
        clarify = await client.post("/query", json=body)
        clarify.raise_for_status()
        checks["clarification"] = {
            "pass": clarify.json()["answer_kind"] == "clarification",
            "task_id": clarify.json()["task_id"],
            "answer_kind": clarify.json()["answer_kind"],
        }
    report = {
        "kind": "real_http",
        "checks": checks,
        "passed": sum(c["pass"] for c in checks.values()),
        "total": len(checks),
    }
    output = ROOT / "artifacts/verification/baseline/http.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return report["passed"] != report["total"]


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
