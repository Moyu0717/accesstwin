"""V2 planning workspace: view models and shared chrome (plan §8 stage A).

Every number here comes from the core (graph, routing, scoring, simulation) through ui.cached — nothing is
copied from the design prototype. Scenarios live in the session only and never touch the database.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field

import streamlit as st

from accesstwin import config
from accesstwin.core.graph import build_graph, find_edge, load_township, node_name
from accesstwin.core.personas import load_personas
from accesstwin.core.routing import edge_passable
from accesstwin.core.scoring import critical_gaps
from accesstwin.core.simulation import load_upgrades
from accesstwin.ui import cached
from accesstwin.ui.i18n import t

DISPLAY_NAMES_PATH = config.DATA_DIR / "display_names.json"
_EDGE_IN_REASON = re.compile(r"^(E\w+):")

STAGES = [("network", "pages/0_🏠_Overview.py"), ("compare", "pages/8_Compare.py"), ("deliver", "pages/9_Deliver.py")]
RESIDENT_PAGES = [("pages/1_🧭_Route_Planner.py", "res_plan"), ("pages/2_📸_Report_Obstacle.py", "res_report"),
                  ("pages/10_Track_Report.py", "res_track")]
STAFF_PAGES = [("pages/3_✅_Verification_Queue.py", "nav_queue"), ("pages/4_🎥_Footfall_Analytics.py", "nav_footfall"),
               ("pages/5_🏗️_Upgrade_Simulator.py", "nav_sim"), ("pages/6_📊_Planner_Dashboard.py", "nav_dash"),
               ("pages/7_ℹ️_About.py", "nav_about")]
MORE_PAGES = RESIDENT_PAGES + STAFF_PAGES
LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M4 27 L16 5 L28 27"/><path d="M10 27 L16 16 L22 27"/>'
        '<path d="M3 27 H29"/></svg>')


def esc(x) -> str:
    """HTML-escape anything that goes into unsafe_allow_html markup (data or user text)."""
    return html.escape(str(x), quote=True)


# ---------------------------------------------------------------- session context (plan §7.1)

def ctx() -> dict:
    """Selected segment, persona and session-only scenario, kept across pages."""
    c = st.session_state.setdefault("ws_ctx", {"segment": None, "scenario": ()})
    c.setdefault("segment", None)
    c.setdefault("scenario", ())
    return c


def persona_key() -> str:
    return st.session_state.get("persona", "wheelchair")


# ---------------------------------------------------------------- view models

def display_names() -> dict[str, str]:
    try:
        with open(DISPLAY_NAMES_PATH, encoding="utf-8") as f:
            return json.load(f).get("segments", {})
    except (OSError, ValueError):
        return {}


def segment_label(G, edge_id: str) -> str:
    e = find_edge(G, edge_id)
    alias = display_names().get(edge_id)
    if alias:
        return alias
    return f"{node_name(G, e['from'])}–{node_name(G, e['to'])}" if e else edge_id


@dataclass
class Location:
    edge_id: str
    label: str
    kind: str  # "barrier" | "inspection" | "blocked"
    status_text: str
    origin: str | None
    dest: str | None
    affected: list[str] = field(default_factory=list)  # persona keys that cannot use the segment
    condition_value: str = ""
    condition_unit: str = ""
    condition_text: str = ""
    upgrade: dict | None = None
    short: str = ""  # barrier in plain words for the priority list, e.g. "15 cm step"


def _condition(e: dict) -> tuple[str, str, str, str, str]:
    """(kind, value, unit, sentence, short) — the recorded *physical fact* first (X2: never "Blocked")."""
    obstructions = [o for o in e.get("obstacles", []) or [] if o.get("kind") == "obstruction"]
    if e.get("has_step") or float(e.get("curb_height_cm") or 0) > 2:
        c = float(e["curb_height_cm"])
        return ("barrier", f"{c:g}", "cm", "raised step — a level change interrupts the direct connection.",
                f"{c:g} cm step")
    if obstructions:
        o = obstructions[0]
        return ("obstruction", o.get("text", "obstruction").capitalize(), "",
                f"confirmed by report #{o.get('report_id')} — affects {', '.join(o.get('personas', [])) or 'some profiles'}.",
                o.get("text", "obstruction"))
    if e.get("status") == "unverified":
        return ("inspection", f"{float(e.get('width_cm', 0)) / 100:.2f}", "m",
                "recorded width · On-site measurement pending — this synthetic record is not a site measurement. "
                "Current access is not verified.", "unverified record")
    if e.get("status") == "blocked":
        return "blocked", "Closed", "", "Explicit full closure recorded for this segment.", "closed"
    if e.get("surface") in ("broken", "gravel"):
        return ("barrier", e["surface"].capitalize(), "", "surface recorded as unsuitable for some profiles.",
                f"{e['surface']} surface")
    if float(e.get("max_slope_pct") or 0) > 8:
        sl = float(e["max_slope_pct"])
        return "barrier", f"{sl:g}", "%", "recorded slope — steep for some profiles.", f"{sl:g}% slope"
    return "barrier", "", "", "Recorded condition limits some profiles.", "recorded barrier"


def _journey_for(G, edge_id: str, gaps: list) -> tuple[str | None, str | None]:
    """Demo journey: among critical gaps blocked by this segment, the most populous home → its destination."""
    from accesstwin.core.scoring import pair_score  # noqa: F401  (documented dependency)

    cands = [g["pair"] for g in gaps if (m := _EDGE_IN_REASON.match(g["pair"].reason or "")) and m.group(1) == edge_id]
    if not cands:
        return None, None
    best = max(cands, key=lambda p: float(G.nodes[p.residential].get("population", 0)))
    dests = [n for n, d in G.nodes(data=True) if d.get("type") == "destination" and d.get("category") == best.category]
    return best.residential, (best.dest or (dests[0] if dests else None))


@st.cache_data(max_entries=16, show_spinner=False)
def priority_locations(overlay_key: str, limit: int = 4) -> list[Location]:
    """Segments that cause the worst critical gaps (from scoring.critical_gaps), in priority order."""
    G = build_graph(load_township(), json.loads(overlay_key) or None)
    P = load_personas()
    s = cached.scores(overlay_key)
    gaps = critical_gaps(s, G, P, top=40)
    ups = {u["edge_id"]: u for u in load_upgrades() if u.get("edge_id") and not u.get("design_mode_only")}
    out: list[Location] = []
    for g in gaps:
        m = _EDGE_IN_REASON.match(g["pair"].reason or "")
        if not m or any(x.edge_id == m.group(1) for x in out):
            continue
        eid = m.group(1)
        e = find_edge(G, eid)
        kind, value, unit, sentence, short = _condition(e)
        affected = [k for k, p in P.items() if not edge_passable(e, p, include_unverified=False)[0]]
        origin, dest = _journey_for(G, eid, gaps)
        status = {"barrier": "Barrier identified", "inspection": "Needs inspection", "blocked": "Closed",
                  "obstruction": "Obstruction confirmed"}[kind]
        out.append(Location(eid, segment_label(G, eid), kind, status, origin, dest, affected, value, unit, sentence,
                            ups.get(eid), short))
        if len(out) >= limit:
            break
    return out


def find_location(overlay_key: str, edge_id: str | None) -> Location | None:
    locs = priority_locations(overlay_key)
    if not locs:
        return None
    return next((x for x in locs if x.edge_id == edge_id), locs[0])


# ---------------------------------------------------------------- chrome

def project_bar(stage: str) -> None:
    """Brand · project · stage tabs (Network / Compare / Deliver) · More — one row, also on phones."""
    cols = st.columns([2.2, 1, 1, 1, 1.1], vertical_alignment="center")
    with cols[0]:
        st.markdown(
            f"<div class='at-tabs' style='display:flex;align-items:center;gap:14px;min-height:48px'>"
            f"<span class='at-brand'>{LOGO}<span class='at-brand-text'>AccessTwin</span></span>"
            f"<span class='at-project'>Demo Township <span class='at-tag'>Study 01</span></span></div>",
            unsafe_allow_html=True)
    for col, (key, page) in zip(cols[1:4], STAGES):
        label = t(f"stage_{key}")
        with col:
            if key == stage:
                st.markdown(f"<div class='at-tab-active' style='min-height:44px;display:flex;align-items:center;justify-content:center;"
                            f"font-weight:600;border-bottom:2px solid #333B30'>{esc(label)}</div>",
                            unsafe_allow_html=True)
            else:
                _page_link(page, label)
    with cols[4]:
        with st.popover(t("more"), use_container_width=False):
            for group, pages in (("res_group", RESIDENT_PAGES), ("staff_group", STAFF_PAGES)):
                st.markdown(f"<div class='at-eyebrow' style='margin:4px 0 0'>{esc(t(group))}</div>",
                            unsafe_allow_html=True)
                for page, key in pages:
                    _page_link(page, t(key))
    st.markdown("<div style='border-bottom:1px solid var(--border-default);margin:0 0 10px'></div>",
                unsafe_allow_html=True)


def _page_link(page: str, label: str) -> None:
    try:
        st.page_link(page, label=label)
    except Exception:  # page registry unavailable when a page runs on its own (tests)
        st.caption(label)


def status_bar(simulated: bool, version: str) -> None:
    mode = ("<span class='at-chip sim'>Simulated</span> scenario values — existing conditions unchanged"
            if simulated else "<span class='at-chip'>Baseline</span> recorded conditions")
    st.markdown(
        f"<div class='at-statusbar'><span><span class='at-chip syn'>Synthetic</span> demo data · {mode}</span>"
        f"<span>Data version {esc(version)}</span><span>{esc(t('planning_aid'))}</span></div>",
        unsafe_allow_html=True)


def score_block(scores, label_state: str, delta: float | None = None, before: float | None = None) -> None:
    """Access Score (higher is better) + per-profile bars, from a ScoreResult."""
    P = load_personas()
    rows = "".join(
        f"<div class='at-prow'><span>{esc(t('p_short_' + k))}</span>"
        f"<span class='at-bar-track'><i style='width:{max(0.0, min(100.0, v)):.0f}%'></i></span>"
        f"<span class='at-num'>{v:.1f}</span></div>" for k, v in scores.persona_index.items() if k in P)
    support = (f"{delta:+.1f} points vs baseline {before:.1f} · simulated" if delta is not None and before is not None
               else f"{delta:+.1f} points · simulated" if delta is not None else t("score_support"))
    st.markdown(
        f"<div class='at-eyebrow' style='display:flex;justify-content:space-between'><span>{esc(t('access_score'))}</span>"
        f"<span>{esc(label_state)}</span></div>"
        f"<div class='at-score'>{scores.index:.1f}<small> /100</small></div>"
        f"<div class='at-sub' style='margin:6px 0 10px'>{esc(support)}</div>"
        f"<div class='at-eyebrow'>{esc(t('by_profile'))}</div>{rows}"
        f"<div class='at-muted' style='font-size:12px;margin-top:8px'>Synthetic inputs · model result</div>",
        unsafe_allow_html=True)


def step_section_svg(curb_cm: float, ramp: bool) -> str:
    """Diagrammatic section of a kerb step (not to scale). Labels come from the recorded value."""
    edge = ("<path d='M40 70 L120 40' stroke='#8E4326' stroke-width='3' fill='none'/>" if ramp
            else "<path d='M40 70 H120 V40' stroke='#394338' stroke-width='2' fill='none'/>")
    return (f"<svg viewBox='0 0 260 96' width='100%' height='96' role='img' "
            f"aria-label='Diagrammatic section of a {curb_cm:g} cm step, not to scale'>"
            f"<path d='M10 70 H40' stroke='#394338' stroke-width='2'/>{edge}"
            f"<path d='M120 40 H250' stroke='#394338' stroke-width='2'/>"
            f"<path d='M120 40 L250 40 L250 70 L120 70 Z' fill='#EEEFE7' opacity='.6'/>"
            f"<line x1='135' y1='42' x2='135' y2='68' stroke='#A63429' stroke-width='1.5'/>"
            f"<text x='142' y='60' font-size='12' fill='#A63429'>{curb_cm * 10:g} mm</text>"
            f"<text x='10' y='90' font-size='12' fill='#586151' letter-spacing='.6'>DIAGRAMMATIC · NOT TO SCALE</text></svg>")


# ---------------------------------------------------------------- compare / deliver snapshot

def _len_txt(m: float | None) -> str:
    if m is None:
        return "—"
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{m:.0f} m"


def compare_rows(overlay_key: str, loc: Location, persona_k: str) -> list[dict]:
    """One aligned table (Assessment | Baseline | Scenario | Change | Source) for the location's upgrade.

    Shared by Compare and Deliver so both always show the same snapshot.
    """
    up = loc.upgrade
    if not up:
        return []
    ids = (up["id"],)
    d, _ = cached.scenario(overlay_key, ids)
    rows = [{"assessment": t("access_score"), "baseline": f"{d.index_before:.1f} /100",
             "scenario": f"{d.index_after:.1f} /100", "change": f"{d.index_delta:+.1f}", "source": "Model · Simulated"}]
    for k in d.persona_before:
        rows.append({"assessment": f"{t('access_score')} — {t('p_short_' + k)}", "baseline": f"{d.persona_before[k]:.1f}",
                     "scenario": f"{d.persona_after[k]:.1f}", "change": f"{d.persona_after[k] - d.persona_before[k]:+.1f}",
                     "source": "Model · Simulated"})
    if loc.origin and loc.dest:
        b = cached.journey(overlay_key, (), loc.origin, loc.dest, persona_k)
        s = cached.journey(overlay_key, ids, loc.origin, loc.dest, persona_k)
        bl = b.length_m if b.reachable else None
        sl = s.length_m if s.reachable else None
        rows.append({"assessment": f"{t('p_short_' + persona_k)} journey distance", "baseline": _len_txt(bl),
                     "scenario": _len_txt(sl), "change": "—" if bl is None or sl is None else f"{sl - bl:+.0f} m",
                     "source": "Routing · Simulated"})
    rows += [
        {"assessment": t("newly_reachable"), "baseline": "—", "scenario": str(len(d.newly_reachable)),
         "change": f"+{len(d.newly_reachable)}", "source": "Model · Simulated"},
        {"assessment": t("est_residents"), "baseline": "—", "scenario": f"{d.beneficiaries:.0f}", "change": "—",
         "source": "Model estimate"},
        {"assessment": "Relative cost tier", "baseline": "—", "scenario": up["cost_tier"].capitalize(), "change": "—",
         "source": "upgrades.json tier"},
        {"assessment": "Delivery status", "baseline": "Existing condition", "scenario": "Proposed · not built",
         "change": "—", "source": "—"},
    ]
    return rows


def rows_table_html(rows: list[dict]) -> str:
    head = "<tr><th>Assessment</th><th>Baseline</th><th>Scenario</th><th>Change</th><th>Source</th></tr>"
    body = "".join(f"<tr><td>{esc(r['assessment'])}</td><td>{esc(r['baseline'])}</td><td class='sc'>{esc(r['scenario'])}</td>"
                   f"<td>{esc(r['change'])}</td><td>{esc(r['source'])}</td></tr>" for r in rows)
    return f"<div class='at-cmp-wrap'><table class='at-cmp'>{head}{body}</table></div>"


def counts_key() -> str:
    return json.dumps(cached.camera_counts(), sort_keys=True)


def reports_key() -> str:
    from accesstwin.core import store

    return json.dumps([[r["id"], r["status"]] for r in store.list_reports()])


def scenario_json(section: dict) -> str:
    return json.dumps(section, ensure_ascii=False, sort_keys=True)



# ---------------------------------------------------------------- review state, evidence, scenario change (X2–X4)

def review_state(edge_id: str) -> tuple[str, str]:
    """(css class, text) for the review chip — separate from the physical fact (X2)."""
    from accesstwin.core import store

    reps = [r for r in store.list_reports() if r["edge_id"] == edge_id]
    if not reps:
        return "unknown", "No report yet"
    approved = [r for r in reps if r["status"] == "approved"]
    if approved:
        r = approved[-1]
        return "verified", f"Obstacle confirmed by {r['reporter_role']} review, {(r.get('decided_at') or '')[:10]}"
    if any(r["status"] == "pending" for r in reps):
        return "pending", "Report pending review"
    return "unknown", "Reports rejected"


def list_label(loc: Location, review: str) -> str:
    """Priority list row (X8): name · ID — barrier · profiles · review state."""
    return f"{loc.label} · {loc.edge_id} — {list_sub(loc, review)}"


def list_sub(loc: Location, review: str) -> str:
    """Second line of a priority row (2A-2): condition · profiles · review state."""
    n = len(loc.affected)
    prof = f"{n} profile{'s' if n != 1 else ''}" if loc.kind != "inspection" else "not assessed"
    rev = {"report pending review": "report pending", "no report yet": ""}.get(review.lower(), review.lower())
    short = "unverified" if loc.short.lower().startswith("unverified") else loc.short
    return " · ".join(x for x in (short, prof, rev) if x)


@st.cache_data(max_entries=64, show_spinner=False)
def photo_b64(path_str: str, mtime: float, side: int = 760) -> str:
    """Downscaled JPEG as base64 for inline evidence images (cached by path + mtime)."""
    import base64
    import io

    from PIL import Image

    with Image.open(path_str) as im:
        im = im.convert("RGB")
        im.thumbnail((side, side))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def edge_evidence(edge_id: str) -> list[dict]:
    """Reports on a segment, newest first, each with its resolved photo path (None when missing)."""
    from accesstwin.core import store

    out = []
    for r in [x for x in store.list_reports() if x["edge_id"] == edge_id][::-1]:
        p = config.resolve_path(r["photo_path"]) if r.get("photo_path") else None
        out.append({**r, "photo": p if p and p.exists() else None})
    return out


@dataclass
class JourneyChange:
    persona: str
    before_m: float | None
    after_m: float | None
    before_ok: bool
    after_ok: bool


def journey_changes(overlay_key: str, loc: Location, upgrade_ids: tuple) -> list[JourneyChange]:
    """Per-profile journey before → after for the location's demo trip (core routing on both graphs)."""
    out = []
    if not (loc.origin and loc.dest):
        return out
    for k in load_personas():
        b = cached.journey(overlay_key, (), loc.origin, loc.dest, k)
        a = cached.journey(overlay_key, upgrade_ids, loc.origin, loc.dest, k)
        out.append(JourneyChange(k, b.length_m if b.reachable else None, a.length_m if a.reachable else None,
                                 b.direct_reachable, a.direct_reachable))
    return out


def evidence_thumbs(edge_id: str, max_bytes: int = 100_000) -> list[dict]:
    """Report photos for the brief as small base64 JPEG thumbnails (X4), newest first."""
    import base64
    import io

    from PIL import Image

    from accesstwin.core import store
    from accesstwin.ui import components as ui

    out = []
    for r in [x for x in store.list_reports() if x["edge_id"] == edge_id][::-1]:
        path = config.resolve_path(r["photo_path"]) if r.get("photo_path") else None
        if not path or not path.exists():
            continue
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((360, 360))
            q, buf = 80, io.BytesIO()
            while True:
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=q)
                if buf.tell() <= max_bytes or q <= 40:
                    break
                q -= 10
        out.append({"b64": base64.b64encode(buf.getvalue()).decode("ascii"),
                    "caption": f"Report #{r['id']} · {r['status']} · {ui.photo_caption(path.name)}"})
    return out
