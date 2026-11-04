"""Persistent, bounded history of sanitized forensic reports."""

import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from truthscan.fusion.engine import ForensicReport, Modality

DATA_DIR = Path("data/api")
HISTORY_LIMIT = 100


class Summary(BaseModel):
    analysis_id: UUID
    created_at: datetime
    status: Literal["completed", "partial", "failed"]
    processing_time_ms: float


class Analysis(Summary):
    report: ForensicReport


class HistoryEntry(Summary):
    assessment: Literal["REAL", "AI-GENERATED", "INCONCLUSIVE"]
    modalities: list[Modality]


@contextmanager
def database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATA_DIR / "results.sqlite3")) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        yield db


def save(analysis: Analysis):
    with database() as db:
        db.execute("INSERT INTO analyses VALUES (?, ?)", (str(analysis.analysis_id), analysis.model_dump_json()))
        db.execute("DELETE FROM analyses WHERE rowid IN "
                   "(SELECT rowid FROM analyses ORDER BY rowid DESC LIMIT -1 OFFSET ?)", (HISTORY_LIMIT,))


def get(analysis_id: UUID) -> Analysis | None:
    with database() as db:
        row = db.execute("SELECT payload FROM analyses WHERE id = ?", (str(analysis_id),)).fetchone()
    return Analysis.model_validate_json(row[0]) if row else None


def recent(limit: int) -> list[HistoryEntry]:
    with database() as db:
        rows = db.execute("SELECT payload FROM analyses ORDER BY rowid DESC LIMIT ?", (limit,))
        entries = []
        for (payload,) in rows:
            analysis = Analysis.model_validate_json(payload)
            entries.append(HistoryEntry(**analysis.model_dump(exclude={"report"}),
                                        assessment=analysis.report.assessment,
                                        modalities=list(analysis.report.findings)))
        return entries
