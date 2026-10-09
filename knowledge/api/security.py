import hashlib
import hmac
import json
import os
from fastapi import HTTPException, Request
from knowledge.core.configuration import required


def owner_for_token(token: str) -> str:
    configured = {"local": required("APP_API_TOKEN")}
    extra = json.loads(os.getenv("APP_USERS_JSON", "{}"))
    if not isinstance(extra, dict):
        raise ValueError("APP_USERS_JSON must be an owner/token object")
    configured.update(extra)
    for owner, secret in configured.items():
        if isinstance(secret, str) and hmac.compare_digest(
            hashlib.sha256(token.encode()).digest(),
            hashlib.sha256(secret.encode()).digest(),
        ):
            return owner
    raise HTTPException(401, "需要本机访问凭证")


def get_owner(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    token = (
        authorization[7:]
        if authorization.startswith("Bearer ")
        else request.cookies.get("shopkeeper_access", "")
    )
    if not token:
        raise HTTPException(401, "需要本机访问凭证")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "不允许跨站请求")
    return owner_for_token(token)
