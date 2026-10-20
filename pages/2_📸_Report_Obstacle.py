"""Report an obstacle — resident flow (plan §5, Round 2B).

Location (pre-filled from the route or segment) → description + optional photo → Analyse photo only on an explicit
click → editable suggestion (the original AI output is kept) → confirm. Works without a photo and when the AI fails.
Submitting is idempotent (one draft id per report) and returns an unguessable receipt code.
"""
import hashlib
import uuid
from pathlib import Path

import streamlit as st

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import iter_edges, node_name
from accesstwin.core.obstacles import OBSTACLE_TYPES, PERSONA_KEYS, SEVERITIES, analyze_photo
from accesstwin.ui import components as ui
from accesstwin.ui import guide
from accesstwin.ui.i18n import t

SOURCES = ["No photo", "Use a sample photo", "Upload a photo"]


def _draft_id() -> str:
    if "ro_draft" not in st.session_state:
        st.session_state["ro_draft"] = uuid.uuid4().hex
    return st.session_state["ro_draft"]


def _new_report() -> None:
    for k in [k for k in st.session_state if k.startswith(("ro_ai::", "ro_receipt", "ro_desc"))]:
        del st.session_state[k]
    st.session_state.pop("ro_draft", None)


def receipt(r: dict, G) -> None:
    state, nxt = store.report_state(r)
    st.markdown(
        f"<div class='at-route-head'><div class='at-eyebrow'>Receipt</div>"
        f"<div class='at-status verified' style='font-size:20px;font-weight:600'>Report received</div>"
        f"<div class='at-kv'><span>Report code</span><b class='at-mono' style='font-size:16px;color:var(--text-primary)'>"
        f"{ui.esc(r['token'])}</b></div>"
        f"<div class='at-kv'><span>Location</span><span>{ui.esc(r['edge_id'])} · "
        f"{ui.esc(node_name(G, store_edge(G, r['edge_id'])['from']))} → "
        f"{ui.esc(node_name(G, store_edge(G, r['edge_id'])['to']))}</span></div>"
        f"<div class='at-kv'><span>Current state</span><b>{ui.esc(state)}</b></div>"
        f"<div class='at-muted' style='margin-top:6px'>Next step: {ui.esc(nxt)}</div>"
        f"<div class='at-muted'>Keep the code to track this report. This demo keeps reports for this browser session "
        f"only; no processing time is promised.</div></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.page_link("pages/10_Track_Report.py", label="Track this report →")
    with c2:
        ui.page_link("pages/1_🧭_Route_Planner.py", label="Back to my route →")
    c3.button("Report another obstacle", key="ro_another", on_click=_new_report)


def store_edge(G, edge_id: str) -> dict:
    return next((e for e in iter_edges(G) if e["id"] == edge_id), {"from": "", "to": ""})


def main() -> None:
    ui.setup_page(t("report_title"), "📸")
    ui.sidebar()
    G = ui.graph()

    ui.page_head(t("report_title"), eyebrow="Resident · Report an obstacle",
                 sub="Tell us where and what. A photo helps but is optional.")
    guide.panel("pages/2_📸_Report_Obstacle.py")

    done = st.session_state.get("ro_receipt")
    if done:
        r = store.get_report(done)
        if r:
            receipt(r, G)
            ui.disclaimer()
            return

    # ---- 1. location (pre-filled from the route / segment)
    edges = sorted(iter_edges(G), key=lambda e: int(e["id"][1:]) if e["id"][1:].isdigit() else 999)
    edge_ids = [e["id"] for e in edges]
    labels = {e["id"]: f"{e['id']} · {node_name(G, e['from'])} → {node_name(G, e['to'])}" for e in edges}
    default_edge = st.session_state.get("ro_edge", "E7")
    st.markdown("<div class='at-eyebrow' style='margin-top:6px'>1 · Where</div>", unsafe_allow_html=True)
    f1, f2 = st.columns([3, 1])
    edge_id = f1.selectbox("Location (nearest segment)", edge_ids,
                           index=edge_ids.index(default_edge) if default_edge in edge_ids else 0,
                           format_func=lambda i: labels[i], key="ro_edge")
    role = f2.radio("I am a", ["resident", "guard"], key="ro_role", horizontal=True)

    # ---- 2. description + optional photo
    st.markdown("<div class='at-eyebrow' style='margin-top:10px'>2 · What is the problem</div>", unsafe_allow_html=True)
    description = st.text_area("Description", key="ro_desc", max_chars=1000,
                               placeholder="e.g. The kerb at the clinic entrance is too high for my wheelchair.")
    st.caption(t("photo_notice"))
    src = st.radio("Photo (optional)", SOURCES, horizontal=True, key="ro_src")
    image_bytes, filename, mime = None, None, "image/jpeg"
    if src == "Use a sample photo":
        samples = sorted(p.name for p in config.PHOTOS_DIR.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
        credits = ui.photo_credits()
        gallery = [s for s in samples if s in credits] or samples
        cols = st.columns(4)
        for i, name in enumerate(gallery):
            with cols[i % 4]:
                st.image(str(config.PHOTOS_DIR / name), width="stretch")
                st.caption(ui.photo_caption(name))
                if st.button("Use this photo", key=f"ro_pick_{name}", help=f"Select {name}"):
                    st.session_state["ro_sample"] = name
        filename = st.selectbox("Selected sample photo", samples, key="ro_sample")
        image_bytes = (config.PHOTOS_DIR / filename).read_bytes()
        mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
    elif src == "Upload a photo":
        up = st.file_uploader("Photo of the obstacle", type=["png", "jpg", "jpeg", "webp"], key="ro_upload")
        if up is not None:
            image_bytes, filename, mime = up.getvalue(), up.name, up.type or "image/jpeg"
    is_upload = src == "Upload a photo"

    # ---- 3. optional AI suggestion (explicit click only) → editable category
    st.markdown("<div class='at-eyebrow' style='margin-top:10px'>3 · Category</div>", unsafe_allow_html=True)
    original = None
    cache_key = None
    if image_bytes:
        cache_key = f"ro_ai::{hashlib.sha256(image_bytes).hexdigest()}::{filename}"
        col_img, col_ai = st.columns([2, 3])
        col_img.image(image_bytes, caption=filename if is_upload else ui.photo_caption(filename), width="stretch")
        with col_ai:
            if cache_key not in st.session_state:
                st.caption("The photo is not analysed until you press the button. "
                           + ("Real AI (Groq) receives a resized copy." if config.vision_provider() == "groq"
                              else "This demo uses a filename-based demo classifier."))
                if st.button("Analyse photo", key="ro_analyse"):
                    with st.spinner("Analysing photo…"):
                        st.session_state[cache_key] = analyze_photo(image_bytes, filename, mime)
                    st.rerun()
            else:
                original = dict(st.session_state[cache_key])
                source = original.get("source", "mock")
                demo_guess = is_upload and source == "mock"
                badge = (f"Groq · {original.get('model', '')}" if source == "groq" else
                         "could not parse — choose manually" if source == "manual_required" else "Demo classifier (Mock)")
                st.markdown(f"**AI suggestion** · `{badge}`")
                if original.get("notice"):
                    st.warning(original["notice"] + " Your description and photo are kept.")
                if demo_guess:
                    ui.card("Demo classifier", "Real AI analysis (Groq) runs on the hosted version with an API key. "
                            "In this demo your own photo is not analysed — please choose the category below.", "warn")
                else:
                    st.markdown(f"#### Suggested type: {original['obstacle_type'].replace('_', ' ')}")
                    st.markdown(f"Severity **{ui.esc(original.get('severity', '?'))}** · confidence "
                                f"{float(original.get('confidence', 0)):.0%} (not a calibrated accuracy)")
                    st.write("**Visible evidence:** " + (original.get("visible_evidence") or "—"))
                needs = original.get("needs_onsite_measurement") or []
                if needs:
                    st.caption("Needs on-site measurement: " + ", ".join(needs))
                if demo_guess:
                    original = {**original, "obstacle_type": "other", "confidence": 0.0, "affected_personas": []}
    base = original or {"obstacle_type": "other", "severity": "medium", "affected_personas": []}
    kid = (cache_key or "nophoto")[7:19]
    c1, c2, c3 = st.columns(3)
    otype = c1.selectbox("Obstacle type", OBSTACLE_TYPES, key=f"ro_manual_type_{kid}",
                         index=OBSTACLE_TYPES.index(base.get("obstacle_type", "other")),
                         format_func=lambda x: x.replace("_", " "))
    sev = c2.selectbox("Severity", SEVERITIES, key=f"ro_manual_sev_{kid}",
                       index=SEVERITIES.index(base.get("severity", "medium")))
    affected = c3.multiselect("Affected profiles", PERSONA_KEYS, key=f"ro_manual_personas_{kid}",
                              default=base.get("affected_personas", []), format_func=ui.persona_short)
    if original:
        st.caption("Your choice is saved next to the original AI suggestion; the original is never overwritten.")

    # ---- 4. confirm
    st.markdown("<div class='at-eyebrow' style='margin-top:10px'>4 · Confirm</div>", unsafe_allow_html=True)
    st.caption(f"Report for **{labels[edge_id]}** as {role}. AI output is only a suggestion; a reviewer decides.")
    if st.button("Submit report", type="primary", key="ro_submit"):
        photo_path = None
        if image_bytes and is_upload:
            up_dir = store.session_uploads_dir()  # X1: uploads are per session
            up_dir.mkdir(parents=True, exist_ok=True)
            dest = up_dir / f"{hashlib.sha256(image_bytes).hexdigest()[:12]}{Path(filename).suffix.lower()}"
            if not dest.exists():
                dest.write_bytes(image_bytes)
            photo_path = dest.as_posix()
        elif image_bytes:
            photo_path = (config.PHOTOS_DIR / filename).relative_to(config.ROOT).as_posix()
        suggestion = {**(original or {}), "obstacle_type": otype, "severity": sev, "affected_personas": affected,
                      "source": (original or {}).get("source", "manual"), "edited": bool(original) and (
                          otype != original.get("obstacle_type") or sev != original.get("severity")
                          or sorted(affected) != sorted(original.get("affected_personas", [])))}
        if not original:
            suggestion.update({"confidence": 0.0, "visible_evidence": "", "needs_onsite_measurement": []})
        try:
            r = store.submit_report(edge_id, role, description, photo_path, suggestion, original, _draft_id())
        except ValueError as exc:
            st.error(f"{exc} Nothing was submitted; your input is kept.")
        else:
            st.session_state["ro_receipt"] = r["id"]
            st.rerun()

    ui.disclaimer()


ui.run_page(main)
