"""Tests for the authenticated streamable HTTP entry point."""

import pytest
from starlette.testclient import TestClient

from src.http_server import (
    StartupError,
    TokenBucket,
    create_app,
    load_tokens,
    validate_startup,
)

TOKEN = "s3cret-token-value"
INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
AUTH = {**MCP_HEADERS, "Authorization": f"Bearer {TOKEN}"}


def client(**kwargs):
    # Entering TestClient as a context manager runs the app lifespan, which starts
    # the MCP session manager that /mcp requires.
    return TestClient(create_app([TOKEN], **kwargs))


def test_healthz_needs_no_auth():
    with client() as c:
        r = c.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["tools"] > 0 and len(body["corpus_hash"]) == 64


def test_mcp_without_token_is_401():
    with client() as c:
        r = c.post("/mcp", json=INIT, headers=MCP_HEADERS)
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Bearer")


def test_mcp_wrong_token_is_401():
    with client() as c:
        r = c.post("/mcp", json=INIT, headers={**MCP_HEADERS, "Authorization": "Bearer nope"})
    assert r.status_code == 401
    assert "nope" not in r.text


def test_mcp_valid_token_reaches_app():
    with client() as c:
        r = c.post("/mcp", json=INIT, headers=AUTH)
    assert r.status_code == 200
    assert "serverInfo" in r.text


def test_rate_limit_returns_429():
    with client(rate_per_min=2) as c:
        codes = [c.post("/mcp", json=INIT, headers=AUTH).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and 429 in codes[2:]


def test_oversized_body_is_413():
    with client(max_body_bytes=100) as c:
        r = c.post("/mcp", content=b"x" * 500, headers=AUTH)
    assert r.status_code == 413


def test_startup_refuses_without_tokens():
    with pytest.raises(StartupError):
        validate_startup("0.0.0.0", [], env={})
    with pytest.raises(StartupError):
        validate_startup("127.0.0.1", [], env={})
    # Opt-out only honoured on loopback.
    with pytest.raises(StartupError):
        validate_startup("0.0.0.0", [], env={"GUARDIAN_HTTP_ALLOW_UNAUTHENTICATED": "1"})
    validate_startup("127.0.0.1", [], env={"GUARDIAN_HTTP_ALLOW_UNAUTHENTICATED": "1"})
    validate_startup("0.0.0.0", ["t"], env={})


def test_load_tokens_from_env_and_file(tmp_path):
    f = tmp_path / "tokens"
    f.write_text("file-one\n\n# comment\nfile-two\n")
    env = {"GUARDIAN_HTTP_TOKENS": " a , b ,", "GUARDIAN_HTTP_TOKEN_FILE": str(f)}
    assert load_tokens(env) == ["a", "b", "file-one", "file-two"]


def test_token_bucket_refills():
    b = TokenBucket(60)
    assert all(b.allow("k", now=0.0) for _ in range(60))
    assert not b.allow("k", now=0.0)
    assert b.allow("k", now=1.0)
