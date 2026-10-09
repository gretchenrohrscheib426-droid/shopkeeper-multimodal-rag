"""Real socket/SDK failure checks in this process only; never stop the user's services.

These are fault-injection tests, not successful model/DB functionality claims.
"""

import argparse
import json
import os
import socket
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHOPKEEPER_ENV_FILE", str(ROOT / ".env.local"))
from knowledge.core.task_store import get_store
from knowledge.core.configuration import required
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils import document_store
from knowledge.service.query_service import QueryService
from knowledge.service.upload_service import UpLoadService


@contextmanager
def override(name, value):
    previous = os.environ.get(name)
    os.environ[name] = value
    StorageClients.close()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous
        StorageClients.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/verification/baseline/failures.json",
    )
    args = parser.parse_args()
    report = {
        "kind": "real_sdk_fault_injection",
        "checks": [],
        "containers_changed": False,
    }
    store = get_store()
    source = ROOT / "examples/public/manual/掌柜智库 操作手册.md"
    before = {
        x["document_id"]: x["version"] for x in document_store.active_documents("local")
    }
    docid = next(
        x["document_id"]
        for x in document_store.active_documents("local")
        if x["file_title"] == "掌柜智库 操作手册"
    )
    # Bind but do not listen: the port cannot belong to an unrelated local service.
    with socket.socket() as blocked:
        blocked.bind(("127.0.0.1", 0))
        port = blocked.getsockname()[1]

        def query():
            task = uuid.uuid4().hex
            session = "fault-" + task
            store.create(task, "local", "query")
            service = QueryService()
            service.reserve_session("local", session)
            service.run_query_graph(
                session,
                task,
                "上传文件大小上限是多少？",
                False,
                "local",
                [docid],
                "dense",
            )
            return store.get(task)

        for name, variable, value in [
            ("mongo_disconnected", "MONGO_URL", f"mongodb://127.0.0.1:{port}"),
            ("milvus_disconnected", "MILVUS_URL", f"http://127.0.0.1:{port}"),
        ]:
            start = time.monotonic()
            with override("STORAGE_TIMEOUT_SECONDS", "1"), override(variable, value):
                row = query()
            report["checks"].append(
                {
                    "name": name,
                    "status": "PASS"
                    if row["status"] == "failed" and not row["results"].get("answer")
                    else "FAIL",
                    "task_id": row["id"],
                    "terminal_status": row["status"],
                    "error": row["results"].get("error"),
                    "seconds": round(time.monotonic() - start, 3),
                }
            )
        task = uuid.uuid4().hex
        directory = ROOT / "data/failure-checks" / task
        directory.mkdir(parents=True)
        sample = directory / "storage-failure.md"
        sample.write_text(
            "# Storage failure check\n\nThis local diagnostic must never become a committed document.\n",
            encoding="utf-8",
        )
        store.create(task, "local", "import")
        start = time.monotonic()
        with (
            override("STORAGE_TIMEOUT_SECONDS", "1"),
            override("MINIO_ENDPOINT", f"127.0.0.1:{port}"),
        ):
            UpLoadService().run_import_graph(
                task, str(sample), str(directory), "local", "fault-" + task
            )
        row = store.get(task)
        report["checks"].append(
            {
                "name": "minio_disconnected",
                "status": "PASS" if row["status"] == "failed" else "FAIL",
                "task_id": task,
                "terminal_status": row["status"],
                "error": row["results"].get("error"),
                "seconds": round(time.monotonic() - start, 3),
            }
        )
    # An intentionally invalid credential sent only to the configured model provider.
    # The real saved key is never changed, printed or sent anywhere else.
    from openai import OpenAI, APIStatusError, APITimeoutError

    for name, kwargs, expected in [
        (
            "model_invalid_key",
            {"api_key": "invalid-diagnostic-credential", "timeout": 8},
            APIStatusError,
        ),
        (
            "model_deadline",
            {"api_key": required("OPENAI_API_KEY"), "timeout": 0.001},
            APITimeoutError,
        ),
    ]:
        start = time.monotonic()
        check = {"name": name, "status": "FAIL"}
        try:
            with OpenAI(
                base_url=required("OPENAI_API_BASE"), max_retries=0, **kwargs
            ) as client:
                client.chat.completions.create(
                    model=required("LLM_DEFAULT_MODEL"),
                    max_tokens=4,
                    messages=[{"role": "user", "content": "Reply OK"}],
                )
        except expected as exc:
            code = getattr(exc, "status_code", None)
            check.update(
                status="PASS"
                if name == "model_deadline" or code in (401, 403)
                else "FAIL",
                error_type=type(exc).__name__,
                http_status=code,
            )
        except Exception as exc:
            check["error_type"] = type(exc).__name__
        check["seconds"] = round(time.monotonic() - start, 3)
        report["checks"].append(check)
    task = uuid.uuid4().hex
    store.create(task, "local", "import")
    store.cancel(task)
    directory = ROOT / "data/failure-checks" / task
    directory.mkdir(parents=True)
    UpLoadService().run_import_graph(task, str(source), str(directory), "local")
    row = store.get(task)
    report["checks"].append(
        {
            "name": "cancel_before_processing",
            "status": "PASS" if row["status"] == "cancelled" else "FAIL",
            "terminal_status": row["status"],
            "task_id": task,
        }
    )
    after = {
        x["document_id"]: x["version"] for x in document_store.active_documents("local")
    }
    report["checks"].append(
        {
            "name": "old_documents_preserved",
            "status": "PASS"
            if all(after.get(k) == v for k, v in before.items())
            else "FAIL",
            "old_document_count": len(before),
        }
    )
    report["status"] = (
        "PASS" if all(x["status"] == "PASS" for x in report["checks"]) else "FAIL"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return report["status"] != "PASS"


if __name__ == "__main__":
    raise SystemExit(main())
