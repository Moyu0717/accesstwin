"""Evidence / validation panel data (P1-5). Mirrors the KPI table in the build spec §10.

Every row states where the number comes from. Nothing here is a field result: synthetic and planned items are
labelled as such, and no statistic is invented.
"""
from __future__ import annotations

import json

from accesstwin import config
from accesstwin.core import footfall
from accesstwin.core.obstacles import mock_analyze


def footfall_check() -> dict:
    """Counting error on the bundled sample clip (synthetic until a real CCTV run is recorded)."""
    pre = footfall.load_precomputed()
    clip = pre["sample_clip"]
    err = footfall.error_pct(int(clip["total"]), int(clip["manual_count"]))
    return {"auto": int(clip["total"]), "manual": int(clip["manual_count"]), "error_pct": err,
            "synthetic": bool(pre.get("synthetic", True))}


def classifier_check() -> dict:
    """Expected label (from the seed reports) vs what the active demo classifier returns for each bundled photo.

    The demo classifier keys on file names, so this is a pipeline check — not an AI accuracy result.
    """
    with open(config.SAMPLE_REPORTS_PATH, encoding="utf-8") as f:
        seeds = json.load(f)
    rows = []
    for s in seeds:
        if not s.get("photo"):
            continue
        predicted = mock_analyze(s["photo"])["obstacle_type"]
        rows.append({"photo": s["photo"], "expected": s.get("obstacle_type", "other"), "predicted": predicted,
                     "match": predicted == s.get("obstacle_type", "other")})
    acc = sum(r["match"] for r in rows) / len(rows) if rows else None
    return {"rows": rows, "accuracy": acc, "n": len(rows)}


def kpi_rows(fc: dict, cc: dict, bundle=None) -> list[dict]:
    """The spec §10 KPI table with an honest source/status column."""
    rows = [
        {"KPI": "Footfall count error vs manual count",
         "value": "—" if fc["error_pct"] is None else f"{fc['error_pct']:.1f}% ({fc['auto']} vs {fc['manual']})",
         "status": "synthetic sample (real CCTV run planned)" if fc["synthetic"] else "sample clip"},
        {"KPI": "Obstacle classification on bundled photos",
         "value": "—" if cc["accuracy"] is None else f"{cc['accuracy']:.0%} of {cc['n']}",
         "status": "demo classifier, pipeline check only — Groq test on 20–30 labelled real photos planned"},
    ]
    if bundle is not None:
        d = bundle.delta
        rows += [
            {"KPI": "Access Score before → after (recommended package)",
             "value": f"{d.index_before:.1f} → {d.index_after:.1f}", "status": "model result on fictional demo data"},
            {"KPI": "Newly reachable trips (recommended package)", "value": str(len(d.newly_reachable)),
             "status": "model result on fictional demo data"},
        ]
    rows += [
        {"KPI": "Route suggestions judged unsafe by real users", "value": "target 0",
         "status": "planned — validation with local disability / senior-citizen groups"},
        {"KPI": "User validation sessions", "value": "—", "status": "planned"},
    ]
    return rows
