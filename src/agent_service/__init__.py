"""Hypothetical production-grade financial-services AI agent, runnable as a standalone HTTP service.

Lets the APRA black-box prober target a real HTTP agent (over the wire) instead of a
mock:// URI. Sector and security posture are fixed at startup — the caller cannot flip
the target's guardrails mid-run (a real target wouldn't let them).
"""
