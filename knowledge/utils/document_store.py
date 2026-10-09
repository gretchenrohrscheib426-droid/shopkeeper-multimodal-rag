"""Mongo is the visibility authority; incomplete Milvus/MinIO writes stay invisible."""

from datetime import datetime, timezone
from knowledge.utils.client.storage_clients import StorageClients


def documents():
    return StorageClients.get_mongo_db()["documents"]


def versions():
    return StorageClients.get_mongo_db()["document_versions"]


def version_key(document_id, version):
    return document_id + ":" + version


def active_documents(owner: str) -> list[dict]:
    return list(
        documents()
        .find({"owner": owner, "status": "committed"}, {"_id": 0})
        .sort("updated_at", -1)
        .limit(500)
    )


def committed_version(owner, document_id, version):
    return versions().find_one(
        {
            "_id": version_key(document_id, version),
            "owner": owner,
            "status": "committed",
        }
    )


def publish(state):
    manifest = {
        "_id": version_key(state["document_id"], state["version"]),
        "owner": state["owner"],
        "document_id": state["document_id"],
        "source_id": state["source_id"],
        "version": state["version"],
        "file_title": state["file_title"],
        "item_name": state["item_name"],
        "entity_type": state["entity_type"],
        "chunk_ids": [c["chunk_id"] for c in state["chunks"]],
        "chunk_count": len(state["chunks"]),
        "images": state["images"],
        "original_object_key": state["original_object_key"],
        "processed_object_key": state["processed_object_key"],
        "status": "committed",
        "embedding_model": "BAAI/bge-m3",
        "embedding_revision": state["chunks"][0]["embedding_revision"],
        "entity_vector_id": state["entity_vector"]["chunk_id"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    versions().replace_one({"_id": manifest["_id"]}, manifest, upsert=True)
    # Publishing the active pointer is the last operation. Cross-store ACID is not claimed.
    pointer = {**manifest, "_id": state["document_id"]}
    documents().replace_one({"_id": pointer["_id"]}, pointer, upsert=True)
    if (
        documents().find_one({"_id": pointer["_id"], "version": state["version"]})
        is None
    ):
        raise RuntimeError("Mongo visibility commit readback failed")
