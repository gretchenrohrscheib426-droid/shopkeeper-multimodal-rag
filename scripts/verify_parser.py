import json, os, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHOPKEEPER_ENV_FILE", str(ROOT / ".env.local"))
from knowledge.core.task_store import get_store
from knowledge.processor.import_processor.nodes.pdf_to_md_node import PdfToMdNode

source = ROOT / "examples/public/manual/掌柜智库 操作手册.pdf"
task = uuid.uuid4().hex
directory = ROOT / "data/parser-verification" / task
directory.mkdir(parents=True)
store = get_store()
store.create(task, "local", "import")
store.status(task, "processing")
start = time.monotonic()
report = {"kind": "real_mineru", "task_id": task, "directory": str(directory)}
try:
    result = PdfToMdNode().process(
        {"task_id": task, "pdf_path": str(source), "file_dir": str(directory)}
    )
    report.update(status="PASS", **result)
    store.status(task, "completed")
except Exception as exc:
    report.update(status="FAIL", error_type=type(exc).__name__, message=str(exc))
    store.status(task, "failed")
report["seconds"] = round(time.monotonic() - start, 3)
(ROOT / "artifacts/verification/baseline/parser.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(report, ensure_ascii=False))
raise SystemExit(0 if report["status"] == "PASS" else 1)
