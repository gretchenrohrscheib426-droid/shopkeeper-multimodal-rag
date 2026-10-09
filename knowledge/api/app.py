"""One local origin, private resources and replayable task events."""

import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, Depends, HTTPException, Request, Query, Response
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from knowledge.api.security import get_owner, owner_for_token
from knowledge.core.paths import get_front_page_dir
from knowledge.core.configuration import required
from knowledge.core.task_store import get_store
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils import document_store
from knowledge.utils.sse_util import sse_generator


class Login(BaseModel):
    token: str = Field(min_length=16, max_length=256)


def owned_task(task_id, owner):
    try:
        task = get_store().get(task_id)
    except KeyError as exc:
        raise HTTPException(404, "任务不存在") from exc
    if task["owner"] != owner:
        raise HTTPException(404, "任务不存在")
    return task


def manifest(owner, document_id, version):
    row = document_store.committed_version(owner, document_id, version)
    if not row:
        raise HTTPException(404, "资料不存在")
    return row


def public_document(row):
    return {
        k: row[k]
        for k in [
            "document_id",
            "version",
            "file_title",
            "item_name",
            "entity_type",
            "chunk_count",
            "updated_at",
        ]
    } | {
        "images": [
            {k: im[k] for k in ["image_id", "name", "summary", "resource_url"]}
            for im in row["images"]
        ],
        "original_url": f"/resources/{row['document_id']}/{row['version']}/original",
    }


def readiness():
    checks = {}
    for name, operation in [
        ("mongo", lambda: StorageClients.get_mongo_db().command("ping")),
        (
            "minio",
            lambda: StorageClients.get_minio_client().bucket_exists(
                required("MINIO_BUCKET_NAME")
            ),
        ),
        ("milvus", lambda: StorageClients.get_milvus_client().get_server_version()),
    ]:
        try:
            operation()
            checks[name] = {"status": "ready"}
        except Exception as exc:
            checks[name] = {"status": "unavailable", "error_type": type(exc).__name__}
    for name, variable in [
        ("embedding", "BGE_M3_PATH"),
        ("reranker", "BGE_RERANKER_LARGE"),
        ("parser", "MINERU_EXECUTABLE"),
    ]:
        checks[name] = {
            "status": "configured"
            if Path(os.getenv(variable, "/__missing__")).exists()
            else "unavailable"
        }
    try:
        from knowledge.utils.client.ai_clients import AIClients

        AIClients.get_vlm_client().models.list(timeout=8)
        checks["model_api"] = {
            "status": "authenticated",
            "inference": "verified separately by end-to-end tests",
        }
    except Exception as exc:
        checks["model_api"] = {
            "status": "unavailable",
            "error_type": type(exc).__name__,
        }
    checks["web_search"] = {
        "status": "configured_unverified"
        if os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true"
        else "disabled"
    }
    ready = not any(x["status"] == "unavailable" for x in checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "components": checks,
    }, 200 if ready else 503


def create_app():
    @asynccontextmanager
    async def lifespan(app):
        get_store().recover()
        yield
        StorageClients.close()

    app = FastAPI(
        title="掌柜智库：多模态文档 RAG 与可追溯问答",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv(
            "APP_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver"
        ).split(","),
    )

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'"
        )
        return response

    @app.get("/")
    def home():
        return RedirectResponse("/front/chat.html")

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready(owner: str = Depends(get_owner)):
        result, code = readiness()
        return JSONResponse(result, status_code=code)

    @app.post("/auth/login")
    def login(body: Login, request: Request, response: Response):
        if request.headers.get("origin") and request.headers["origin"].rstrip(
            "/"
        ) != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "不允许跨站请求")
        owner = owner_for_token(body.token)
        response.set_cookie(
            "shopkeeper_access",
            body.token,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            max_age=8 * 3600,
        )
        return {"owner": owner}

    @app.get("/auth/me")
    def me(owner: str = Depends(get_owner)):
        return {"owner": owner}

    @app.post("/auth/logout")
    def logout(response: Response, owner: str = Depends(get_owner)):
        response.delete_cookie("shopkeeper_access")
        return {"status": "signed_out"}

    @app.get("/status/{task_id}")
    def status(task_id: str, owner: str = Depends(get_owner)):
        row = owned_task(task_id, owner)
        row.pop("owner", None)
        row.pop("_runner_pid", None)
        return row

    @app.post("/tasks/{task_id}/cancel", status_code=202)
    def cancel(task_id: str, owner: str = Depends(get_owner)):
        owned_task(task_id, owner)
        get_store().cancel(task_id)
        return {"cancel_requested": True}

    @app.get("/stream/{task_id}")
    async def stream(
        task_id: str,
        request: Request,
        after: int = Query(0, ge=0),
        owner: str = Depends(get_owner),
    ):
        owned_task(task_id, owner)
        try:
            cursor = max(after, int(request.headers.get("last-event-id", "0")))
        except ValueError as exc:
            raise HTTPException(422, "无效事件编号") from exc
        return StreamingResponse(
            sse_generator(task_id, request, cursor),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    @app.get("/documents")
    def docs(owner: str = Depends(get_owner)):
        return {
            "items": [
                public_document(x) for x in document_store.active_documents(owner)
            ]
        }

    @app.get("/sources/{document_id}/{version}/{chunk_id}")
    def source(
        document_id: str, version: str, chunk_id: str, owner: str = Depends(get_owner)
    ):
        doc = manifest(owner, document_id, version)
        if chunk_id not in doc["chunk_ids"]:
            raise HTTPException(404, "片段不存在")
        rows = StorageClients.get_milvus_client().get(
            required("CHUNKS_COLLECTION"),
            [chunk_id],
            output_fields=[
                "content",
                "title",
                "char_start",
                "char_end",
                "image_ids",
                "owner",
                "version",
            ],
        )
        if not rows or rows[0]["owner"] != owner or rows[0]["version"] != version:
            raise HTTPException(404, "片段不存在")
        row = rows[0]
        row.pop("owner", None)
        return {"chunk": row, "document": public_document(doc)}

    @app.get("/resources/{document_id}/{version}/{kind}")
    @app.get("/resources/{document_id}/{version}/{kind}/{image_id}")
    def resource(
        document_id: str,
        version: str,
        kind: str,
        image_id: str = "",
        owner: str = Depends(get_owner),
    ):
        doc = manifest(owner, document_id, version)
        if kind == "images":
            matches = [x for x in doc["images"] if x["image_id"] == image_id]
            if not matches:
                raise HTTPException(404, "图片不存在")
            key = matches[0]["object_key"]
            mime = matches[0]["mime_type"]
            filename = matches[0]["name"]
        elif kind in {"original", "processed"} and not image_id:
            key = (
                doc["original_object_key"]
                if kind == "original"
                else doc["processed_object_key"]
            )
            mime = mimetypes.guess_type(key)[0] or "application/octet-stream"
            filename = doc["file_title"] + Path(key).suffix
        else:
            raise HTTPException(404, "资源不存在")
        response = StorageClients.get_minio_client().get_object(
            required("MINIO_BUCKET_NAME"), key
        )

        def content():
            try:
                yield from response.stream(64 * 1024)
            finally:
                response.close()
                response.release_conn()

        disposition = (
            "inline"
            if mime in {"application/pdf", "image/png", "image/jpeg", "image/webp"}
            else "attachment"
        )
        return StreamingResponse(
            content(),
            media_type=mime,
            headers={
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}"
            },
        )

    from knowledge.api.import_router import register_router as register_import
    from knowledge.api.query_router import register_router as register_query

    register_import(app)
    register_query(app)
    app.mount("/front", StaticFiles(directory=get_front_page_dir()), name="front")
    return app


app = create_app()
