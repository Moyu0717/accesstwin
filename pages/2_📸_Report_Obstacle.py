import uuid
from pathlib import Path

import streamlit as st

from accesstwin import config
from accesstwin.core import store
from accesstwin.core.graph import iter_edges, node_name
from accesstwin.core.obstacles import OBSTACLE_TYPES, PERSONA_KEYS, SEVERITIES, analyze_photo
from accesstwin.ui import components as ui
from accesstwin.ui.i18n import t


def main() -> None:
    ui.setup_page(t("report_title"), "📸")
    persona = ui.sidebar()
    G = ui.graph()

    st.title(f"📸 {t('report_title')}")
    st.info(f"📷 {t('photo_notice')}")
    st.caption("The AI result is only a **suggestion pending review**. The map changes only after a guard or admin "
               "approves the report in the Verification Queue.")

    src = st.radio("Photo source", ["Upload a photo", "Use a sample photo"], horizontal=True, key="ro_src")
    image_bytes, filename, mime = None, None, "image/png"
    if src == "Upload a photo":
        up = st.file_uploader("Photo of the obstacle", type=["png", "jpg", "jpeg", "webp"], key="ro_upload")
        if up is not None:
            image_bytes, filename, mime = up.getvalue(), up.name, up.type or "image/jpeg"
    else:
        samples = sorted(p.name for p in config.PHOTOS_DIR.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
        if not samples:
            st.warning("No sample photos found in data/photos/.")
        else:
            filename = st.selectbox("Sample photo", samples, key="ro_sample")
            image_bytes = (config.PHOTOS_DIR / filename).read_bytes()
            mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"

    if not image_bytes:
        st.info("Upload or pick a photo to get an AI suggestion.")
        ui.disclaimer()
        st.stop()

    col_img, col_ai = st.columns([2, 3])
    col_img.image(image_bytes, caption=filename, width="stretch")

    cache_key = f"ro_ai::{filename}::{len(image_bytes)}"
    if cache_key not in st.session_state:
        with st.spinner("Analysing photo…"):
            st.session_state[cache_key] = analyze_photo(image_bytes, filename, mime)
    ai = dict(st.session_state[cache_key])

    with col_ai:
        source = ai.get("source", "mock")
        badge = f"AI: Groq · {ai.get('model', '')}" if source == "groq" else (
            "AI: could not parse — choose manually" if source == "manual_required" else "AI: Demo classifier (Mock)")
        st.markdown(f"**AI suggestion** · `{badge}`")
        if ai.get("notice"):
            st.warning(ai["notice"])
        if source == "manual_required":
            ai["obstacle_type"] = st.selectbox("Obstacle type", OBSTACLE_TYPES, index=OBSTACLE_TYPES.index("other"), key="ro_manual_type")
            ai["severity"] = st.selectbox("Severity", SEVERITIES, index=1, key="ro_manual_sev")
            ai["affected_personas"] = st.multiselect("Affected personas", PERSONA_KEYS, key="ro_manual_personas")
        st.markdown(f"#### Suggested type: {ai['obstacle_type'].replace('_', ' ')}")
        b, c = st.columns(2)
        b.metric("Severity", ai["severity"])
        c.metric("Confidence", f"{float(ai.get('confidence', 0)):.0%}")
        st.write("**Affected personas:** " + (", ".join(ui.persona_label(p) for p in ai.get("affected_personas", [])) or "—"))
        st.write("**Visible evidence:** " + (ai.get("visible_evidence") or "—"))
        needs = ai.get("needs_onsite_measurement") or []
        if needs:
            st.warning("📏 Needs on-site measurement: " + ", ".join(needs))

    st.divider()
    edges = sorted(iter_edges(G), key=lambda e: int(e["id"][1:]) if e["id"][1:].isdigit() else 999)
    edge_ids = [e["id"] for e in edges]
    labels = {e["id"]: f"{e['id']} · {node_name(G, e['from'])} ↔ {node_name(G, e['to'])} ({e.get('status')})" for e in edges}
    default_edge = st.session_state.get("ro_edge", "E7")
    f1, f2 = st.columns([3, 1])
    edge_id = f1.selectbox("Nearest segment", edge_ids, index=edge_ids.index(default_edge) if default_edge in edge_ids else 0,
                           format_func=lambda i: labels[i], key="ro_edge")
    role = f2.radio("Reporter role", ["resident", "guard"], key="ro_role")

    if st.button("Submit report", type="primary", key="ro_submit"):
        photo_path = None
        if src == "Upload a photo":
            config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            dest = config.UPLOADS_DIR / f"{uuid.uuid4().hex[:10]}{Path(filename).suffix.lower()}"
            dest.write_bytes(image_bytes)
            photo_path = dest.as_posix()
        else:
            photo_path = (config.PHOTOS_DIR / filename).relative_to(config.ROOT).as_posix()
        rid = store.add_report(edge_id, role, photo_path, ai)
        st.success(f"Report #{rid} submitted for {edge_id} — status **pending**. A guard/admin will review it in the Verification Queue.")
        ui.page_link("pages/3_✅_Verification_Queue.py", label="Open the Verification Queue", icon="✅")

    ui.disclaimer()


ui.run_page(main)
