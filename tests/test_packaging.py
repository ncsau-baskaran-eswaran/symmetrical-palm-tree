"""Packaging and database-location tests."""

import tomllib
from pathlib import Path

from src import db

ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def test_build_system_declared():
    cfg = _pyproject()
    assert cfg["build-system"]["build-backend"] == "hatchling.build"
    assert "hatchling" in cfg["build-system"]["requires"]
    assert cfg["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src"]


def test_scripts_declared():
    scripts = _pyproject()["project"]["scripts"]
    assert scripts["guardian-compliance-mcp"] == "src.server:main"
    assert scripts["apra-mcp"] == "src.server:main"
    assert scripts["guardian-compliance-mcp-http"] == "src.http_server:main"


def test_server_main_is_callable():
    from src import server

    assert callable(server.main)


def test_db_path_beside_code_when_writable(monkeypatch):
    monkeypatch.delenv("GUARDIAN_DB_PATH", raising=False)
    monkeypatch.setattr(db.os, "access", lambda *a, **k: True)
    assert db.resolve_db_path() == Path(db.__file__).parent / "guardian.db"


def test_db_path_falls_back_to_user_cache_when_read_only(monkeypatch, tmp_path):
    monkeypatch.delenv("GUARDIAN_DB_PATH", raising=False)
    monkeypatch.setattr(db.os, "access", lambda *a, **k: False)
    monkeypatch.setattr(db.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    path = db.resolve_db_path()
    assert path.name == "guardian.db"
    assert path.parent.is_dir()
    assert path.parent.name == "guardian-compliance"
    assert tmp_path in path.parents


def test_db_path_override(monkeypatch, tmp_path):
    target = tmp_path / "nested" / "custom.db"
    monkeypatch.setenv("GUARDIAN_DB_PATH", str(target))
    assert db.resolve_db_path() == target
    assert target.parent.is_dir()


def test_init_db_seeds_at_overridden_path(monkeypatch, tmp_path):
    target = tmp_path / "seeded.db"
    monkeypatch.setattr(db, "DB_PATH", target)
    db.init_db()
    assert target.exists()
    conn = db.get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM standards").fetchone()[0] > 0
    finally:
        conn.close()
