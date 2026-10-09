"""Bounded SDK connections. No collection/volume deletion or public bucket policy."""

import os
import threading
import urllib3
from minio import Minio
from pymilvus import MilvusClient
from pymongo import MongoClient
from pymongo.database import Database
from knowledge.core.configuration import load_environment, required
from knowledge.utils.client.base import BaseClientManager

load_environment()


class StorageClients(BaseClientManager):
    _minio_client = None
    _minio_lock = threading.Lock()
    _milvus_client = None
    _milvus_lock = threading.Lock()
    _mongo_client = None
    _mongo_db = None
    _mongo_lock = threading.Lock()

    @classmethod
    def get_minio_client(cls) -> Minio:
        return cls._get_or_create(
            "_minio_client", cls._minio_lock, cls._create_minio_client
        )

    @classmethod
    def _create_minio_client(cls) -> Minio:
        timeout = float(os.getenv("STORAGE_TIMEOUT_SECONDS", "8"))
        return Minio(
            required("MINIO_ENDPOINT"),
            access_key=required("MINIO_ACCESS_KEY"),
            secret_key=required("MINIO_SECRET_KEY"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            http_client=urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=timeout, read=timeout), retries=False
            ),
        )

    @classmethod
    def get_milvus_client(cls) -> MilvusClient:
        return cls._get_or_create(
            "_milvus_client", cls._milvus_lock, cls._create_milvus_client
        )

    @classmethod
    def _create_milvus_client(cls) -> MilvusClient:
        return MilvusClient(
            uri=required("MILVUS_URL"),
            token=os.getenv("MILVUS_TOKEN", ""),
            timeout=float(os.getenv("STORAGE_TIMEOUT_SECONDS", "8")),
        )

    @classmethod
    def get_mongo_db(cls) -> Database:
        return cls._get_or_create("_mongo_db", cls._mongo_lock, cls._create_mongo_db)

    @classmethod
    def _create_mongo_db(cls) -> Database:
        timeout = int(float(os.getenv("STORAGE_TIMEOUT_SECONDS", "8")) * 1000)
        client = MongoClient(
            required("MONGO_URL"),
            serverSelectionTimeoutMS=timeout,
            connectTimeoutMS=timeout,
            socketTimeoutMS=timeout,
        )
        client.admin.command("ping")
        cls._mongo_client = client
        return client[required("MONGO_DB_NAME")]

    @classmethod
    def close(cls):
        if cls._milvus_client is not None:
            cls._milvus_client.close()
        if cls._mongo_client is not None:
            cls._mongo_client.close()
        cls._milvus_client = cls._mongo_client = cls._mongo_db = cls._minio_client = (
            None
        )
