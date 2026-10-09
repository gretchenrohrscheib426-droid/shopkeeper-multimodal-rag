import math
from threading import Lock
from pymilvus import DataType
from knowledge.core.configuration import required
from knowledge.core.task_store import get_store
from knowledge.processor.import_processor.base import BaseNode
from knowledge.processor.import_processor.state import ImportGraphState
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils import document_store

_schema_lock = Lock()


class ImportMilvusNode(BaseNode):
    name = "import_milvus_node"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        chunks = state.get("chunks", [])
        if not chunks:
            raise ValueError("No chunks to commit")
        for chunk in chunks:
            dense = chunk.get("dense_vector", [])
            sparse = chunk.get("sparse_vector", {})
            if (
                len(dense) != 1024
                or not all(math.isfinite(v) for v in dense)
                or not any(dense)
            ):
                raise ValueError("Invalid dense vector before commit")
            if not sparse or any(
                not isinstance(k, int) or k < 0 or not math.isfinite(v) or v <= 0
                for k, v in sparse.items()
            ):
                raise ValueError("Invalid sparse vector before commit")
        client = StorageClients.get_milvus_client()
        collection = required("CHUNKS_COLLECTION")
        self._create_chunks_collection(collection, client, 1024)
        for i in range(0, len(chunks), 32):
            get_store().check(state.get("task_id", ""))
            batch = chunks[i : i + 32]
            result = client.upsert(collection, data=batch)
            if result.get("upsert_count") != len(batch):
                raise RuntimeError("Milvus upsert count mismatch")
        client.flush(collection)
        for i in range(0, len(chunks), 100):
            expected = {c["chunk_id"] for c in chunks[i : i + 100]}
            rows = client.get(
                collection,
                ids=sorted(expected),
                output_fields=["chunk_id", "version"],
                consistency_level="Strong",
            )
            if {r["chunk_id"] for r in rows} != expected or any(
                r["version"] != state["version"] for r in rows
            ):
                raise RuntimeError("Milvus persisted chunk verification failed")
        get_store().check(state.get("task_id", ""))
        entity = state["entity_vector"]
        entity_collection = required("ENTITY_NAME_COLLECTION")
        if entity_collection == collection:
            raise ValueError("Entity and chunk collections must be distinct")
        self._create_chunks_collection(entity_collection, client, 1024)
        if client.upsert(entity_collection, data=[entity]).get("upsert_count") != 1:
            raise RuntimeError("Entity upsert count mismatch")
        client.flush(entity_collection)
        persisted = client.get(
            entity_collection,
            [entity["chunk_id"]],
            output_fields=["version", "document_id"],
            consistency_level="Strong",
        )
        if (
            len(persisted) != 1
            or persisted[0]["version"] != state["version"]
            or persisted[0]["document_id"] != state["document_id"]
        ):
            raise RuntimeError("Entity vector readback failed")
        get_store().check(state.get("task_id", ""))
        document_store.publish(state)
        return {"committed": True, "chunk_count": len(chunks)}

    def _create_chunks_collection(self, collection, client, dim):
        with _schema_lock:
            if client.has_collection(collection):
                schema = client.describe_collection(collection)
                fields = {f["name"]: f for f in schema["fields"]}
                if (
                    fields.get("chunk_id", {}).get("type") != DataType.VARCHAR
                    or int(
                        fields.get("dense_vector", {}).get("params", {}).get("dim", 0)
                    )
                    != dim
                ):
                    raise ValueError(
                        "Collection schema is incompatible; choose a new versioned collection"
                    )
                if schema.get("auto_id"):
                    raise ValueError("Collection must use stable, explicit chunk IDs")
                return
            schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field(
                "chunk_id", DataType.VARCHAR, is_primary=True, max_length=64
            )
            schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=dim)
            schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
            for name, length in [
                ("owner", 64),
                ("document_id", 64),
                ("version", 64),
                ("content", 65535),
                ("item_name", 1024),
            ]:
                schema.add_field(name, DataType.VARCHAR, max_length=length)
            index = client.prepare_index_params()
            index.add_index(
                field_name="dense_vector", index_type="AUTOINDEX", metric_type="COSINE"
            )
            index.add_index(
                field_name="sparse_vector",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="IP",
            )
            client.create_collection(collection, schema=schema, index_params=index)
