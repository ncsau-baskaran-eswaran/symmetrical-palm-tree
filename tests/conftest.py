"""Shared test setup: build the registry database once, so any test file can run on its own."""

from src.db import init_db

init_db()
