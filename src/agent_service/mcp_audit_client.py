"""Persistent stdio MCP client used by the runtime agent guardrail (guarded mode)."""

import json
import os
import shlex
import sys
import asyncio
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPAuditClient:
    """Own a persistent MCP session to the APRA server and call its audit tool."""

    def __init__(self) -> None:
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._timeout = float(os.environ.get("APRA_MCP_AUDIT_TIMEOUT_SECONDS", "5"))
        if self._timeout <= 0:
            raise ValueError("APRA_MCP_AUDIT_TIMEOUT_SECONDS must be greater than zero")

    async def start(self) -> None:
        if self._session is not None:
            return

        command = os.environ.get("APRA_MCP_SERVER_COMMAND", sys.executable)
        args = shlex.split(os.environ.get("APRA_MCP_SERVER_ARGS", "-m src.server"))
        project_root = Path(__file__).resolve().parents[2]
        params = StdioServerParameters(command=command, args=args, cwd=project_root)

        stack = AsyncExitStack()
        try:
            async with asyncio.timeout(self._timeout):
                read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                await session.initialize()
        except Exception:
            await stack.aclose()
            raise

        self._stack = stack
        self._session = session

    async def close(self) -> None:
        stack, self._stack = self._stack, None
        self._session = None
        if stack is not None:
            await stack.aclose()

    async def audit(
        self,
        *,
        agent_role: str,
        user_prompt: str,
        agent_response: str,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if self._session is None:
            raise RuntimeError("MCP audit session is not connected")

        context = context or {}
        result = await self._session.call_tool(
            "audit_agent_for_regulatory_breach",
            arguments={
                "agent_role": agent_role,
                "user_prompt": user_prompt,
                "agent_response": agent_response,
                "context_claim_amount": float(context.get("claim_amount", 0.0) or 0.0),
            },
            read_timeout_seconds=timedelta(seconds=self._timeout),
        )
        if result.isError:
            raise RuntimeError("MCP audit tool returned an error")

        def _unwrap(obj: Any) -> Any:
            # FastMCP wraps a dict return as {"result": {...}}; unwrap to the audit dict.
            if isinstance(obj, dict) and "audit_verdict" not in obj and isinstance(obj.get("result"), dict):
                return obj["result"]
            return obj

        payload = _unwrap(result.structuredContent)
        if not isinstance(payload, dict) or "audit_verdict" not in payload:
            for item in result.content or []:
                text = getattr(item, "text", None)
                if not text:
                    continue
                try:
                    decoded = _unwrap(json.loads(text))
                except (TypeError, json.JSONDecodeError):
                    continue
                if isinstance(decoded, dict) and "audit_verdict" in decoded:
                    payload = decoded
                    break
        if not isinstance(payload, dict) or "audit_verdict" not in payload:
            raise RuntimeError("MCP audit tool returned an invalid result")
        return payload
