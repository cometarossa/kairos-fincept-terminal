"""Local synthetic-data memory prototype for Fincept × KAIROS.

NOT production authentication, a broker/order ledger, or an LLM memory service.
No network calls, no model execution, no background processes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import sqlite3
import uuid
from typing import Callable

_SCOPE = re.compile(r"[a-z][a-z0-9_-]{1,31}:[a-z][a-z0-9_-]{1,31}\Z")
_SOURCE = re.compile(r"(git|ledger|report|fixture):[^\s]{1,240}\Z")
_ZERO = "0" * 64
_MAX_CONTENT = 8_000

_SQL = """
CREATE TABLE IF NOT EXISTS memory_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    dedup_key TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,
    content TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    expires_at TEXT,
    supersedes TEXT UNIQUE,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_memory_scope_time
    ON memory_events(scope, recorded_at, observed_at);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
    USING fts5(content, content='memory_events', content_rowid='seq', tokenize='unicode61');
"""


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("UTC timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash(fields: dict) -> str:
    payload = json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    scope: str
    content: str
    source_ref: str
    observed_at: str
    recorded_at: str
    expires_at: str | None
    supersedes: str | None
    event_hash: str


class LocalEvidenceMemory:
    """Append-only application-level evidence log + lexical full-text recall.

    Scope is a filter, NOT authentication. Never expose this class directly over
    a network. Hindsight/Mem0 are optional future semantic-index adapters.
    File owner can rewrite SQLite: hash chain detects accidental/local tampering,
    not malicious rewrite of the complete database.
    """

    def __init__(self, filename: str | Path, *, clock: Callable[[], datetime] | None = None):
        self.filename = Path(filename).expanduser()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.filename.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Require a private parent; do not silently make an existing shared directory safe.
        if self.filename.parent.stat().st_mode & 0o077:
            raise PermissionError("Memory directory must not be accessible by group/others")
        if self.filename.is_symlink():
            raise PermissionError("Memory database path must not be a symlink")
        if self.filename.exists() and (
            not self.filename.is_file() or self.filename.stat().st_mode & 0o077
        ):
            raise PermissionError("Existing memory database must be a private regular file")
        created = not self.filename.exists()
        with self._connect() as db:
            db.executescript(_SQL)
        if created:
            os.chmod(self.filename, 0o600)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.filename), timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        return db

    @staticmethod
    def _validate(scope: str, content: str, source_ref: str) -> None:
        if not _SCOPE.fullmatch(scope):
            raise ValueError("Invalid scope")
        if not _SOURCE.fullmatch(source_ref):
            raise ValueError("Source must be a bounded git:/ledger:/report:/fixture: reference")
        if not content.strip() or len(content) > _MAX_CONTENT:
            raise ValueError("Memory content must contain 1..8000 characters")

    def _append(
        self, scope: str, content: str, source_ref: str, observed_at: datetime,
        *, expires_at: datetime | None = None, supersedes: str | None = None
    ) -> MemoryRecord:
        self._validate(scope, content, source_ref)
        observed = _utc(observed_at)
        recorded = _utc(self._clock())
        expiry = _utc(expires_at) if expires_at is not None else None
        if observed > recorded:
            raise ValueError("Observation timestamp cannot be later than its recording time")
        if expiry is not None and expiry <= recorded:
            raise ValueError("Memory already expired")

        dedup_key = _hash(dict(scope=scope, content=content, source_ref=source_ref,
                               observed_at=observed, expires_at=expiry, supersedes=supersedes))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            duplicate = db.execute(
                "SELECT * FROM memory_events WHERE dedup_key=?", (dedup_key,)
            ).fetchone()
            if duplicate is not None:
                return self._record(duplicate)
            if supersedes:
                prior = db.execute(
                    "SELECT scope FROM memory_events WHERE id=?", (supersedes,)
                ).fetchone()
                if prior is None or prior["scope"] != scope:
                    raise ValueError("Correction must target an existing memory in the same scope")
                if db.execute(
                    "SELECT 1 FROM memory_events WHERE supersedes=?", (supersedes,)
                ).fetchone():
                    raise ValueError("Memory has already been superseded")
            last = db.execute(
                "SELECT event_hash FROM memory_events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            prev = last["event_hash"] if last else _ZERO
            event_id = uuid.uuid4().hex
            fields = dict(id=event_id, dedup_key=dedup_key,
                          scope=scope, content=content,
                          source_ref=source_ref, observed_at=observed,
                          recorded_at=recorded, expires_at=expiry,
                          supersedes=supersedes, previous_hash=prev)
            digest = _hash(fields)
            cursor = db.execute(
                """INSERT INTO memory_events
                   (id,dedup_key,scope,content,source_ref,observed_at,recorded_at,
                    expires_at,supersedes,previous_hash,event_hash)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (event_id, dedup_key, scope, content, source_ref, observed, recorded,
                 expiry, supersedes, prev, digest),
            )
            db.execute("INSERT INTO memory_fts(rowid,content) VALUES (?,?)",
                       (cursor.lastrowid, content))
            db.commit()
        return MemoryRecord(event_id, scope, content, source_ref,
                            observed, recorded, expiry, supersedes, digest)

    def remember(
        self, *, scope: str, content: str, source_ref: str,
        observed_at: datetime, expires_at: datetime | None = None
    ) -> MemoryRecord:
        return self._append(scope, content, source_ref, observed_at, expires_at=expires_at)

    def supersede(
        self, memory_id: str, *, scope: str, corrected_content: str,
        source_ref: str, observed_at: datetime
    ) -> MemoryRecord:
        return self._append(scope, corrected_content, source_ref,
                            observed_at, supersedes=memory_id)

    @staticmethod
    def _record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(*(row[k] for k in (
            "id", "scope", "content", "source_ref", "observed_at", "recorded_at",
            "expires_at", "supersedes", "event_hash"
        )))

    def recall(
        self, query: str, *, scope: str, as_of: datetime | None = None, limit: int = 8
    ) -> list[MemoryRecord]:
        if not _SCOPE.fullmatch(scope):
            raise ValueError("Invalid scope")
        if not 1 <= limit <= 20:
            raise ValueError("Limit must be 1..20")
        tokens = re.findall(r"(?u)\w+", query[:512].casefold())[:12]
        if not tokens:
            return []
        terms = " AND ".join('"' + token.replace('"', '""') + '"' for token in tokens)
        when = _utc(as_of if as_of is not None else self._clock())
        with self._connect() as db:
            rows = db.execute(
                """SELECT e.* FROM memory_fts f
                   JOIN memory_events e ON f.rowid=e.seq
                   WHERE memory_fts MATCH ? AND e.scope=?
                   AND e.recorded_at<=? AND e.observed_at<=?
                   AND (e.expires_at IS NULL OR e.expires_at>?)
                   AND NOT EXISTS (
                      SELECT 1 FROM memory_events s
                      WHERE s.supersedes=e.id AND s.recorded_at<=?
                   )
                   ORDER BY bm25(memory_fts), e.seq DESC LIMIT ?""",
                (terms, scope, when, when, when, when, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    def get_original(self, memory_id: str, *, scope: str) -> MemoryRecord | None:
        if not _SCOPE.fullmatch(scope):
            raise ValueError("Invalid scope")
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM memory_events WHERE id=? AND scope=?", (memory_id, scope)
            ).fetchone()
        return self._record(row) if row is not None else None

    def verify_chain(self) -> bool:
        previous = _ZERO
        with self._connect() as db:
            rows = db.execute("SELECT * FROM memory_events ORDER BY seq").fetchall()
        for row in rows:
            fields = {k: row[k] for k in (
                "id", "dedup_key", "scope", "content", "source_ref", "observed_at",
                "recorded_at", "expires_at", "supersedes", "previous_hash"
            )}
            if row["previous_hash"] != previous or row["event_hash"] != _hash(fields):
                return False
            previous = row["event_hash"]
        return True

    def event_count(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT count(*) FROM memory_events").fetchone()[0])
