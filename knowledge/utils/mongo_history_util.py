import time
from knowledge.utils.client.storage_clients import StorageClients


def _get_collection():
    return StorageClients.get_mongo_db()["chat_messages_v2"]


def save_turn(state):
    # One document per turn makes the user+assistant pair atomic on standalone Mongo.
    row = {
        "_id": state["task_id"],
        "owner": state["owner"],
        "session_id": state["session_id"],
        "task_id": state["task_id"],
        "query": state["original_query"],
        "answer": state["answer"],
        "rewritten_query": state.get("rewritten_query", ""),
        "item_names": state.get("item_names", []),
        "document_ids": [d["document_id"] for d in state.get("document_scope", [])],
        "citations": state.get("citations", []),
        "answer_kind": state.get("answer_kind", "answer"),
        "usage": {
            k: state.get(k, {}) for k in ["rewrite_usage", "hyde_usage", "answer_usage"]
        },
        "ts": time.time(),
    }
    _get_collection().replace_one({"_id": row["_id"]}, row, upsert=True)
    if _get_collection().find_one({"_id": row["_id"], "owner": state["owner"]}) is None:
        raise RuntimeError("History readback failed")


def get_recent_messages(
    session_id: str, limit: int = 10, owner: str = "local"
) -> list[dict]:
    rows = list(
        _get_collection()
        .find({"session_id": session_id, "owner": owner})
        .sort("ts", -1)
        .limit(max(1, min(limit, 100)))
    )
    messages = []
    for row in reversed(rows):
        common = {
            k: row.get(k)
            for k in [
                "session_id",
                "task_id",
                "rewritten_query",
                "item_names",
                "document_ids",
                "ts",
            ]
        }
        messages.extend(
            [
                {**common, "role": "user", "text": row["query"]},
                {
                    **common,
                    "role": "assistant",
                    "text": row["answer"],
                    "citations": row.get("citations", []),
                    "answer_kind": row.get("answer_kind"),
                },
            ]
        )
    return messages[-limit:]


def clear_history(session_id: str, owner: str = "local") -> int:
    return (
        _get_collection()
        .delete_many({"session_id": session_id, "owner": owner})
        .deleted_count
    )
