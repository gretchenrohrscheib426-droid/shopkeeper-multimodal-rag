"""Real isolated read/write checks. Never deletes existing buckets or collections."""

import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHOPKEEPER_ENV_FILE", str(ROOT / ".env.local"))
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils.client.ai_clients import AIClients
from knowledge.utils.embedding_util import generate_bge_m3_hybrid_vectors
from knowledge.utils.object_storage import put_verified
from knowledge.core.configuration import required
from pymilvus import DataType


def run():
    report = {
        "kind": "real_services",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": {},
    }
    probe_id = "doctor-" + uuid.uuid4().hex
    scratch = ROOT / "data" / "doctor"
    scratch.mkdir(parents=True, exist_ok=True)
    for name, check in [
        ("mongo", lambda: mongo(probe_id)),
        ("minio", lambda: minio(probe_id, scratch)),
        ("milvus", milvus),
    ]:
        start = time.monotonic()
        try:
            report["checks"][name] = {"status": "PASS", **check()}
        except Exception as exc:
            report["checks"][name] = {
                "status": "FAIL",
                "error_type": type(exc).__name__,
                "code": getattr(exc, "code", None),
            }
        report["checks"][name]["seconds"] = round(time.monotonic() - start, 3)
        print(name, report["checks"][name], flush=True)
    report["status"] = (
        "PASS"
        if all(v["status"] == "PASS" for v in report["checks"].values())
        else "FAIL"
    )
    out = ROOT / "artifacts/verification/baseline/doctor.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    StorageClients.close()
    return report


def mongo(probe_id):
    db = StorageClients.get_mongo_db()
    ping = db.command("ping")
    server = db.command("hello")
    from datetime import timezone

    delta = abs(
        time.time() - server["localTime"].replace(tzinfo=timezone.utc).timestamp()
    )
    row = {"_id": probe_id, "kind": "isolated_readback", "message": "掌柜智库写读校验"}
    db["doctor_probes"].insert_one(row)
    if db["doctor_probes"].find_one({"_id": probe_id}) != row:
        raise RuntimeError("Mongo readback mismatch")
    return {
        "ping": ping["ok"],
        "readback": True,
        "server_clock_delta_seconds": round(delta, 2),
    }


def minio(probe_id, scratch):
    path = scratch / (probe_id + ".txt")
    path.write_text("掌柜智库 MinIO 实际读回校验\n" + probe_id, encoding="utf-8")
    key = put_verified(path, "doctor/" + path.name, "text/plain; charset=utf-8")
    client = StorageClients.get_minio_client()
    bucket = required("MINIO_BUCKET_NAME")
    listed = [
        obj.object_name
        for obj in client.list_objects(bucket, prefix=key, recursive=True)
    ]
    if key not in listed:
        raise RuntimeError("MinIO uploaded object not listed")
    return {
        "verified_object": key,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bucket": bucket,
        "upload": True,
        "list_objects": True,
        "size_verified": True,
        "sha256_readback": True,
    }


def milvus():
    client = StorageClients.get_milvus_client()
    name = "shopkeeper_doctor_v2"
    version = client.get_server_version()
    if not client.has_collection(name):
        schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=1024)
        schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
        indexes = client.prepare_index_params()
        indexes.add_index(
            field_name="dense_vector", index_type="FLAT", metric_type="COSINE"
        )
        indexes.add_index(
            field_name="sparse_vector",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="IP",
        )
        client.create_collection(name, schema=schema, index_params=indexes)
    vectors = generate_bge_m3_hybrid_vectors(
        AIClients.get_bge_m3_client(), ["掌柜智库文档导入后保留来源和切片标识。"]
    )
    result = client.upsert(
        name,
        [
            {
                "id": "provenance-probe",
                "dense_vector": vectors["dense"][0],
                "sparse_vector": vectors["sparse"][0],
            }
        ],
    )
    client.flush(name)
    hits = client.search(
        name,
        [vectors["dense"][0]],
        anns_field="dense_vector",
        limit=1,
        consistency_level="Strong",
    )
    if not hits or hits[0][0]["id"] != "provenance-probe":
        raise RuntimeError("Milvus query mismatch")
    return {
        "server_version": version,
        "upsert_count": result.get("upsert_count"),
        "top_id": hits[0][0]["id"],
        "score": hits[0][0]["distance"],
    }


if __name__ == "__main__":
    raise SystemExit(0 if run()["status"] == "PASS" else 1)
