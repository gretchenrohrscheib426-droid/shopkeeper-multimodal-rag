import os
import uuid
from pathlib import Path
from threading import Lock
from fastapi import UploadFile
from knowledge.core.paths import get_local_base_dir
from knowledge.core.task_store import get_store, TaskCancelled
from knowledge.processor.import_processor.main_graph import import_app
from knowledge.processor.import_processor.nodes.entry_node import EntryNode
from knowledge.processor.import_processor.state import create_default_state
from knowledge.utils import document_store
from knowledge.utils.task_util import set_task_result

_import_lock = Lock()


class UpLoadService:
    def get_base_dir(self) -> str:
        return str(Path(get_local_base_dir()) / "imports")

    def run_import_graph(
        self,
        task_id: str,
        import_file_path: str,
        file_dir: str,
        owner: str = "local",
        source_label: str = "",
    ):
        store = get_store()
        store.status(task_id, "processing")
        acquired = False
        try:
            while not acquired:
                store.check(task_id)
                acquired = _import_lock.acquire(timeout=0.2)
            state = create_default_state(
                task_id=task_id,
                owner=owner,
                import_file_path=import_file_path,
                file_dir=file_dir,
                source_label=source_label,
            )
            identity = EntryNode().process(state)
            store.mutate(
                task_id,
                lambda p: p.update(
                    {
                        "import_attempt": {
                            "document_id": identity["document_id"],
                            "version": identity["version"],
                            "artifact_prefix": f"documents/{identity['document_id']}/{identity['version']}",
                            "source_name": Path(import_file_path).name,
                        }
                    }
                ),
            )
            active = document_store.documents().find_one(
                {
                    "_id": identity["document_id"],
                    "owner": owner,
                    "status": "committed",
                    "version": identity["version"],
                }
            )
            if active:
                result = {
                    "document_id": active["document_id"],
                    "version": active["version"],
                    "chunk_count": active["chunk_count"],
                    "already_imported": True,
                    "committed": True,
                }
                store.emit(
                    task_id,
                    "progress",
                    {"node": "idempotency_check", "phase": "reused_committed_version"},
                )
            else:
                final = import_app.invoke(state)
                if not final.get("committed") or not final.get("chunk_count"):
                    raise RuntimeError(
                        "Import ended without verified artifacts and committed chunks"
                    )
                result = {
                    k: final[k]
                    for k in ["document_id", "version", "chunk_count", "committed"]
                }
                result["image_count"] = len(final.get("images", []))
            set_task_result(task_id, "import", result)
            store.status(task_id, "completed", result)
        except TaskCancelled:
            store.status(task_id, "cancelled")
        except Exception as exc:
            # Exception classes/node identify the failed component without exposing keys or SDK URLs.
            details = {
                "error_type": type(exc).__name__,
                "node": getattr(exc, "node_name", "preflight"),
                "error": "导入失败；请检查对应节点配置、服务就绪状态和本机诊断日志。",
            }
            set_task_result(task_id, "error", details)
            store.status(task_id, "failed", details)
            log = Path(file_dir) / "failure.txt"
            log.write_text(type(exc).__name__ + ": " + str(exc), encoding="utf-8")
        finally:
            if acquired:
                _import_lock.release()

    def process_upload_file(self, file: UploadFile, owner: str = "local"):
        name = file.filename or ""
        if (
            not name
            or Path(name).name != name
            or "/" in name
            or "\\" in name
            or ":" in name
            or name in {".", ".."}
        ):
            raise ValueError("Invalid upload filename")
        if Path(name).suffix.lower() not in {".pdf", ".md", ".docx"}:
            raise ValueError("Only PDF, Markdown and DOCX are supported")
        task_id = uuid.uuid4().hex
        directory = Path(self.get_base_dir()) / task_id
        directory.mkdir(parents=True)
        path = self.save_upload_file_to_local(file, str(directory))
        get_store().create(task_id, owner, "import")
        return task_id, path, str(directory)

    def save_upload_file_to_local(self, file: UploadFile, file_dir: str) -> str:
        name = file.filename or ""
        if (
            not name
            or Path(name).name != name
            or "/" in name
            or "\\" in name
            or ":" in name
        ):
            raise ValueError("Invalid upload filename")
        directory = Path(file_dir).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        temporary = directory / (name + ".part")
        total = 0
        limit = int(os.getenv("MAX_UPLOAD_MB", "40")) * 1024 * 1024
        try:
            with temporary.open("xb") as stream:
                while data := file.file.read(1024 * 1024):
                    total += len(data)
                    if total > limit:
                        raise ValueError("Upload exceeds size limit")
                    stream.write(data)
            if not total:
                raise ValueError("Upload is empty")
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return str(target)
