"""Shared Streamlit components: page setup, sidebar persona selector, mock badge, disclaimer."""
from __future__ import annotations

import json
from typing import Callable

import networkx as nx
import streamlit as st

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import build_graph, load_township
from accesstwin.core.personas import Persona, load_personas
from accesstwin.ui.i18n import LANGUAGES, current_lang, t

PERSONA_ICONS = {"wheelchair": "♿", "elderly": "🧓", "stroller": "👶", "visually_impaired": "🦯"}
# Wide status / barrier columns so labels like "No modelled demand (off-route)" never truncate.
DEMAND_COLUMNS = {
    "status": st.column_config.TextColumn("status", width="large"),
    "barriers on route": st.column_config.TextColumn("barriers on route", width="medium"),
}
PERSONA_SHORT = {"wheelchair": "Wheelchair", "elderly": "Older adult", "stroller": "Stroller", "visually_impaired": "Low vision"}


def setup_page(title: str, icon: str = "♿", page_config_done: bool = False) -> None:
    """Page config (unless the caller already set it to paint something instantly), DB init and CSS."""
    if not page_config_done:
        st.set_page_config(page_title=f"{title} · AccessTwin", page_icon=icon, layout="wide",
                           initial_sidebar_state="collapsed")
    store.init_db()
    from accesstwin.ui import guide  # local import: guide imports this module's siblings only

    guide.apply_pending()
    from accesstwin.ui.theme import css

    st.markdown(css(), unsafe_allow_html=True)


@st.cache_data
def _personas_cached() -> dict[str, Persona]:
    return load_personas()


def personas() -> dict[str, Persona]:
    return _personas_cached()


@st.cache_data
def _township_cached() -> dict:
    return load_township()


def overlay_key() -> str:
    """Hashable fingerprint of the SQLite overlay — the cache key for every overlay-dependent result."""
    return json.dumps(store.get_overlay(), sort_keys=True)


def run_page(body: Callable[[], None]) -> None:
    """Run a page body; any unexpected error is shown on the page instead of leaving it blank."""
    try:
        body()
    except Exception as exc:  # st.stop / st.rerun raise BaseException subclasses, so they pass through untouched
        st.error("Something went wrong on this page. Try **Reset demo data** in the sidebar, or reload.")
        st.exception(exc)


def graph() -> nx.MultiGraph:
    """Cached base JSON + the SQLite overlay, re-applied on every rerun so approvals show up immediately."""
    try:
        return build_graph(_township_cached(), store.get_overlay())
    except FileNotFoundError as exc:
        st.error(f"Township data not found ({exc.filename}). Run `python -m accesstwin.core.validate` to check data/.")
        st.stop()
    except Exception as exc:  # corrupt JSON / DB
        st.error(f"Could not load the township graph: {exc}. Try **Reset demo data** in the sidebar.")
        st.stop()


def persona_label(key: str) -> str:
    return f"{PERSONA_ICONS.get(key, '')} {t('p_' + key) if t('p_' + key) != 'p_' + key else personas()[key].label}"


def persona_short(key: str) -> str:
    """Plain-text short profile name (V2: no emoji in labels)."""
    if current_lang() != "en":
        return t("p_short_" + key)
    return PERSONA_SHORT.get(key, personas()[key].label)


def sidebar(bar: bool = True) -> Persona:
    """Sidebar (language, profile, Reset). `bar` also renders the V2 project bar for pages that don't draw their own."""
    if bar:
        from accesstwin.ui import workspace  # local import: workspace depends on this module's siblings

        workspace.project_bar("")
    ps = personas()
    keys = list(ps)
    with st.sidebar:
        st.markdown(f"### ♿ {t('app_title')}")
        if config.mock_mode():
            st.markdown(
                f"<span class='at-badge' style='background:#FEF3C7;color:#92400E'>{t('mock_badge')}</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<span class='at-badge' style='background:#DCFCE7;color:#166534'>{t('live_badge')}</span>",
                unsafe_allow_html=True,
            )
        st.selectbox(t("language"), list(LANGUAGES), format_func=LANGUAGES.get, key="lang",
                     help="BM and 中文 are machine-drafted and pending human proofreading.")
        current = st.session_state.get("persona", "wheelchair")
        choice = st.selectbox(
            t("persona"), keys, index=keys.index(current) if current in keys else 0,
            format_func=persona_label, key="persona_select",
        )
        st.session_state["persona"] = choice
        st.caption(t("persona_assumption"))
        with st.expander("Persona rules"):
            p = ps[choice]
            st.write(
                {
                    "steps allowed": p.allow_step,
                    "max curb (cm)": p.max_curb_cm,
                    "max slope (%)": p.max_slope_pct,
                    "min width (cm)": p.min_width_cm,
                    "unsuitable surfaces": list(p.bad_surfaces),
                    "max trip (m)": p.max_trip_m,
                    "prefers covered": p.prefers_covered,
                    "needs tactile": p.needs_tactile,
                    "equity weight": p.equity_weight,
                }
            )
        st.toggle(t("show_ids"), key="show_ids", value=st.session_state.get("show_ids", False))
        st.caption(t("fictional"))
        st.divider()
        if st.button(t("reset"), help="Clears reports, verifications and work orders, then re-seeds sample reports."):
            store.reset_demo()
            st.cache_data.clear()
            st.success("Demo data reset.")
    return ps[choice]


def disclaimer() -> None:
    st.divider()
    st.caption(f"⚠️ {t('disclaimer')}")
    st.caption(f"🔒 {t('pdpa')}")


def card(title: str, body: str, kind: str = "") -> None:
    """Card with an escaped title. `body` may contain trusted markup — escape any data/user text with esc()."""
    st.markdown(
        f"<div class='at-card {('at-' + kind) if kind else ''}'><b>{esc(title)}</b><br>{body}</div>",
        unsafe_allow_html=True,
    )


def esc(x) -> str:
    """HTML-escape data or user text before it goes into unsafe_allow_html markup (plan §7.1)."""
    import html

    return html.escape(str(x), quote=True)


def photo_credits() -> dict:
    """data/photos/credits.json (third-party photos: label, source, url), if present."""
    import json

    try:
        with open(config.PHOTOS_DIR / "credits.json", encoding="utf-8") as f:
            return json.load(f).get("photos", {})
    except (OSError, ValueError):
        return {}


def photo_caption(filename: str) -> str:
    """Placeholders say so; third-party photos always carry their source (credits.json)."""
    credit = photo_credits().get(filename)
    if credit:
        return f"{credit['label']} — source: {credit['source']}"
    label = filename.rsplit(".", 1)[0].replace("_", " ")
    return f"Illustration (placeholder): {label}" if is_placeholder_photo(filename) else label


def is_placeholder_photo(filename: str) -> bool:
    from accesstwin.core.obstacles import PLACEHOLDER_PHOTOS

    return filename in PLACEHOLDER_PHOTOS


def fmt_m(metres: float) -> str:
    return f"{metres / 1000:.1f} km" if metres >= 1000 else f"{metres:.0f} m"


def page_link(page: str, label: str, icon: str | None = None) -> None:
    """st.page_link that degrades to a caption when the page registry is unavailable (e.g. a page run on its own)."""
    try:
        st.page_link(page, label=label, icon=icon)
    except Exception:  # StreamlitPageNotFoundError
        st.caption(f"{icon or ''} {label} (open it from the sidebar)")


def bundle_card(b, key_prefix: str = "bundle", allow_apply: bool = False) -> None:
    """Headline "what should we fund first?" card for a simulation.Bundle (P1-2)."""
    if b is None:
        st.info("No low-cost package improves access with the current data.")
        return
    d = b.delta
    with st.container(border=True):
        st.markdown(f"#### 📦 Recommended package: {' + '.join(b.upgrade_ids)}")
        st.caption(f"Greedy by priority score within a budget of {b.budget:g} cost-weight units "
                   f"(low 1 · medium 2.5 · high 5); this package uses {b.cost_weight:g}. Relative tiers only — no RM costs.")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Package: Access Score", f"{d.index_after:.1f}", f"{d.index_delta:+.1f} (from {d.index_before:.1f})")
        m2.metric("Package: newly reachable (modelled)", len(d.newly_reachable), help="Resident–persona–destination trips that become practical")
        m3.metric("Estimated residents (model)", f"{d.beneficiaries:.0f}", help="population × vulnerable share (model estimate)")
        m4.metric("Wheelchair index", f"{d.persona_after.get('wheelchair', 0):.0f}",
                  f"{d.persona_delta().get('wheelchair', 0):+.1f}")
        st.caption("Estimated residents (model) by profile: " + ", ".join(
            f"{persona_short(k)} {v:.0f}" for k, v in d.beneficiaries_by_persona.items()))
        st.markdown(b.explanation)
        st.caption("⚠️ Requires on-site verification after completion. Model estimate on fictional demo data.")
        if allow_apply and st.button("Load this package into the scenario", key=f"{key_prefix}_apply"):
            st.session_state["sim_selected"] = list(b.upgrade_ids)
            st.session_state["sim_multiselect"] = list(b.upgrade_ids)
            st.rerun()
