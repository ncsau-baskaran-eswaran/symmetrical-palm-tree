"""Remote streamable-HTTP entry point for the Guardian Compliance MCP server.

Serves the existing FastMCP instance from src/server.py at /mcp behind bearer
token authentication, a request size limit and a per-token rate limit, plus an
unauthenticated GET /healthz for load balancers.

The MCP streamable HTTP app owns a session manager that must be started by the
ASGI lifespan. We therefore wrap the app returned by ``mcp.streamable_http_app()``
with a pure ASGI middleware (lifespan scopes pass straight through) instead of
mounting it inside a second Starlette app, so the server's own lifespan runs.

Configuration (environment variables):
    GUARDIAN_HTTP_TOKENS                   comma-separated bearer tokens
    GUARDIAN_HTTP_TOKEN_FILE               file with one token per line
    GUARDIAN_HTTP_ALLOW_UNAUTHENTICATED    "1" permits no tokens, loopback bind only
    GUARDIAN_HTTP_HOST / GUARDIAN_HTTP_PORT  bind address (127.0.0.1 / 8765)
    GUARDIAN_HTTP_RATE_PER_MIN             requests per token per minute (120, 0 disables)
    GUARDIAN_HTTP_RATE_BACKEND             "memory" (default, per process) or "redis" (shared)
    GUARDIAN_HTTP_REDIS_URL                Redis URL, required when the backend is "redis"
    GUARDIAN_HTTP_STATELESS                "1" serves stateless streamable HTTP (no session ids),
                                           so replicas need no sticky sessions
    GUARDIAN_HTTP_MAX_BODY_BYTES           request body limit (1048576)
    GUARDIAN_HTTP_ALLOWED_HOSTS            comma-separated public Host header values
"""

import hashlib
import hmac
import ipaddress
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from src.db import corpus_hash
from src.server import mcp

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_RATE_PER_MIN = 120
DEFAULT_MAX_BODY_BYTES = 1024 * 1024
HEALTH_PATH = "/healthz"


class StartupError(RuntimeError):
    """Raised when the server is configured in an unsafe way."""


def is_loopback(host: str) -> bool:
    """True if the bind host is a loopback address or 'localhost'."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def load_tokens(env: Optional[Dict[str, str]] = None) -> List[str]:
    """Collect bearer tokens from GUARDIAN_HTTP_TOKENS and GUARDIAN_HTTP_TOKEN_FILE."""
    env = os.environ if env is None else env
    tokens = [t.strip() for t in env.get("GUARDIAN_HTTP_TOKENS", "").split(",")]
    token_file = env.get("GUARDIAN_HTTP_TOKEN_FILE", "").strip()
    if token_file:
        tokens += [ln.strip() for ln in Path(token_file).read_text().splitlines()]
    return [t for t in tokens if t and not t.startswith("#")]


def validate_startup(host: str, tokens: List[str], env: Optional[Dict[str, str]] = None) -> None:
    """Refuse unsafe configurations: no tokens is only allowed explicitly on loopback."""
    env = os.environ if env is None else env
    if tokens:
        return
    if env.get("GUARDIAN_HTTP_ALLOW_UNAUTHENTICATED") != "1":
        raise StartupError(
            "No bearer tokens configured. Set GUARDIAN_HTTP_TOKENS or GUARDIAN_HTTP_TOKEN_FILE "
            "(or GUARDIAN_HTTP_ALLOW_UNAUTHENTICATED=1 for loopback development)."
        )
    if not is_loopback(host):
        raise StartupError(
            f"Refusing to run unauthenticated on non-loopback host {host!r}. Configure bearer tokens."
        )


class TokenBucket:
    """In-memory token bucket per key. Not shared across processes."""

    def __init__(self, per_minute: int):
        self.capacity = float(per_minute)
        self.refill_per_sec = per_minute / 60.0
        self._state: Dict[str, List[float]] = {}

    def allow(self, key: str, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        tokens, last = self._state.get(key, [self.capacity, now])
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
        if tokens < 1.0:
            self._state[key] = [tokens, now]
            return False
        self._state[key] = [tokens - 1.0, now]
        return True


class RedisRateLimiter:
    """Fixed-window counter shared across replicas through Redis.

    Each key gets one counter per 60 second window (INCR, then EXPIRE on first hit).
    ``client`` is any object with ``incr(name)`` and ``expire(name, seconds)``, which
    lets tests inject a fake. Fails open if Redis is unreachable, so an outage does
    not take the service down (bearer auth still applies).
    """

    WINDOW_SECONDS = 60

    def __init__(self, client: Any, per_minute: int, prefix: str = "guardian:rate"):
        self.client = client
        self.limit = per_minute
        self.prefix = prefix

    def allow(self, key: str, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        window = int(now // self.WINDOW_SECONDS)
        name = f"{self.prefix}:{key}:{window}"
        try:
            count = int(self.client.incr(name))
            if count == 1:
                self.client.expire(name, self.WINDOW_SECONDS * 2)
        except Exception as exc:  # noqa: BLE001 - any backend error must not become a 500
            print(f"guardian-compliance-mcp-http: rate limiter backend error: {exc}", file=sys.stderr)
            return True
        return count <= self.limit


def build_rate_limiter(
    per_minute: int,
    backend: str = "memory",
    redis_url: str = "",
    redis_client: Any = None,
) -> Optional[Any]:
    """Return the limiter for the chosen backend, or None when rate limiting is off."""
    if per_minute <= 0:
        return None
    backend = (backend or "memory").strip().lower()
    if backend == "memory":
        return TokenBucket(per_minute)
    if backend != "redis":
        raise StartupError(f"Unknown GUARDIAN_HTTP_RATE_BACKEND {backend!r}; use 'memory' or 'redis'.")
    if redis_client is None:
        if not redis_url:
            raise StartupError("GUARDIAN_HTTP_RATE_BACKEND=redis requires GUARDIAN_HTTP_REDIS_URL.")
        try:
            import redis  # imported lazily: optional dependency
        except ImportError:
            raise StartupError(
                "GUARDIAN_HTTP_RATE_BACKEND=redis needs the 'redis' package. Install it (pip install redis) "
                "or use the in-memory limiter / rate limiting at the proxy."
            )
        redis_client = redis.Redis.from_url(redis_url)
    return RedisRateLimiter(redis_client, per_minute)


class _BodyTooLarge(Exception):
    pass


class GuardMiddleware:
    """Bearer auth, per-token rate limit and body size limit around the MCP app.

    /healthz and lifespan events bypass all checks. Tokens are compared with
    hmac.compare_digest and are never logged or echoed.
    """

    def __init__(
        self,
        app: ASGIApp,
        tokens: List[str],
        rate_per_min: int = DEFAULT_RATE_PER_MIN,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        limiter: Optional[Any] = None,
    ):
        self.app = app
        self.tokens = [t.encode() for t in tokens]
        self.max_body_bytes = max_body_bytes
        if limiter is not None:
            self.bucket = limiter
        else:
            self.bucket = TokenBucket(rate_per_min) if rate_per_min > 0 else None

    def _match_token(self, presented: bytes) -> bool:
        # Check every configured token (no early exit) to avoid timing leaks on position.
        matched = False
        for token in self.tokens:
            if hmac.compare_digest(presented, token):
                matched = True
        return matched

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == HEALTH_PATH:
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope["headers"]}
        rate_key = "anonymous"
        if self.tokens:
            auth = headers.get(b"authorization", b"")
            scheme, _, presented = auth.partition(b" ")
            presented = presented.strip()
            if scheme.lower() != b"bearer" or not self._match_token(presented):
                response = JSONResponse(
                    {"error": "unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": 'Bearer realm="guardian-compliance-mcp"'},
                )
                await response(scope, receive, send)
                return
            # Key the bucket on a digest so raw tokens are not held as dict keys.
            rate_key = hashlib.sha256(presented).hexdigest()

        if self.bucket is not None and not self.bucket.allow(rate_key):
            response = JSONResponse(
                {"error": "rate limit exceeded"}, status_code=429, headers={"Retry-After": "10"}
            )
            await response(scope, receive, send)
            return

        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_body_bytes:
            await Response("request body too large", status_code=413)(scope, receive, send)
            return

        # Enforce the limit on the actual stream too (chunked bodies carry no Content-Length).
        received = 0
        response_started = False

        async def limited_receive() -> Dict[str, Any]:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message: Dict[str, Any]) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await Response("request body too large", status_code=413)(scope, receive, send)


async def healthz(request: Request) -> JSONResponse:
    tools = await mcp.list_tools()
    return JSONResponse({"status": "ok", "tools": len(tools), "corpus_hash": corpus_hash()})


def create_app(
    tokens: List[str],
    rate_per_min: int = DEFAULT_RATE_PER_MIN,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    allowed_hosts: Optional[List[str]] = None,
    stateless: bool = False,
    limiter: Optional[Any] = None,
) -> ASGIApp:
    """Build the ASGI app. Run it with a server that honours lifespan (uvicorn does).

    The returned app's lifespan starts the MCP session manager; test clients must
    enter it (``with TestClient(app)``) before calling /mcp.
    """
    # FastMCP only enables DNS-rebinding protection for loopback Host headers. Behind
    # a proxy the Host is the public name, so either allow-list it or disable the
    # check (bearer auth is the gate).
    if allowed_hosts:
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=[],
        )
    else:
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
    # Stateless mode drops MCP session ids so any replica can serve any request.
    mcp.settings.stateless_http = stateless
    mcp.settings.json_response = stateless
    # The session manager's run() may only be entered once per instance; rebuild it.
    mcp._session_manager = None
    inner = mcp.streamable_http_app()
    inner.router.routes.append(Route(HEALTH_PATH, healthz, methods=["GET"]))
    return GuardMiddleware(
        inner, tokens, rate_per_min=rate_per_min, max_body_bytes=max_body_bytes, limiter=limiter
    )


def main() -> None:
    """Console entry point: validate config, then serve with uvicorn."""
    import uvicorn

    host = os.environ.get("GUARDIAN_HTTP_HOST", DEFAULT_HOST)
    port = int(os.environ.get("GUARDIAN_HTTP_PORT", DEFAULT_PORT))
    try:
        tokens = load_tokens()
        validate_startup(host, tokens)
    except (StartupError, OSError) as exc:
        print(f"guardian-compliance-mcp-http: {exc}", file=sys.stderr)
        raise SystemExit(2)

    if not tokens:
        print("WARNING: running WITHOUT authentication (loopback only).", file=sys.stderr)
    if not is_loopback(host):
        print(
            f"WARNING: binding to {host} serves plain HTTP; bearer tokens travel in clear text. "
            "Terminate TLS in front of this service (nginx, Caddy, ALB) and do not expose it directly.",
            file=sys.stderr,
        )

    rate_per_min = int(os.environ.get("GUARDIAN_HTTP_RATE_PER_MIN", DEFAULT_RATE_PER_MIN))
    try:
        limiter = build_rate_limiter(
            rate_per_min,
            backend=os.environ.get("GUARDIAN_HTTP_RATE_BACKEND", "memory"),
            redis_url=os.environ.get("GUARDIAN_HTTP_REDIS_URL", "").strip(),
        )
    except StartupError as exc:
        print(f"guardian-compliance-mcp-http: {exc}", file=sys.stderr)
        raise SystemExit(2)

    public_hosts = [h.strip() for h in os.environ.get("GUARDIAN_HTTP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    allowed_hosts = public_hosts + ["127.0.0.1:*", "localhost:*", "127.0.0.1", "localhost"] if public_hosts else None
    app = create_app(
        tokens,
        rate_per_min=rate_per_min,
        max_body_bytes=int(os.environ.get("GUARDIAN_HTTP_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES)),
        allowed_hosts=allowed_hosts,
        stateless=os.environ.get("GUARDIAN_HTTP_STATELESS", "0") == "1",
        limiter=limiter,
    )
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
