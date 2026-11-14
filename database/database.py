"""SQLite persistence for MarketMind AI runs, evidence index, and metrics."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.config import ROOT_DIR

DB_PATH = ROOT_DIR / "database" / "marketmind.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                topic TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                evidence_count INTEGER DEFAULT 0,
                tool_calls INTEGER DEFAULT 0,
                iterations INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0,
                tokens INTEGER DEFAULT 0,
                confidence TEXT,
                qc_pass INTEGER,
                approval TEXT,
                incomplete INTEGER DEFAULT 0,
                is_demo INTEGER DEFAULT 0,
                state_path TEXT,
                meta_json TEXT
            );

            CREATE TABLE IF NOT EXISTS evidence_index (
                evidence_id TEXT PRIMARY KEY,
                run_id TEXT,
                question_id TEXT,
                claim TEXT,
                claim_type TEXT,
                confidence TEXT,
                credibility TEXT,
                source_detail TEXT,
                source_ref TEXT,
                is_demo INTEGER DEFAULT 0,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                ts TEXT,
                kind TEXT,
                message TEXT,
                is_demo INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS evaluation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT,
                verdict TEXT,
                detail TEXT,
                run_at TEXT,
                meta_json TEXT
            );
            """
        )


def upsert_run(row: dict[str, Any]) -> None:
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, topic, status, created_at, updated_at, evidence_count,
                tool_calls, iterations, cost_usd, tokens, confidence, qc_pass,
                approval, incomplete, is_demo, state_path, meta_json
            ) VALUES (
                :run_id, :topic, :status, :created_at, :updated_at, :evidence_count,
                :tool_calls, :iterations, :cost_usd, :tokens, :confidence, :qc_pass,
                :approval, :incomplete, :is_demo, :state_path, :meta_json
            )
            ON CONFLICT(run_id) DO UPDATE SET
                topic=excluded.topic,
                status=excluded.status,
                updated_at=excluded.updated_at,
                evidence_count=excluded.evidence_count,
                tool_calls=excluded.tool_calls,
                iterations=excluded.iterations,
                cost_usd=excluded.cost_usd,
                tokens=excluded.tokens,
                confidence=excluded.confidence,
                qc_pass=excluded.qc_pass,
                approval=excluded.approval,
                incomplete=excluded.incomplete,
                is_demo=excluded.is_demo,
                state_path=excluded.state_path,
                meta_json=excluded.meta_json
            """,
            {
                "run_id": row["run_id"],
                "topic": row.get("topic", ""),
                "status": row.get("status", "unknown"),
                "created_at": row.get("created_at") or now,
                "updated_at": now,
                "evidence_count": row.get("evidence_count", 0),
                "tool_calls": row.get("tool_calls", 0),
                "iterations": row.get("iterations", 0),
                "cost_usd": row.get("cost_usd", 0.0),
                "tokens": row.get("tokens", 0),
                "confidence": row.get("confidence"),
                "qc_pass": 1 if row.get("qc_pass") else 0 if row.get("qc_pass") is not None else None,
                "approval": row.get("approval"),
                "incomplete": 1 if row.get("incomplete") else 0,
                "is_demo": 1 if row.get("is_demo") else 0,
                "state_path": row.get("state_path"),
                "meta_json": json.dumps(row.get("meta") or {}),
            },
        )


def replace_evidence_for_run(run_id: str, records: list[dict[str, Any]], is_demo: bool = False) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute("DELETE FROM evidence_index WHERE run_id = ?", (run_id,))
        for e in records:
            conn.execute(
                """
                INSERT OR REPLACE INTO evidence_index (
                    evidence_id, run_id, question_id, claim, claim_type,
                    confidence, credibility, source_detail, source_ref, is_demo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    e.get("evidence_id"),
                    run_id,
                    e.get("question_id"),
                    e.get("claim"),
                    e.get("claim_type"),
                    e.get("confidence"),
                    e.get("credibility"),
                    e.get("source_detail"),
                    e.get("source_ref"),
                    1 if is_demo else 0,
                ),
            )


def log_activity(run_id: str, kind: str, message: str, is_demo: bool = False) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO activities (run_id, ts, kind, message, is_demo) VALUES (?, ?, ?, ?, ?)",
            (
                run_id,
                datetime.now(timezone.utc).isoformat(),
                kind,
                message,
                1 if is_demo else 0,
            ),
        )


def list_runs(limit: int = 50, include_demo: bool = True) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        if include_demo:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM runs WHERE is_demo = 0 ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id: str) -> dict[str, Any] | None:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def list_evidence(
    run_id: str | None = None,
    claim_type: str | None = None,
    confidence: str | None = None,
) -> list[dict[str, Any]]:
    init_db()
    q = "SELECT * FROM evidence_index WHERE 1=1"
    params: list[Any] = []
    if run_id:
        q += " AND run_id = ?"
        params.append(run_id)
    if claim_type and claim_type != "all":
        q += " AND claim_type = ?"
        params.append(claim_type)
    if confidence and confidence != "all":
        q += " AND confidence = ?"
        params.append(confidence)
    q += " ORDER BY run_id DESC"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def recent_activities(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM activities ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def dashboard_kpis() -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
        completed = conn.execute(
            "SELECT COUNT(*) c FROM runs WHERE approval = 'approve'"
        ).fetchone()["c"]
        evidence = conn.execute("SELECT COUNT(*) c FROM evidence_index").fetchone()["c"]
        spend = conn.execute("SELECT COALESCE(SUM(cost_usd),0) s FROM runs").fetchone()["s"]
        conf_rows = conn.execute(
            "SELECT confidence, COUNT(*) c FROM runs WHERE confidence IS NOT NULL GROUP BY confidence"
        ).fetchall()
        success_den = conn.execute(
            "SELECT COUNT(*) c FROM runs WHERE status IN ('completed','approved','rejected','partial')"
        ).fetchone()["c"]
        success_num = conn.execute(
            "SELECT COUNT(*) c FROM runs WHERE approval = 'approve' OR (qc_pass = 1 AND incomplete = 0)"
        ).fetchone()["c"]
    conf_map = {r["confidence"]: r["c"] for r in conf_rows}
    # Weighted average proxy: high=3, medium=2, low=1
    weight = {"high": 3, "medium": 2, "low": 1}
    total_w = sum(weight.get(k, 0) * v for k, v in conf_map.items())
    total_c = sum(conf_map.values()) or 1
    avg_conf = round(total_w / total_c, 2)
    rate = round((success_num / success_den) * 100, 1) if success_den else 0.0
    return {
        "total_projects": total,
        "completed_reports": completed,
        "evidence_records": evidence,
        "average_confidence_score": avg_conf,
        "estimated_api_spend_usd": round(float(spend or 0), 4),
        "research_success_rate_pct": rate,
    }


def status_distribution() -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) c FROM runs GROUP BY status"
        ).fetchall()
    return [{"status": r["status"] or "unknown", "count": r["c"]} for r in rows]


def activity_over_time() -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS day, COUNT(*) c
            FROM runs
            GROUP BY day
            ORDER BY day
            """
        ).fetchall()
    return [{"day": r["day"], "count": r["c"]} for r in rows]


def claim_type_distribution() -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT claim_type, COUNT(*) c FROM evidence_index GROUP BY claim_type"
        ).fetchall()
    return [{"claim_type": r["claim_type"] or "unknown", "count": r["c"]} for r in rows]


def save_evaluation_result(case_id: str, verdict: str, detail: str, meta: dict | None = None) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO evaluation_results (case_id, verdict, detail, run_at, meta_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                case_id,
                verdict,
                detail,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(meta or {}),
            ),
        )


def list_evaluation_results(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM evaluation_results ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
