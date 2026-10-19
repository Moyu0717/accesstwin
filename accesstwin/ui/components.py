"""Shared Streamlit components: page setup, sidebar persona selector, mock badge, disclaimer."""
from __future__ import annotations

import networkx as nx
import streamlit as st

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import load_graph
from accesstwin.core.personas import Persona, load_personas
from accesstwin.ui.i18n import t

PERSONA_ICONS = {"wheelchair": "♿", "elderly": "🧓", "stroller": "👶", "visually_impaired": "🦯"}
PERSONA_SHORT = {"wheelchair": "Wheelchair", "elderly": "Elderly", "stroller": "Stroller", "visually_impaired": "Low vision"}


def setup_page(title: str, icon: str = "♿") -> None:
    st.set_page_config(page_title=f"{title} · AccessTwin", page_icon=icon, layout="wide")
    store.init_db()
    st.markdown(
        """
        <style>
        .at-card {border:1px solid #D1E7E4; border-radius:12px; padding:14px 16px; background:#F7FBFA; margin-bottom:10px;}
        .at-bad {border-color:#FCA5A5; background:#FEF2F2;}
        .at-good {border-color:#86EFAC; background:#F0FDF4;}
        .at-warn {border-color:#FCD34D; background:#FFFBEB;}
        .at-muted {color:#6B7280; font-size:0.85rem;}
        .at-badge {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem; font-weight:600;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def _personas_cached() -> dict[str, Persona]:
    return load_personas()


def personas() -> dict[str, Persona]:
    return _personas_cached()


def graph() -> nx.MultiGraph:
    """Base JSON + SQLite overlay, reloaded on every rerun so approvals show up immediately."""
    try:
        return load_graph(with_overlay=True)
    except FileNotFoundError as exc:
        st.error(f"Township data not found ({exc.filename}). Run `python -m accesstwin.core.validate` to check data/.")
        st.stop()
    except Exception as exc:  # corrupt JSON / DB
        st.error(f"Could not load the township graph: {exc}. Try **Reset demo data** in the sidebar.")
        st.stop()


def persona_label(key: str) -> str:
    return f"{PERSONA_ICONS.get(key, '')} {personas()[key].label}"


def persona_short(key: str) -> str:
    return f"{PERSONA_ICONS.get(key, '')} {PERSONA_SHORT.get(key, personas()[key].label)}"


def sidebar() -> Persona:
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
        st.caption(t("fictional"))
        st.divider()
        if st.button(t("reset"), help="Clears reports, verifications and work orders, then re-seeds sample reports."):
            store.reset_demo()
            st.success("Demo data reset.")
    return ps[choice]


def disclaimer() -> None:
    st.divider()
    st.caption(f"⚠️ {t('disclaimer')}")
    st.caption(f"🔒 {t('pdpa')}")


def card(title: str, body: str, kind: str = "") -> None:
    st.markdown(
        f"<div class='at-card {('at-' + kind) if kind else ''}'><b>{title}</b><br>{body}</div>",
        unsafe_allow_html=True,
    )


def fmt_m(metres: float) -> str:
    return f"{metres / 1000:.1f} km" if metres >= 1000 else f"{metres:.0f} m"


def page_link(page: str, label: str, icon: str | None = None) -> None:
    """st.page_link that degrades to a caption when the page registry is unavailable (e.g. a page run on its own)."""
    try:
        st.page_link(page, label=label, icon=icon)
    except Exception:  # StreamlitPageNotFoundError
        st.caption(f"{icon or ''} {label} (open it from the sidebar)")
