"""Cached pure computations, keyed by the overlay fingerprint (fix pack F3.6).

Every function takes hashable keys only and rebuilds what it needs, so results are shared across reruns and
pages. "Reset demo data" calls st.cache_data.clear(); any approval/verification changes the overlay key.
"""
from __future__ import annotations

import json

import streamlit as st

from accesstwin.core import report, store
from accesstwin.core.demand import suppressed_demand
from accesstwin.core.graph import build_graph, load_township
from accesstwin.core.personas import load_personas
from accesstwin.core.scoring import compute_scores
from accesstwin.core.simulation import load_upgrades, rank_upgrades


def _graph(overlay_key: str):
    return build_graph(load_township(), json.loads(overlay_key) or None)


@st.cache_data(max_entries=16, show_spinner="Computing the Access Score…")
def scores(overlay_key: str):
    return compute_scores(_graph(overlay_key), load_personas())


@st.cache_data(max_entries=16, show_spinner="Ranking every candidate upgrade…")
def ranking(overlay_key: str, mode: str):
    return rank_upgrades(_graph(overlay_key), load_upgrades(), load_personas(), mode=mode)


def camera_counts() -> dict:
    from accesstwin.core.footfall import camera_counts as _counts

    return _counts()


@st.cache_data(max_entries=16, show_spinner=False)
def demand(overlay_key: str, counts_key: str):
    return suppressed_demand(_graph(overlay_key), load_personas(), json.loads(counts_key))


@st.cache_data(max_entries=16, show_spinner=False)
def brief_html(overlay_key: str, counts_key: str, mode: str, reports_key: str, scenario_key: str = "") -> str:
    G = _graph(overlay_key)
    return report.brief_html(G, load_personas(), scores(overlay_key), ranking(overlay_key, mode),
                             demand(overlay_key, counts_key), store.list_reports(), mode, bundle(overlay_key, mode),
                             json.loads(scenario_key) if scenario_key else None)


@st.cache_data(max_entries=64, show_spinner="Simulating…")
def scenario(overlay_key: str, upgrade_ids: tuple[str, ...]):
    """(Delta, explanation) for a combined upgrade scenario."""
    from accesstwin.core.simulation import apply_upgrades, compare, explain

    G = _graph(overlay_key)
    by_id = {u["id"]: u for u in load_upgrades()}
    chosen = [by_id[i] for i in upgrade_ids]
    G2 = apply_upgrades(G, chosen)
    P = load_personas()
    d = compare(G, G2, P, before=scores(overlay_key))
    title = chosen[0]["title"] if len(chosen) == 1 else f"Combined scenario ({', '.join(upgrade_ids)})"
    return d, explain(G2, d, P, d.reductions, title)


@st.cache_data(max_entries=16, show_spinner="Choosing the best low-cost package…")
def bundle(overlay_key: str, mode: str):
    """Recommended low-cost package (P1-2), or None."""
    from accesstwin.core.simulation import recommend_bundle

    return recommend_bundle(_graph(overlay_key), load_upgrades(), load_personas(), mode=mode,
                            ranking=ranking(overlay_key, mode))


def data_version(overlay_key: str) -> str:
    """Short fingerprint of the base data + overlay, shown on every V2 view and in the brief."""
    import hashlib

    from accesstwin import config

    h = hashlib.sha256()
    for p in (config.TOWNSHIP_PATH, config.PERSONAS_PATH, config.UPGRADES_PATH):
        h.update(p.read_bytes())
    h.update(overlay_key.encode("utf-8"))
    return h.hexdigest()[:8]


@st.cache_data(max_entries=128, show_spinner=False)
def journey(overlay_key: str, upgrade_ids: tuple[str, ...], origin: str, dest: str, persona_key: str):
    """route() for one journey on the baseline (no upgrades) or a session-only scenario graph."""
    from accesstwin.core.routing import route
    from accesstwin.core.simulation import apply_upgrades

    G = _graph(overlay_key)
    if upgrade_ids:
        by_id = {u["id"]: u for u in load_upgrades()}
        G = apply_upgrades(G, [by_id[i] for i in upgrade_ids])
    return route(G, origin, dest, load_personas()[persona_key])
