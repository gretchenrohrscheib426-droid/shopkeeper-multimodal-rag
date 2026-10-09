import pytest
from fastapi.testclient import TestClient
from knowledge.api.app import create_app
from knowledge.core import task_store
from knowledge.utils import document_store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ALLOWED_HOSTS", "testserver,127.0.0.1,localhost")
    monkeypatch.setenv("APP_API_TOKEN", "local-test-token-1234567890")
    monkeypatch.setenv("APP_USERS_JSON", '{"other":"other-test-token-1234567890"}')
    store = task_store.TaskStore(tmp_path / "tasks.sqlite3")
    monkeypatch.setattr(task_store, "_store", store)
    monkeypatch.setattr(document_store, "active_documents", lambda owner: [])
    monkeypatch.setattr(document_store, "committed_version", lambda *args: None)
    with TestClient(create_app()) as client:
        yield client, store


def login(c):
    response = c.post("/auth/login", json={"token": "local-test-token-1234567890"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]


def test_private_routes_and_unknown_resources(client):
    c, store = client
    assert c.get("/health/live").status_code == 200
    for path in [
        "/documents",
        "/history/x",
        "/status/x",
        "/stream/x",
        "/resources/x/y/original",
    ]:
        assert c.get(path).status_code == 401
    login(c)
    assert c.get("/documents").json() == {"items": []}
    assert c.get("/status/missing").status_code == 404
    assert c.get("/resources/x/y/original").status_code == 404
    store.create("private", "other", "query")
    assert c.get("/status/private").status_code == 404
    assert c.post("/tasks/private/cancel").status_code == 404
    assert c.get("/stream/private").status_code == 404


def test_cross_site_and_upload_validation(client):
    c, _ = client
    login(c)
    assert (
        c.post(
            "/tasks/x/cancel", headers={"origin": "https://untrusted.invalid"}
        ).status_code
        == 403
    )
    for name, content in [
        ("a.exe", b"payload"),
        ("../bad.md", b"bad"),
        ("empty.md", b""),
    ]:
        assert c.post("/upload", files={"file": (name, content)}).status_code == 422
    for query in ["", "   ", "x" * 4001]:
        assert c.post("/query", json={"query": query}).status_code == 422
    assert (
        c.post(
            "/query", json={"query": "hello", "selected_document_ids": ["not-owned"]}
        ).status_code
        == 404
    )


def test_reconnect_and_terminal_metadata(client):
    c, store = client
    login(c)
    store.create("replay", "local", "query")
    a = store.emit("replay", "progress", {"node": "work"})
    store.status("replay", "failed", {"error": "expected failure"})
    result = c.get("/stream/replay", headers={"Last-Event-ID": str(a)})
    assert result.status_code == 200
    assert result.text.count("event: final") == 1
    assert "event: progress" not in result.text
    assert '"task_id": "replay"' in result.text and '"timestamp":' in result.text
    assert (
        c.get("/stream/replay", headers={"Last-Event-ID": "invalid"}).status_code == 422
    )
    assert c.get("/status/replay").json()["status"] == "failed"


def test_pages_are_same_origin_and_safe_by_default(client):
    c, _ = client
    for name in ["chat.html", "import.html"]:
        response = c.get("/front/" + name)
        assert response.status_code == 200
        assert "<script>" not in response.text
        assert "script-src 'self'" in response.headers["content-security-policy"]
