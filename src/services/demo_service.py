"""Clearly labelled DEMO DATA seed for empty installations."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from database import database as db


DEMO_RUN_ID = "demo_s1_ai_support"


def seed_demo_if_empty() -> bool:
    """Insert labelled demo records only when no real runs exist."""
    db.init_db()
    existing = db.list_runs(limit=5, include_demo=False)
    demos = [r for r in db.list_runs(limit=5) if r.get("is_demo")]
    if existing or demos:
        return False

    now = datetime.now(timezone.utc).isoformat()
    db.upsert_run(
        {
            "run_id": DEMO_RUN_ID,
            "topic": "[DEMO DATA] AI-powered customer support software market",
            "status": "approved",
            "created_at": now,
            "evidence_count": 6,
            "tool_calls": 12,
            "iterations": 8,
            "cost_usd": 0.042,
            "tokens": 18500,
            "confidence": "medium",
            "qc_pass": True,
            "approval": "approve",
            "incomplete": False,
            "is_demo": True,
            "state_path": None,
            "meta": {"label": "DEMO DATA"},
        }
    )
    demo_evidence = [
        {
            "evidence_id": f"demo_ev_{i}",
            "question_id": "demo_q1",
            "claim": claim,
            "claim_type": ctype,
            "confidence": conf,
            "credibility": cred,
            "source_detail": src,
            "source_ref": f"demo_src_{i}",
        }
        for i, (claim, ctype, conf, cred, src) in enumerate(
            [
                (
                    "[DEMO DATA] Zendesk Suite Team starts at $55/agent/month (annual).",
                    "fact",
                    "high",
                    "high",
                    "demo://zendesk_pricing",
                ),
                (
                    "[DEMO DATA] Freshdesk Pro is listed near $49/agent/month in the sample corpus.",
                    "fact",
                    "high",
                    "high",
                    "demo://freshdesk_pricing",
                ),
                (
                    "[DEMO DATA] Resolution-based AI pricing is expanding among conversational vendors.",
                    "inference",
                    "medium",
                    "medium",
                    "demo://trend_note",
                ),
                (
                    "[DEMO DATA] Sample sources disagree on 2025 market size ($8.2bn vs $5.1bn).",
                    "uncertainty",
                    "low",
                    "medium",
                    "demo://market_size_conflict",
                ),
                (
                    "[DEMO DATA] SMB ecommerce niches remain relatively open for vertical helpdesks.",
                    "recommendation",
                    "medium",
                    "medium",
                    "demo://positioning",
                ),
                (
                    "[DEMO DATA] Capacity enterprise seat minimum is not established in the sample corpus.",
                    "uncertainty",
                    "low",
                    "unknown",
                    "demo://gap",
                ),
            ],
            start=1,
        )
    ]
    db.replace_evidence_for_run(DEMO_RUN_ID, demo_evidence, is_demo=True)
    db.log_activity(
        DEMO_RUN_ID,
        "demo_seed",
        "[DEMO DATA] Seeded sample AI customer support research project",
        is_demo=True,
    )
    return True
