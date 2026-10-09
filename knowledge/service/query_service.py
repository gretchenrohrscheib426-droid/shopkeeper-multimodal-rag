import uuid
from pathlib import Path
from threading import Lock
from knowledge.core.paths import get_local_base_dir
from knowledge.core.task_store import get_store, TaskCancelled
from knowledge.processor.query_processor.main_graph import query_app
from knowledge.processor.query_processor.state import create_default_state
from knowledge.utils.task_util import set_task_result, get_task_result
from knowledge.utils.mongo_history_util import get_recent_messages, clear_history

_guard = Lock()
_active_sessions = set()


class QueryService:
    @staticmethod
    def generate_session_id():
        return str(uuid.uuid4())

    @staticmethod
    def generate_task_id():
        return uuid.uuid4().hex

    def reserve_session(self, owner, session_id):
        with _guard:
            key = (owner, session_id)
            if key in _active_sessions:
                raise ValueError("A query is already running in this session")
            _active_sessions.add(key)

    def release_session(self, owner, session_id):
        with _guard:
            _active_sessions.discard((owner, session_id))

    def run_query_graph(
        self,
        session_id,
        task_id,
        query,
        is_stream,
        owner="local",
        selected_document_ids=None,
        retrieval_mode="rerank",
        candidate_limit=10,
    ):
        store = get_store()
        store.status(task_id, "processing")
        try:
            state = create_default_state(
                session_id=session_id,
                task_id=task_id,
                original_query=query,
                is_stream=is_stream,
                owner=owner,
                selected_document_ids=selected_document_ids or [],
                retrieval_mode=retrieval_mode,
                candidate_limit=candidate_limit,
            )
            result = query_app.invoke(state)
            if not result.get("history_saved") or not result.get("answer"):
                raise RuntimeError("Query ended without saved validated answer")
            payload = {
                k: result.get(k)
                for k in [
                    "answer",
                    "citations",
                    "answer_kind",
                    "clarification_options",
                    "rewritten_query",
                    "embedding_chunks",
                    "hyde_embedding_chunks",
                    "rrf_chunks",
                    "reranked_docs",
                    "hybrid_status",
                    "hyde_status",
                    "web_status",
                    "join_count",
                    "answer_attempts",
                ]
            }
            payload["usage"] = {
                k: result.get(k, {})
                for k in ["rewrite_usage", "hyde_usage", "answer_usage"]
            }
            payload["degraded"] = any(
                str(result.get(k, "")).startswith("failed:")
                for k in ["hybrid_status", "hyde_status", "web_status"]
            )
            set_task_result(task_id, "query", payload)
            set_task_result(task_id, "answer", result["answer"])
            store.status(task_id, "completed", {**payload, "committed": True})
        except TaskCancelled:
            store.status(task_id, "cancelled")
        except Exception as exc:
            details = {
                "error_type": type(exc).__name__,
                "node": getattr(exc, "node_name", "query"),
                "error": "查询失败，没有发布未经验证的答案。请查看组件就绪状态。",
            }
            set_task_result(task_id, "error", details)
            store.status(task_id, "failed", details)
            log = Path(get_local_base_dir()) / "query-errors"
            log.mkdir(parents=True, exist_ok=True)
            (log / (task_id + ".txt")).write_text(
                type(exc).__name__ + ": " + str(exc), encoding="utf-8"
            )
        finally:
            self.release_session(owner, session_id)

    def get_task_result(self, task_id):
        return get_task_result(task_id, "answer")

    def get_history(self, session_id, limit=50, owner="local"):
        return get_recent_messages(session_id, limit, owner)

    def clear_history(self, session_id, owner="local"):
        return clear_history(session_id, owner)
