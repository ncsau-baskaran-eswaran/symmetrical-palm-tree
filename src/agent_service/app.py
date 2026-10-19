"""Standalone HTTP service for the hypothetical financial-services AI agent.

Wire-compatible with the APRA black-box prober:
  POST /v1/chat  accepts {"message": ...} | {"prompt": ...} | OpenAI {"messages":[...]}
                 returns {"response": ...} (plus agent/sector/mode metadata)
  GET  /health   liveness + posture

Security posture (sector + mode) is fixed at startup via env/config and is NOT
caller-controllable — a real target does not let the client flip its own guardrails.
"""

import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError
from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route

from src.agent_service.brains import get_brain
from src.agent_service.mcp_audit_client import MCPAuditClient

logger = logging.getLogger("apra.agent_service")

MAX_PROMPT_CHARS = 20_000


@dataclass
class AgentConfig:
    sector: str = "insurance"
    mode: str = "vulnerable"
    name: str = ""
    auth_token: Optional[str] = None
    max_prompt_chars: int = MAX_PROMPT_CHARS

    def __post_init__(self):
        if not self.name:
            label = "National Trust Bank" if self.sector == "banking" else "Australian Mutual Insurance"
            self.name = f"{label} AI Assistant"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(
            sector=os.environ.get("AGENT_SECTOR", "insurance").lower().strip(),
            mode=os.environ.get("AGENT_MODE", "vulnerable").lower().strip(),
            name=os.environ.get("AGENT_NAME", "").strip(),
            auth_token=(os.environ.get("AGENT_AUTH_TOKEN") or None),
        )


class ChatRequest(BaseModel):
    """Accepts the three payload shapes the prober can send."""
    message: Optional[str] = None
    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None

    def extract_prompt(self) -> str:
        if self.message:
            return str(self.message)
        if self.prompt:
            return str(self.prompt)
        if self.messages:
            # Last user turn, else last turn's content.
            for turn in reversed(self.messages):
                if isinstance(turn, dict) and turn.get("role") == "user" and turn.get("content"):
                    return str(turn["content"])
            last = self.messages[-1]
            if isinstance(last, dict) and last.get("content"):
                return str(last["content"])
        return ""


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def build_app(config: Optional[AgentConfig] = None) -> Starlette:
    config = config or AgentConfig.from_env()
    brain = get_brain(config.sector, config.mode)

    @asynccontextmanager
    async def lifespan(app):
        audit_client = None
        if brain.audit_role:
            audit_client = MCPAuditClient()
            # Fail startup if the MCP server cannot initialize: guarded mode must
            # never silently fall back to returning an unaudited candidate reply.
            await audit_client.start()
        app.state.mcp_audit_client = audit_client
        try:
            yield
        finally:
            if audit_client is not None:
                await audit_client.close()

    async def index(request):
        # Friendly landing page — browsers GET here; the chat API is POST /v1/chat.
        auth_line = (
            "<li>Auth: <strong>Bearer token required</strong> on /v1/chat</li>"
            if config.auth_token else
            "<li>Auth: none</li>"
        )
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{config.name}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background:#0f172a; color:#e2e8f0; margin:0; padding:48px 20px; line-height:1.6; }}
  .box {{ max-width:640px; margin:0 auto; }}
  h1 {{ font-size:1.4rem; margin:0 0 4px; }}
  .tag {{ display:inline-block; font-size:.72rem; font-weight:700; letter-spacing:.04em;
    text-transform:uppercase; padding:3px 10px; border-radius:999px; background:#1e293b; color:#93c5fd; }}
  ul {{ color:#94a3b8; font-size:.92rem; padding-left:20px; }}
  pre {{ background:#1e293b; border:1px solid #334155; border-radius:8px; padding:14px;
    overflow:auto; font-size:.82rem; color:#e2e8f0; }}
  code {{ color:#93c5fd; }} a {{ color:#60a5fa; }}
</style></head>
<body><div class="box">
  <p class="tag">Hypothetical agent · for APRA red-team testing</p>
  <h1>{config.name}</h1>
  <ul>
    <li>Sector: <strong>{config.sector}</strong> · Posture: <strong>{config.mode}</strong></li>
    {auth_line}
    <li>Health: <a href="/health">/health</a></li>
  </ul>
  <p>This is a chat API. The browser sent a <code>GET</code>; the endpoint takes <code>POST</code>:</p>
  <pre>curl -X POST {request.url.scheme}://{request.url.netloc}/v1/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "Hello"}}'</pre>
  <p style="color:#64748b;font-size:.8rem">Synthetic fixtures only — no real accounts, data, or transactions.</p>
</div></body></html>"""
        return HTMLResponse(html)

    async def health(request):
        return JSONResponse({
            "status": "ok",
            "agent": config.name,
            "sector": config.sector,
            "mode": config.mode,
        })

    async def chat_get(request):
        # Helpful hint when someone opens the chat URL in a browser (GET).
        return JSONResponse(
            {"error": "method not allowed", "hint": "POST JSON to this URL, e.g. {\"message\": \"...\"}"},
            status_code=405,
        )

    async def chat(request):
        request_id = uuid.uuid4().hex[:12]
        start = time.time()

        # Bearer auth (only enforced when a token is configured).
        if config.auth_token:
            header = request.headers.get("authorization", "")
            if header != f"Bearer {config.auth_token}":
                logger.info(json.dumps({"event": "chat", "request_id": request_id, "status": 401}))
                return JSONResponse({"error": "unauthorized"}, status_code=401)

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "request body must be valid JSON"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "request body must be a JSON object"}, status_code=422)

        try:
            req = ChatRequest(**body)
        except ValidationError as e:
            return JSONResponse({"error": "invalid request schema", "detail": e.errors()}, status_code=422)

        prompt = req.extract_prompt()
        if not prompt:
            return JSONResponse(
                {"error": "provide one of: message, prompt, or messages[]"}, status_code=422
            )
        if len(prompt) > config.max_prompt_chars:
            return JSONResponse({"error": "prompt too large"}, status_code=413)

        try:
            if brain.audit_role:
                reply = await brain.reply_with_mcp_audit(
                    prompt,
                    request.app.state.mcp_audit_client.audit,
                )
            else:
                reply = brain.reply(prompt)
        except Exception:
            logger.exception(json.dumps({
                "event": "mcp_preflight_failed",
                "request_id": request_id,
                "sector": config.sector,
                "mode": config.mode,
            }))
            return JSONResponse(
                {"error": "runtime compliance audit unavailable; candidate response withheld"},
                status_code=503,
            )
        latency_ms = round((time.time() - start) * 1000, 1)

        # Structured log — prompt/response hashed, never emitted in the clear (CPS 234 hygiene).
        logger.info(json.dumps({
            "event": "chat",
            "request_id": request_id,
            "sector": config.sector,
            "mode": config.mode,
            "prompt_sha256_12": _sha12(prompt),
            "response_sha256_12": _sha12(reply),
            "response_chars": len(reply),
            "latency_ms": latency_ms,
            "status": 200,
        }))

        return JSONResponse({
            "response": reply,
            "agent": config.name,
            "sector": config.sector,
            "mode": config.mode,
            "request_id": request_id,
        })

    return Starlette(
        routes=[
            Route("/", index),
            Route("/health", health),
            Route("/v1/chat", chat, methods=["POST"]),
            Route("/v1/chat", chat_get, methods=["GET"]),
        ],
        lifespan=lifespan,
    )


# Module-level app for `uvicorn src.agent_service.app:app` (reads config from env).
app = build_app()
