import hashlib
from pathlib import Path
from knowledge.core.configuration import required
from knowledge.utils.client.storage_clients import StorageClients


def put_verified(path: Path, key: str, content_type: str) -> str:
    client = StorageClients.get_minio_client()
    bucket = required("MINIO_BUCKET_NAME")
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    client.fput_object(bucket, key, str(path), content_type=content_type)
    if client.stat_object(bucket, key).size != path.stat().st_size:
        raise RuntimeError("MinIO size verification failed")
    response = client.get_object(bucket, key)
    try:
        actual = hashlib.sha256()
        for data in response.stream(1024 * 1024):
            actual.update(data)
    finally:
        response.close()
        response.release_conn()
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual.hexdigest() != expected:
        raise RuntimeError("MinIO readback checksum mismatch")
    return key
