#!/usr/bin/env python3
"""Launch the hypothetical financial-services agent as a standalone HTTP service.

Examples
--------
    # Unhardened insurance claims agent on :9000
    uv run python run_agent_service.py --sector insurance --mode vulnerable --port 9000

    # Runtime Guardian MCP guardrail on :9001
    uv run python run_agent_service.py --sector insurance --mode guarded --port 9001

Then point the prober at it. Because the prober blocks loopback by default (SSRF),
allowlist the exact URL for the web UI / campaign process:

    export APRA_PROBER_ALLOWED_LOCAL_URLS="http://127.0.0.1:9000/v1/chat,http://127.0.0.1:9001/v1/chat"
    uv run python -m src.web_ui        # open http://localhost:8080/probe
"""

import argparse
import logging

import uvicorn

from src.agent_service.app import AgentConfig, build_app
from src.agent_service.brains import SECTORS, MODES


def main():
    parser = argparse.ArgumentParser(description="Run the hypothetical APRA agent service.")
    parser.add_argument("--sector", "-s", default="insurance", choices=SECTORS,
                        help="Regulated sector the agent represents (default: insurance)")
    parser.add_argument("--mode", "-m", default="vulnerable", choices=MODES,
                        help="Security posture, fixed for this instance (default: vulnerable)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=9000, help="Bind port (default: 9000)")
    parser.add_argument("--token", default=None, help="Optional Bearer token required on /v1/chat")
    parser.add_argument("--name", default=None, help="Optional display name for the agent")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    config = AgentConfig(
        sector=args.sector,
        mode=args.mode,
        name=args.name or "",
        auth_token=args.token,
    )
    app = build_app(config)

    url = f"http://{args.host}:{args.port}/v1/chat"
    print("=" * 70)
    print(f"  {config.name}")
    print(f"  Sector: {config.sector}   Mode: {config.mode}   Auth: {'on' if args.token else 'off'}")
    print(f"  Chat endpoint : {url}")
    print(f"  Health        : http://{args.host}:{args.port}/health")
    if args.mode == "guarded":
        print("  Guardrail     : APRA MCP stdio client → audit_agent_for_regulatory_breach")
    print("-" * 70)
    print("  To probe it, allowlist the exact URL for the prober process:")
    print(f'    export APRA_PROBER_ALLOWED_LOCAL_URLS="{url}"')
    print("=" * 70)

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
