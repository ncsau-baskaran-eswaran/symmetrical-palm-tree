"""Tests for the authenticated streamable HTTP entry point."""

import pytest
from starlette.testclient import TestClient

from src.http_server import (
    RedisRateLimiter,
    StartupError,
    TokenBucket,
    build_rate_limiter,
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


def test_stateless_requests_need_no_session_id():
    with client(stateless=True) as c:
        r1 = c.post("/mcp", json=INIT, headers=AUTH)
        assert r1.status_code == 200 and "serverInfo" in r1.text
        assert "mcp-session-id" not in r1.headers
        # An independent request with no session id and no initialize handshake.
        r2 = c.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=AUTH)
    assert r2.status_code == 200 and "tools" in r2.text


class FakeRedis:
    """Minimal stand-in for redis.Redis: incr and expire only."""

    def __init__(self):
        self.counts = {}
        self.expiries = {}

    def incr(self, name):
        self.counts[name] = self.counts.get(name, 0) + 1
        return self.counts[name]

    def expire(self, name, seconds):
        self.expiries[name] = seconds


def test_redis_limiter_fixed_window():
    fake = FakeRedis()
    lim = RedisRateLimiter(fake, 2)
    assert lim.allow("k", now=0.0) and lim.allow("k", now=1.0)
    assert not lim.allow("k", now=2.0)
    assert lim.allow("other", now=2.0)
    assert lim.allow("k", now=61.0)  # next window
    assert fake.expiries  # counters expire


def test_redis_limiter_shared_between_replicas_and_fails_open():
    fake = FakeRedis()
    a, b = RedisRateLimiter(fake, 2), RedisRateLimiter(fake, 2)
    assert a.allow("k", now=0.0) and b.allow("k", now=0.0)
    assert not a.allow("k", now=0.0) and not b.allow("k", now=0.0)

    class Broken:
        def incr(self, name):
            raise ConnectionError("down")

    assert RedisRateLimiter(Broken(), 1).allow("k")


def test_redis_limiter_through_app_returns_429():
    with client(limiter=RedisRateLimiter(FakeRedis(), 2)) as c:
        codes = [c.post("/mcp", json=INIT, headers=AUTH).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and 429 in codes[2:]


def test_build_rate_limiter_selection(monkeypatch):
    assert isinstance(build_rate_limiter(10), TokenBucket)
    assert build_rate_limiter(0, backend="redis") is None
    assert isinstance(build_rate_limiter(10, "redis", redis_client=FakeRedis()), RedisRateLimiter)
    with pytest.raises(StartupError):
        build_rate_limiter(10, "bogus")
    with pytest.raises(StartupError, match="REDIS_URL"):
        build_rate_limiter(10, "redis")
    # Selected but the package is missing: refuse to start with a clear message.
    import sys

    monkeypatch.setitem(sys.modules, "redis", None)
    with pytest.raises(StartupError, match="redis"):
        build_rate_limiter(10, "redis", redis_url="redis://localhost:6379/0")
