"""Central structured logging: console + run-scoped file."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.config import RUNS_DIR


def setup_logging(level: str = "INFO", run_id: str | None = None) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    if run_id:
        d = RUNS_DIR / run_id
        d.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(d / "run.log", encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
