"""Single-file HTML "Planning Brief" + CSV export (spec section 5.8). Returned as strings — no server-side files."""
from __future__ import annotations

import html
from collections import Counter
from datetime import datetime

import networkx as nx
import pandas as pd

from accesstwin.core.demand import EdgeDemand
from accesstwin.core.personas import Persona
from accesstwin.core.scoring import ScoreResult

DISCLAIMER = (
    "AccessTwin is a planning aid, not proof of compliance with accessibility design standards (e.g. MS 1184). "
    "All routes and upgrades require on-site verification. Persona rules are demo assumptions. Costs are relative "
    "tiers only (low / medium / high), never construction estimates. AI suggestions are reviewed by a person "
    "before they change the map. CCTV analytics are aggregate counts only."
)


def _e(x) -> str:
    return html.escape(str(x))


def report_stats(reports: list[dict]) -> dict:
    return {
        "total": len(reports),
        "by_status": dict(Counter(r["status"] for r in reports)),
        "by_type": dict(Counter((r.get("ai") or {}).get("obstacle_type", "other") for r in reports)),
        "by_role": dict(Counter(r["reporter_role"] for r in reports)),
    }


def brief_html(
    G: nx.MultiGraph, personas: dict[str, Persona], scores: ScoreResult, ranking: pd.DataFrame,
    demand: list[EdgeDemand], reports: list[dict], mode: str = "operate", bundle=None, scenario: dict | None = None,
) -> str:
    stats = report_stats(reports)
    title = "Pre-construction Accessibility Review" if mode == "design" else "Accessibility Planning Brief"
    gm = scores.gap_matrix(G)
    persona_rows = "".join(
        f"<tr><td>{_e(personas[k].label)}</td><td>{v:.0f}</td></tr>" for k, v in scores.persona_index.items())
    gap_head = "".join(f"<th>{_e(personas[c].label)}</th>" for c in gm.columns)
    gap_rows = "".join(
        "<tr><td>" + _e(idx) + "</td>" + "".join(f"<td>{v:.0f}</td>" for v in row) + "</tr>"
        for idx, row in zip(gm.index, gm.values))
    top = ranking.head(5) if not ranking.empty else ranking
    up_rows = "".join(
        f"<tr><td>#{r['rank']}</td><td><b>{_e(r['id'])}</b> {_e(r['title'])}</td><td>{_e(r['cost_tier'])}</td>"
        f"<td>{r['delta_index']:+.1f}</td><td>{r['new_reachable_pairs']}</td><td>{r['beneficiaries']}</td>"
        f"<td>{r['roi']:.1f}</td></tr><tr><td></td><td colspan='6' class='ex'>{_e(r['explanation'])} "
        f"<i>Requires on-site verification after completion.</i></td></tr>"
        for _, r in top.iterrows())
    sup = [d for d in demand if d.suppressed]
    sup_rows = "".join(
        f"<tr><td>{_e(d.edge_id)}</td><td>{_e(d.cctv_id)}</td><td>{d.observed:.0f}</td><td>{d.expected:.0f}</td>"
        f"<td>{d.ratio:.2f}</td><td>{_e('; '.join(d.barrier_reasons[:3]))}</td></tr>" for d in sup
    ) or "<tr><td colspan='6'>No suppressed-demand segments detected.</td></tr>"
    status_txt = ", ".join(f"{k}: {v}" for k, v in stats["by_status"].items()) or "none"
    type_txt = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in stats["by_type"].items()) or "none"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AccessTwin — {_e(title)}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1F2937;max-width:960px;margin:24px auto;padding:0 16px;line-height:1.45}}
h1{{color:#0F766E;margin-bottom:4px}} h2{{border-bottom:2px solid #D1E7E4;padding-bottom:4px;margin-top:28px}}
table{{border-collapse:collapse;width:100%;margin:8px 0}} th,td{{border:1px solid #E5E7EB;padding:6px 8px;text-align:left;font-size:14px;vertical-align:top}}
th{{background:#F0F7F6}} .big{{font-size:44px;font-weight:700;color:#0F766E}} .muted{{color:#6B7280;font-size:13px}}
.ex{{color:#374151;font-size:13px;background:#FAFAFA}} .disc{{margin-top:32px;padding:12px;border:1px solid #FCD34D;background:#FFFBEB;font-size:13px}}
@media print{{body{{margin:0}} h2{{break-after:avoid}}}}
</style></head><body>
<h1>{_e(title)}</h1>
<div class="muted">{_e(G.graph.get('meta', {}).get('name', 'Demo Township'))} — fictional demo layout · generated {datetime.now():%Y-%m-%d %H:%M} · mode: {_e(mode)}</div>
<h2>Access Score (higher is better)</h2>
<div class="big">{scores.index:.0f}<span style="font-size:20px"> / 100</span></div>
<table><tr><th>Profile</th><th>Access Score</th></tr>{persona_rows}</table>
<h3>Gap matrix (residential × persona, 0–100)</h3>
<table><tr><th>Residential</th>{gap_head}</tr>{gap_rows}</table>
{_scenario_html(scenario)}
{_bundle_html(bundle)}
<h2>Top 5 recommended upgrades (upgrade priority score = benefit ÷ cost tier)</h2>
<table><tr><th>Rank</th><th>Upgrade</th><th>Cost tier</th><th>Δ Access Score</th><th>Newly reachable (modelled)</th><th>Estimated residents (model)</th><th>Upgrade priority score</th></tr>{up_rows}</table>
<h2>Suppressed-demand segments</h2>
<p class="muted">Observed CCTV footfall far below the gravity-model expectation on a route with a barrier: people may not walk here because they can't. Edges without CCTV are not inferred.</p>
<table><tr><th>Edge</th><th>Camera</th><th>Observed</th><th>Expected</th><th>Ratio</th><th>Barriers</th></tr>{sup_rows}</table>
<h2>Obstacle reports</h2>
<p>{stats['total']} reports — by status: {_e(status_txt)}. By type: {_e(type_txt)}.</p>
<div class="disc"><b>Disclaimer.</b> {_e(DISCLAIMER)}</div>
<p class="muted">Print this page to PDF from your browser (Ctrl+P) to share it.</p>
</body></html>"""


def _scenario_html(sc: dict | None) -> str:
    """Study section for the same Baseline / Scenario snapshot shown on the Compare page (V2 Deliver)."""
    if not sc:
        return ""
    rows = "".join(f"<tr><td>{_e(r['assessment'])}</td><td>{_e(r['baseline'])}</td><td>{_e(r['scenario'])}</td>"
                   f"<td>{_e(r['change'])}</td><td>{_e(r['source'])}</td></tr>" for r in sc.get("rows", []))
    steps = "".join(f"<li><b>{_e(h)}</b> — {_e(b)}</li>" for h, b in sc.get("steps", []))
    ev = "".join(f"<figure style='display:inline-block;margin:0 12px 12px 0;max-width:240px'>"
                 f"<img src='data:image/jpeg;base64,{x['b64']}' alt='{_e(x['caption'])}' style='max-width:240px'>"
                 f"<figcaption style='font-size:12px'>{_e(x['caption'])}</figcaption></figure>"
                 for x in sc.get("evidence", []))
    ev_html = f"<h3>Evidence</h3>{ev}" if ev else "<h3>Evidence</h3><p>No photo evidence yet.</p>"
    table = (f"<table><tr><th>Assessment</th><th>Baseline</th><th>Scenario (simulated)</th><th>Change</th>"
             f"<th>Source</th></tr>{rows}</table>") if rows else "<p>Not assessed — confirm site conditions first.</p>"
    return (f"<h2>Study: {_e(sc.get('location', ''))}</h2>"
            f"<p>Proposed change: <b>{_e(sc.get('upgrade') or 'none yet')}</b> · data version {_e(sc.get('version', ''))} · "
            f"<b>Simulated</b> values on <b>synthetic</b> demo data — the recorded network is unchanged.</p>{table}"
            f"{ev_html}<h3>Delivery steps</h3><ol>{steps}</ol>")


def _bundle_html(bundle) -> str:
    if bundle is None:
        return ""
    d = bundle.delta
    by = ", ".join(f"{_e(k.replace('_', ' '))} {v:.0f}" for k, v in d.beneficiaries_by_persona.items())
    return (f"<h2>Recommended package: {_e(' + '.join(bundle.upgrade_ids))}</h2>"
            f"<p>Within a budget of {bundle.budget:g} cost-weight units (uses {bundle.cost_weight:g}). Access Score "
            f"{d.index_before:.1f} → {d.index_after:.1f} ({d.index_delta:+.1f}); {len(d.newly_reachable)} newly reachable combinations (modelled); "
            f"≈{d.beneficiaries:.0f} residents who need extra mobility support benefit ({by}).</p>"
            f"<p class='ex'>{_e(bundle.explanation)} <i>Requires on-site verification after completion.</i></p>")


def ranking_csv(ranking: pd.DataFrame) -> str:
    cols = ["rank", "id", "title", "edge", "cost_tier", "delta_index", "new_reachable_pairs", "beneficiaries",
            "avg_detour_reduction_m", "benefit", "roi", "explanation"]
    return ranking[[c for c in cols if c in ranking.columns]].to_csv(index=False)


def demand_csv(demand: list[EdgeDemand]) -> str:
    return pd.DataFrame([{
        "edge": d.edge_id, "camera": d.cctv_id, "observed": d.observed, "expected": d.expected, "ratio": d.ratio,
        "status": d.status, "barrier_edges": " ".join(d.barrier_edges),
    } for d in demand]).to_csv(index=False)
