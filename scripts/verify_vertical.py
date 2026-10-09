"""Real services + GPU embeddings + paid provider calls; no mock fallback."""

import json, os, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHOPKEEPER_ENV_FILE", str(ROOT / ".env.local"))
from knowledge.core.task_store import get_store
from knowledge.service.upload_service import UpLoadService
from knowledge.service.query_service import QueryService
from knowledge.utils import document_store


def main():
    source = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "examples/public/manual/掌柜智库 操作手册.md"
    )
    question = sys.argv[2] if len(sys.argv) > 2 else "单个上传文件大小上限是多少？"
    store = get_store()
    report = {"kind": "real_vertical", "source": source.name, "checks": {}}
    started = time.monotonic()
    task = uuid.uuid4().hex
    directory = ROOT / "data/verification" / task
    directory.mkdir(parents=True)
    store.create(task, "local", "import")
    UpLoadService().run_import_graph(task, str(source), str(directory), "local")
    imported = store.get(task)
    report["checks"]["import"] = {
        "task_id": task,
        "status": imported["status"],
        "results": imported["results"],
        "seconds": round(time.monotonic() - started, 3),
        "durations": imported["durations"],
    }
    print(
        "import", json.dumps(report["checks"]["import"], ensure_ascii=False), flush=True
    )
    if imported["status"] == "completed":
        docid = imported["results"]["import"]["document_id"]
        doc = document_store.documents().find_one({"_id": docid})
        report["checks"]["manifest"] = {
            "status": "PASS",
            "chunks": doc["chunk_count"],
            "images": len(doc["images"]),
            "version": doc["version"],
        }
        again = uuid.uuid4().hex
        store.create(again, "local", "import")
        UpLoadService().run_import_graph(again, str(source), str(directory), "local")
        repeated = store.get(again)
        report["checks"]["idempotency"] = {
            "status": repeated["status"],
            "results": repeated["results"],
        }
        query = uuid.uuid4().hex
        session = "vertical-" + uuid.uuid4().hex
        store.create(query, "local", "query")
        service = QueryService()
        service.reserve_session("local", session)
        start = time.monotonic()
        service.run_query_graph(session, query, question, True, "local", [docid])
        result = store.get(query)
        report["checks"]["query"] = {
            "task_id": query,
            "session_id": session,
            "status": result["status"],
            "results": result["results"],
            "seconds": round(time.monotonic() - start, 3),
            "durations": result["durations"],
        }
        print(
            "query",
            json.dumps(
                {
                    "task_id": query,
                    "status": result["status"],
                    "seconds": report["checks"]["query"]["seconds"],
                    "answer": result["results"].get("query", {}).get("answer"),
                    "citation_count": len(
                        result["results"].get("query", {}).get("citations", [])
                    ),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    report["status"] = (
        "PASS"
        if report["checks"].get("query", {}).get("status") == "completed"
        and report["checks"]["query"]["results"]["query"].get("citations")
        else "FAIL"
    )
    output = (
        Path(sys.argv[3])
        if len(sys.argv) > 3
        else ROOT
        / "artifacts/verification/baseline"
        / ("vertical-" + source.suffix[1:] + ".json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
