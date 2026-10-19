"""Regulatory instrument registry: SQLite storage and full-text search over the AU insurance corpus.

Every `*.json` file under `src/data/instruments/` is one instrument (APRA prudential standards, Acts, ASIC
regulatory guides, industry codes, privacy and cyber law). The database is rebuilt whenever the corpus content
hash changes, so editing a JSON file is enough to update what the MCP serves.
"""

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DB_PATH = Path(__file__).parent / "guardian.db"
DATA_DIR = Path(__file__).parent / "data"
INSTRUMENTS_DIR = DATA_DIR / "instruments"

SCHEMA_VERSION = "2"

_SCHEMA = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE standards (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    short_name TEXT NOT NULL,
    regulator TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    legislative_instrument TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    amended_date TEXT NOT NULL,
    status TEXT NOT NULL,
    sectors TEXT NOT NULL,
    entity_types TEXT NOT NULL,
    enforceability TEXT NOT NULL,
    source_url TEXT NOT NULL,
    licence TEXT NOT NULL,
    text_kind TEXT NOT NULL,
    verified_on TEXT NOT NULL,
    verification_notes TEXT NOT NULL,
    coverage_default TEXT NOT NULL,
    superseded_standards TEXT NOT NULL,
    companion_guidance TEXT NOT NULL,
    summary TEXT NOT NULL,
    extra TEXT NOT NULL,
    source_file TEXT NOT NULL
);

CREATE TABLE clauses (
    id TEXT PRIMARY KEY,
    standard_code TEXT NOT NULL,
    clause_number TEXT NOT NULL,
    section_name TEXT NOT NULL,
    heading TEXT NOT NULL,
    text TEXT NOT NULL,
    subclauses TEXT NOT NULL,
    is_mandatory INTEGER NOT NULL,
    notification_trigger TEXT,
    key_topics TEXT NOT NULL,
    notes TEXT,
    obligation_type TEXT,
    agent_relevance TEXT,
    sectors TEXT NOT NULL,
    anchor TEXT,
    FOREIGN KEY (standard_code) REFERENCES standards(code)
);

CREATE INDEX idx_clauses_standard ON clauses(standard_code);
CREATE INDEX idx_clauses_anchor ON clauses(standard_code, anchor);

CREATE VIRTUAL TABLE clauses_fts USING fts5(
    id UNINDEXED,
    standard_code,
    clause_number,
    section_name,
    heading,
    text,
    subclauses,
    key_topics,
    notes,
    tokenize='porter unicode61'
);

CREATE TABLE definitions (
    term TEXT PRIMARY KEY,
    standard TEXT NOT NULL,
    clause TEXT NOT NULL,
    definition TEXT NOT NULL,
    mandatory_examples TEXT NOT NULL
);

CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    regulator TEXT NOT NULL,
    standard TEXT NOT NULL,
    clause TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timeframe_hours INTEGER,
    timeframe_days INTEGER,
    day_basis TEXT,
    urgency TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    apra_reporting_content TEXT NOT NULL,
    interaction_notes TEXT NOT NULL
);
"""

_INSTRUMENT_JSON_FIELDS = ("sectors", "entity_types", "superseded_standards", "companion_guidance", "extra")
_CLAUSE_JSON_FIELDS = ("subclauses", "key_topics", "sectors")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _corpus_files() -> List[Path]:
    files = sorted(INSTRUMENTS_DIR.rglob("*.json"))
    files += [DATA_DIR / "definitions.json", DATA_DIR / "notifications.json"]
    return [f for f in files if f.exists()]


def corpus_hash() -> str:
    """Content hash of every corpus file plus the schema version; any edit triggers a reseed."""
    h = hashlib.sha256(SCHEMA_VERSION.encode())
    for f in _corpus_files():
        h.update(str(f.relative_to(DATA_DIR)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def _stored_hash() -> Optional[str]:
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT value FROM meta WHERE key = 'corpus_hash'").fetchone()
        conn.close()
        return row[0] if row else None
    except sqlite3.DatabaseError:
        return None


def init_db(force: bool = False) -> None:
    """Build the registry database if it is missing or the corpus has changed.

    The new database is written to a temporary file and swapped in atomically, so concurrent readers (the MCP
    server, web UI and agent service) never observe a half-seeded registry.
    """
    current = corpus_hash()
    if not force and _stored_hash() == current:
        return

    fd, tmp_name = tempfile.mkstemp(prefix=".guardian-", suffix=".db", dir=DB_PATH.parent)
    os.close(fd)
    conn = sqlite3.connect(tmp_name)
    try:
        conn.executescript(_SCHEMA)
        _seed_data(conn.cursor())
        conn.execute("INSERT INTO meta VALUES ('corpus_hash', ?)", (current,))
        conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
        conn.commit()
    except Exception:
        conn.close()
        os.unlink(tmp_name)
        raise
    conn.close()
    os.replace(tmp_name, DB_PATH)


def load_instrument_files() -> List[Dict[str, Any]]:
    """Parse every instrument file. Raises on duplicate codes so corpus mistakes fail loudly."""
    instruments: List[Dict[str, Any]] = []
    seen: Dict[str, Path] = {}
    for path in sorted(INSTRUMENTS_DIR.rglob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        code = data["code"]
        if code in seen:
            raise ValueError(f"Duplicate instrument code '{code}' in {path} and {seen[code]}")
        seen[code] = path
        data["_source_file"] = str(path.relative_to(DATA_DIR))
        instruments.append(data)
    return instruments


def _seed_data(cursor: sqlite3.Cursor) -> None:
    known = {
        "code", "title", "short_name", "regulator", "instrument_type", "legislative_instrument",
        "effective_date", "amended_date", "status", "sectors", "entity_types", "enforceability", "source_url",
        "licence", "text_kind", "verified_on", "verification_notes", "coverage_default",
        "superseded_standards", "companion_guidance", "summary", "clauses", "_source_file",
    }
    for inst in load_instrument_files():
        code = inst["code"]
        extra = {k: v for k, v in inst.items() if k not in known}
        cursor.execute(
            "INSERT INTO standards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                code,
                inst["title"],
                inst.get("short_name", inst["title"]),
                inst.get("regulator", ""),
                inst.get("instrument_type", ""),
                inst.get("legislative_instrument", ""),
                inst.get("effective_date", ""),
                inst.get("amended_date", ""),
                inst.get("status", ""),
                json.dumps(inst.get("sectors", [])),
                json.dumps(inst.get("entity_types", [])),
                inst.get("enforceability", ""),
                inst.get("source_url", ""),
                inst.get("licence", ""),
                inst.get("text_kind", ""),
                inst.get("verified_on", ""),
                inst.get("verification_notes", ""),
                inst.get("coverage_default", "reference_only"),
                json.dumps(inst.get("superseded_standards", [])),
                json.dumps(inst.get("companion_guidance", [])),
                inst.get("summary", ""),
                json.dumps(extra),
                inst["_source_file"],
            ),
        )
        for cl in inst.get("clauses", []):
            subclauses = cl.get("subclauses", [])
            key_topics = cl.get("key_topics", [])
            cursor.execute(
                "INSERT INTO clauses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cl["id"],
                    code,
                    str(cl["clause_number"]),
                    cl.get("section_name", ""),
                    cl.get("heading", ""),
                    cl.get("text", ""),
                    json.dumps(subclauses),
                    1 if cl.get("is_mandatory", True) else 0,
                    cl.get("notification_trigger"),
                    json.dumps(key_topics),
                    cl.get("notes"),
                    cl.get("obligation_type"),
                    cl.get("agent_relevance"),
                    json.dumps(cl.get("sectors", inst.get("sectors", []))),
                    cl.get("anchor"),
                ),
            )
            cursor.execute(
                """
                INSERT INTO clauses_fts (id, standard_code, clause_number, section_name, heading, text, subclauses, key_topics, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cl["id"],
                    code,
                    str(cl["clause_number"]),
                    cl.get("section_name", ""),
                    cl.get("heading", ""),
                    cl.get("text", ""),
                    " ".join(subclauses),
                    " ".join(key_topics),
                    cl.get("notes") or "",
                ),
            )

    def_path = DATA_DIR / "definitions.json"
    if def_path.exists():
        with open(def_path, "r", encoding="utf-8") as f:
            for d in json.load(f).get("definitions", []):
                cursor.execute(
                    "INSERT OR REPLACE INTO definitions VALUES (?, ?, ?, ?, ?)",
                    (d["term"], d["standard"], d["clause"], d["definition"], json.dumps(d.get("mandatory_examples", {}))),
                )

    notif_path = DATA_DIR / "notifications.json"
    if notif_path.exists():
        with open(notif_path, "r", encoding="utf-8") as f:
            for r in json.load(f).get("rules", []):
                cursor.execute(
                    """
                    INSERT INTO notifications (regulator, standard, clause, event_type, timeframe, timeframe_hours,
                        timeframe_days, day_basis, urgency, trigger_condition, apra_reporting_content, interaction_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.get("regulator", "APRA"),
                        r["standard"],
                        r["clause"],
                        r["event_type"],
                        r["timeframe"],
                        r.get("timeframe_hours"),
                        r.get("timeframe_days"),
                        r.get("day_basis"),
                        r["urgency"],
                        r["trigger_condition"],
                        json.dumps(r.get("apra_reporting_content", r.get("reporting_content", []))),
                        r.get("interaction_notes", ""),
                    ),
                )


def _decode(row: sqlite3.Row, fields: Iterable[str]) -> Dict[str, Any]:
    d = dict(row)
    for k in fields:
        if k in d and isinstance(d[k], str):
            d[k] = json.loads(d[k])
    if "is_mandatory" in d:
        d["is_mandatory"] = bool(d["is_mandatory"])
    return d


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def resolve_instrument_code(code: str) -> Optional[str]:
    """Map a user-typed code ('cps230', 'Insurance Contracts Act', 'RG271') to the registry code."""
    conn = get_connection()
    rows = conn.execute("SELECT code, title, short_name FROM standards").fetchall()
    conn.close()
    target = _norm(code)
    if not target:
        return None
    for r in rows:
        if _norm(r["code"]) == target:
            return r["code"]
    for r in rows:
        if target in (_norm(r["title"]), _norm(r["short_name"])):
            return r["code"]
    candidates = [r["code"] for r in rows if target in _norm(r["code"]) or target in _norm(r["title"])]
    return min(candidates, key=len) if candidates else None


def get_standard_by_code(code: str) -> Optional[Dict[str, Any]]:
    resolved = resolve_instrument_code(code)
    if not resolved:
        return None
    conn = get_connection()
    row = conn.execute("SELECT * FROM standards WHERE code = ?", (resolved,)).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM clauses WHERE standard_code = ?", (resolved,)).fetchone()[0]
    conn.close()
    d = _decode(row, _INSTRUMENT_JSON_FIELDS)
    d["clause_count"] = count
    return d


def list_instrument_rows() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT s.*, (SELECT COUNT(*) FROM clauses c WHERE c.standard_code = s.code) AS clause_count
        FROM standards s ORDER BY s.regulator, s.code
        """
    ).fetchall()
    conn.close()
    return [_decode(r, _INSTRUMENT_JSON_FIELDS) for r in rows]


def get_clauses_for(standard_code: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM clauses WHERE standard_code = ? ORDER BY rowid", (standard_code,)).fetchall()
    conn.close()
    return [_decode(r, _CLAUSE_JSON_FIELDS) for r in rows]


def _clause_keys(clause_number: str) -> List[str]:
    """Normalised spellings of a citation: 's 13', 'section 13', '13' and 'RG 271.38' vs '38' all collapse."""
    n = _norm(clause_number)
    keys = {n}
    for prefix in ("section", "sec", "paragraph", "para", "clause", "s", "p"):
        if n.startswith(prefix) and len(n) > len(prefix) and n[len(prefix)].isdigit():
            keys.add(n[len(prefix):])
    return list(keys)


def get_clause_by_number(standard_code: str, clause_number: str) -> Optional[Dict[str, Any]]:
    """Find a clause by citation or by anchor within one instrument."""
    resolved = resolve_instrument_code(standard_code)
    if not resolved:
        return None
    wanted = _clause_keys(str(clause_number))
    for clause in get_clauses_for(resolved):
        if clause.get("anchor") and clause["anchor"] == str(clause_number).strip():
            return clause
        have = _clause_keys(clause["clause_number"])
        code_prefix = _norm(resolved)
        have += [k[len(code_prefix):] for k in have if k.startswith(code_prefix) and len(k) > len(code_prefix)]
        if set(wanted) & set(have):
            return clause
    return None


def search_clauses(
    query: str,
    standard_code: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 10,
    regulator: Optional[str] = None,
    sector: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Hybrid FTS (BM25) and keyword search over clauses, optionally filtered by instrument, regulator or sector."""
    code = resolve_instrument_code(standard_code) if standard_code else None
    if standard_code and not code:
        return []

    filters, filter_params = [], []
    if code:
        filters.append("c.standard_code = ?")
        filter_params.append(code)
    if regulator:
        filters.append("s.regulator LIKE ?")
        filter_params.append(f"%{regulator}%")
    if sector:
        filters.append("c.sectors LIKE ?")
        filter_params.append(f'%"{sector}"%')
    where_extra = "".join(f" AND {f}" for f in filters)

    conn = get_connection()
    cursor = conn.cursor()
    clean_q = "".join(c if c.isalnum() or c in (" ", "-", "_") else " " for c in query).strip()
    words = [w for w in clean_q.split() if len(w) > 1]

    results: List[Dict[str, Any]] = []
    if words:
        fts_query = " OR ".join(f'"{w}"*' for w in words)
        sql = f"""
        SELECT c.*, bm25(clauses_fts) AS rank
        FROM clauses_fts
        JOIN clauses c ON clauses_fts.id = c.id
        JOIN standards s ON s.code = c.standard_code
        WHERE clauses_fts MATCH ?{where_extra}
        ORDER BY rank LIMIT ?
        """
        try:
            cursor.execute(sql, [fts_query, *filter_params, limit])
            results = [_decode(r, _CLAUSE_JSON_FIELDS) for r in cursor.fetchall()]
        except sqlite3.OperationalError:
            results = []

    if not results:
        like = f"%{query.strip()}%"
        sql = f"""
        SELECT c.* FROM clauses c JOIN standards s ON s.code = c.standard_code
        WHERE (c.text LIKE ? OR c.heading LIKE ? OR c.section_name LIKE ? OR c.notes LIKE ?){where_extra}
        LIMIT ?
        """
        cursor.execute(sql, [like, like, like, like, *filter_params, limit])
        results = [_decode(r, _CLAUSE_JSON_FIELDS) for r in cursor.fetchall()]

    conn.close()
    return results


def get_all_notifications() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM notifications
        ORDER BY COALESCE(timeframe_hours, timeframe_days * 24) ASC NULLS LAST, regulator
        """
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["apra_reporting_content"] = json.loads(d["apra_reporting_content"])
        out.append(d)
    return out


def get_all_definitions() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM definitions").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["mandatory_examples"] = json.loads(d["mandatory_examples"])
        out.append(d)
    return out
