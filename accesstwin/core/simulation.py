"""What-if simulation and Upgrade ROI ranking (spec section 5.3)."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import networkx as nx
import pandas as pd

from accesstwin import config
from accesstwin.core.graph import add_edge, find_edge, node_name, set_edge_attrs
from accesstwin.core.personas import Persona
from accesstwin.core.scoring import ScoreResult, compute_scores, vulnerable_population


GROUP_NOUNS = {
    "wheelchair": "wheelchair users",
    "elderly": "elderly residents",
    "stroller": "parents with strollers",
    "visually_impaired": "visually impaired residents",
}
MATERIAL_SCORE_GAIN = 0.05  # a (residential, persona, category) pair "benefits" if its score rises by >= 5 points


def group_noun(persona: Persona) -> str:
    return GROUP_NOUNS.get(persona.key, f"{persona.label.lower()} users")


def load_upgrades(path: Path | str | None = None) -> list[dict]:
    with open(path or config.UPGRADES_PATH, encoding="utf-8") as f:
        return json.load(f)


def available_upgrades(upgrades: list[dict], mode: str = "operate") -> list[dict]:
    """Operate mode hides `design_mode_only` upgrades."""
    return [u for u in upgrades if mode == "design" or not u.get("design_mode_only")]


def apply_upgrade(G: nx.MultiGraph, upgrade: dict, assume_verified: bool = True) -> nx.MultiGraph:
    """Return a modified copy; the original graph is never mutated.

    With `assume_verified` (simulate_assume_verified=True) upgraded edges are treated as passable;
    every result card must still say "Requires on-site verification after completion".
    """
    H = copy.deepcopy(G)
    _apply_in_place(H, upgrade, assume_verified)
    return H


def apply_upgrades(G: nx.MultiGraph, upgrades: Iterable[dict], assume_verified: bool = True) -> nx.MultiGraph:
    """Combined scenario: several upgrades simulated together."""
    H = copy.deepcopy(G)
    for u in upgrades:
        _apply_in_place(H, u, assume_verified)
    return H


def _apply_in_place(H: nx.MultiGraph, upgrade: dict, assume_verified: bool) -> None:
    if upgrade.get("new_edge"):
        new = dict(upgrade["new_edge"])
        if assume_verified:
            new["status"] = "verified_accessible"
        add_edge(H, new)
        return
    changes = dict(upgrade.get("changes", {}))
    if assume_verified:
        changes["status"] = "verified_accessible"
    if not set_edge_attrs(H, upgrade["edge_id"], changes):
        raise KeyError(f"upgrade {upgrade.get('id')} references unknown edge {upgrade['edge_id']}")


@dataclass
class Delta:
    index_before: float
    index_after: float
    persona_before: dict[str, float]
    persona_after: dict[str, float]
    newly_reachable: list[dict] = field(default_factory=list)  # (residential, persona, category, dest)
    improved_pairs: int = 0
    beneficiaries: float = 0.0
    beneficiary_nodes: list[str] = field(default_factory=list)
    avg_detour_reduction_m: float = 0.0
    reductions: list[dict] = field(default_factory=list)
    explanation: str = ""

    @property
    def index_delta(self) -> float:
        return self.index_after - self.index_before

    def persona_delta(self) -> dict[str, float]:
        return {k: self.persona_after[k] - self.persona_before[k] for k in self.persona_after}


def compare(
    G: nx.MultiGraph, G2: nx.MultiGraph, personas: dict[str, Persona],
    before: ScoreResult | None = None, include_unverified: bool = False,
) -> Delta:
    before = before or compute_scores(G, personas, include_unverified)
    after = compute_scores(G2, personas, include_unverified)
    bmap, amap = before.pair_map(), after.pair_map()
    newly, reductions, gainers = [], [], set()
    gaining_personas: dict[str, set[str]] = {}
    improved = 0
    for key, a in amap.items():
        b = bmap.get(key)
        if b is None:
            continue
        if a.score > b.score + 1e-9:
            improved += 1
        if a.score - b.score >= MATERIAL_SCORE_GAIN or (a.reach == 1.0 and b.reach < 1.0):
            gainers.add(a.residential)
            gaining_personas.setdefault(a.residential, set()).add(a.persona)
        # "Newly reachable" = now reachable within the persona's max trip, and not before.
        if a.reach == 1.0 and b.reach < 1.0:
            newly.append({"residential": a.residential, "persona": a.persona, "category": a.category,
                          "dest": a.dest, "length_m": a.length_m,
                          "before": "unreachable" if b.reach == 0 else f"over max trip ({b.length_m:.0f} m)"})
        if a.reachable and b.reachable and a.length_m < b.length_m - 1e-9:
            reductions.append({"key": key, "before": b.length_m, "after": a.length_m})
    # Assumption: a node's vulnerable residents are spread evenly over the 4 personas.
    n_personas = len(personas) or 1
    beneficiaries = sum(vulnerable_population(G2, r) * len(ps) / n_personas for r, ps in gaining_personas.items())
    avg_red = sum(x["before"] - x["after"] for x in reductions) / len(reductions) if reductions else 0.0
    d = Delta(
        index_before=before.index, index_after=after.index,
        persona_before=before.persona_index, persona_after=after.persona_index,
        newly_reachable=newly, improved_pairs=improved, beneficiaries=beneficiaries,
        beneficiary_nodes=sorted(gainers), avg_detour_reduction_m=avg_red, reductions=reductions,
    )
    d.explanation = explain(G2, d, personas, reductions)
    return d


def benefit(delta: Delta) -> float:
    return (
        delta.index_delta * config.BENEFIT_INDEX_COEF
        + len(delta.newly_reachable) * config.BENEFIT_PAIR_COEF
        + delta.beneficiaries / config.BENEFIT_BENEFICIARY_DIVISOR
    )


def _fmt(m: float) -> str:
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{m:.0f} m"


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def explain(G: nx.MultiGraph, d: Delta, personas: dict[str, Persona], reductions: list[dict],
            upgrade_title: str | None = None) -> str:
    """Plain-language explanation, e.g. "Adding a ramp at E7 lets wheelchair users from Block A ..."."""
    head = upgrade_title or "This scenario"
    if d.improved_pairs == 0:
        return (f"{head}: no measurable change to reachability or detours for the four personas. "
                "It may still improve comfort or safety (e.g. lighting at night), which the index does not capture.")
    parts = []
    biggest = max(reductions, key=lambda x: x["before"] - x["after"], default=None)
    if biggest:
        r, p, c = biggest["key"]
        same = [x for x in reductions if x["key"][1] == p and x["key"][2] == c]
        froms = _join(sorted({node_name(G, x["key"][0]) for x in same}))
        parts.append(f"{head} lets {group_noun(personas[p])} from {froms} reach the {c.replace('_', ' ')} more directly; "
                     f"the detour drops from {_fmt(biggest['before'])} to {_fmt(biggest['after'])}.")
    if d.newly_reachable:
        cats = sorted({x["category"].replace("_", " ") for x in d.newly_reachable})
        verb = "" if biggest else f"{head}: "
        parts.append(f"{verb}{len(d.newly_reachable)} resident–persona trips become practical within a comfortable "
                     f"walking distance ({', '.join(cats)}).")
    pdelta = d.persona_delta()
    top_p = max(pdelta, key=lambda k: pdelta[k])
    parts.append(f"{personas[top_p].label} index {d.persona_before[top_p]:.0f} → {d.persona_after[top_p]:.0f}; "
                 f"township index {d.index_before:.1f} → {d.index_after:.1f} ({d.index_delta:+.1f}).")
    if d.beneficiaries >= 1:
        parts.append(f"An estimated {d.beneficiaries:.0f} residents who need extra mobility support benefit.")
    return " ".join(parts)


def rank_upgrades(
    G: nx.MultiGraph, upgrades: list[dict], personas: dict[str, Persona], mode: str = "operate",
    include_unverified: bool = False,
) -> pd.DataFrame:
    """Benefit = Δindex×10 + new_pairs×3 + Σbeneficiaries/100; ROI = benefit / cost weight (descending)."""
    before = compute_scores(G, personas, include_unverified)
    rows = []
    for u in available_upgrades(upgrades, mode):
        G2 = apply_upgrade(G, u)
        d = compare(G, G2, personas, before, include_unverified)
        b = benefit(d)
        w = config.COST_TIER_WEIGHTS[u["cost_tier"]]
        edge = u.get("edge_id") or (u.get("new_edge") or {}).get("id")
        d.explanation = explain(G2, d, personas, d.reductions, u["title"])
        rows.append({
            "id": u["id"], "title": u["title"], "edge": edge, "cost_tier": u["cost_tier"], "cost_weight": w,
            "delta_index": round(d.index_delta, 2), "new_reachable_pairs": len(d.newly_reachable),
            "beneficiaries": round(d.beneficiaries), "avg_detour_reduction_m": round(d.avg_detour_reduction_m),
            "benefit": round(b, 2), "roi": round(b / w, 2), "explanation": d.explanation,
            "design_mode_only": bool(u.get("design_mode_only")),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values(["roi", "benefit"], ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def edge_exists(G: nx.MultiGraph, upgrade: dict) -> bool:
    return bool(upgrade.get("new_edge")) or find_edge(G, upgrade["edge_id"]) is not None
