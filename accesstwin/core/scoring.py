"""Accessibility Gap Index and beneficiary calculation (spec section 5.2)."""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

from accesstwin.core.graph import categories, destination_nodes, residential_nodes
from accesstwin.core.personas import Persona
from accesstwin.core.routing import route


@dataclass
class PairScore:
    residential: str
    persona: str
    category: str
    dest: str | None
    reachable: bool
    length_m: float
    baseline_m: float
    detour_ratio: float | None
    reach: float
    score: float
    reason: str | None


@dataclass
class ScoreResult:
    index: float  # township index 0–100
    persona_index: dict[str, float]
    node_persona: dict[tuple[str, str], float]  # (residential, persona) -> 0–1
    pairs: list[PairScore] = field(default_factory=list)

    def pair_map(self) -> dict[tuple[str, str, str], PairScore]:
        return {(p.residential, p.persona, p.category): p for p in self.pairs}

    @property
    def unreachable_pairs(self) -> list[PairScore]:
        return [p for p in self.pairs if p.reach == 0]

    def gap_matrix(self, G: nx.MultiGraph | None = None) -> pd.DataFrame:
        """Residential × persona heatmap data (0–100)."""
        rows = sorted({r for r, _ in self.node_persona})
        cols = list(dict.fromkeys(p for _, p in self.node_persona))
        df = pd.DataFrame(index=rows, columns=cols, dtype=float)
        for (r, p), v in self.node_persona.items():
            df.loc[r, p] = round(v * 100, 1)
        if G is not None:
            df.index = [G.nodes[r].get("name", r) for r in df.index]
        return df

    def pairs_frame(self) -> pd.DataFrame:
        return pd.DataFrame([p.__dict__ for p in self.pairs])


def detour_penalty(detour_ratio: float | None) -> float:
    if detour_ratio is None:
        return 1.0
    return min(1.0, max(0.0, (detour_ratio - 1.0) / 2.0))


def pair_score(G: nx.MultiGraph, r: str, persona: Persona, category: str, include_unverified: bool = False) -> PairScore:
    """Nearest reachable destination of `category` for this persona (shortest persona route length)."""
    best = None
    first_reason = None
    for d in destination_nodes(G, category):
        res = route(G, r, d["id"], persona, include_unverified)
        if res.reachable:
            if best is None or res.length_m < best.length_m:
                best = res
        elif first_reason is None:
            first_reason = res.reason
    if best is None:
        return PairScore(r, persona.key, category, None, False, 0.0, 0.0, None, 0.0, 0.0, first_reason)
    reach = 1.0 if best.within_max_trip else 0.5
    score = reach * (1 - 0.5 * detour_penalty(best.detour_ratio))
    return PairScore(r, persona.key, category, best.dest, True, best.length_m, best.baseline_length_m,
                     best.detour_ratio, reach, score, best.reason)


def compute_scores(G: nx.MultiGraph, personas: dict[str, Persona], include_unverified: bool = False) -> ScoreResult:
    cats = categories(G)
    total_imp = sum(cats.values()) or 1.0
    pairs: list[PairScore] = []
    node_persona: dict[tuple[str, str], float] = {}
    for rn in residential_nodes(G):
        for pk, persona in personas.items():
            acc = 0.0
            for cat, imp in cats.items():
                ps = pair_score(G, rn["id"], persona, cat, include_unverified)
                pairs.append(ps)
                acc += imp * ps.score
            node_persona[(rn["id"], pk)] = acc / total_imp

    # Township index: weights population × vulnerable_share × equity_weight_p.
    num = den = 0.0
    persona_index: dict[str, float] = {}
    for pk, persona in personas.items():
        pn = pd_ = 0.0
        for rn in residential_nodes(G):
            w = float(rn.get("population", 0)) * float(rn.get("vulnerable_share", 0))
            v = node_persona[(rn["id"], pk)]
            pn += w * v
            pd_ += w
            num += w * persona.equity_weight * v
            den += w * persona.equity_weight
        persona_index[pk] = 100 * pn / pd_ if pd_ else 0.0
    index = 100 * num / den if den else 0.0
    return ScoreResult(index=index, persona_index=persona_index, node_persona=node_persona, pairs=pairs)


def vulnerable_population(G: nx.MultiGraph, r: str) -> float:
    n = G.nodes[r]
    return float(n.get("population", 0)) * float(n.get("vulnerable_share", 0))


def critical_gaps(result: ScoreResult, G: nx.MultiGraph, personas: dict[str, Persona], top: int = 3) -> list[dict]:
    """Worst (residential, persona, category) gaps weighted by importance × vulnerable population × equity."""
    cats = categories(G)
    rows = []
    for p in result.pairs:
        if p.score >= 1.0:
            continue
        loss = (1 - p.score) * cats[p.category] * vulnerable_population(G, p.residential) * personas[p.persona].equity_weight
        rows.append({"pair": p, "weight": loss})
    rows.sort(key=lambda x: -x["weight"])
    return rows[:top]
