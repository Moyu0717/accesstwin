"""UI labels in one place: English, Bahasa Malaysia and 中文 (P1-6).

The BM and 中文 strings are MACHINE-DRAFTED and need human proofreading before the pitch (marked "REVIEW").
Any key missing in a language falls back to English, then to the key itself.
"""
from __future__ import annotations

LANG = "en"  # default; the sidebar selector stores the visitor's choice in st.session_state["lang"]
LANGUAGES = {"en": "English", "ms": "Bahasa Malaysia", "zh": "中文"}

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "AccessTwin",
        "tagline": "A township accessibility digital twin — which segment to fix first, at what cost tier, and who gains access.",
        "fictional": "Fictional demo layout (Elmina-style Demo Township). Not a real site.",
        "persona": "Persona",
        "language": "Language",
        "mock_badge": "DEMO MODE — photo AI uses the demo classifier (no API key)",
        "live_badge": "Live AI — Groq vision configured",
        "persona_assumption": "Persona rules are demo assumptions — not a design standard.",
        "disclaimer": (
            "AccessTwin is a planning aid, not proof of compliance with accessibility design standards "
            "(e.g. MS 1184). All routes and upgrades require on-site verification. AI output is a suggestion "
            "pending human review, never a certification."
        ),
        "pdpa": (
            "Privacy (PDPA): CCTV analytics produce aggregate counts only — no frames stored, no face "
            "recognition, no cross-camera tracking. Requires property authorisation before connecting real cameras."
        ),
        "photo_notice": ("Please avoid capturing faces or licence plates. Photos stay in this demo; only when real AI "
                         "is enabled is a resized copy sent to Groq for a suggestion."),
        "onsite": "Requires on-site verification after completion.",
        "unverified_notice": "Grey dashed segments are unverified and excluded from routing by default (pending verification).",
        "reset": "Reset demo data",
        "show_ids": "Show segment IDs on maps",
        "guide_start": "▶ Guided demo (3 min)",
        "legend": (
            "**Segments:** solid blue = verified accessible · solid orange-red with ✖ = blocked · grey dashed = unverified · "
            "thin dotted orange-red = impassable for the selected persona · amber thick = upgraded (simulator). "
            "**Points:** light-blue circles = homes · coloured circles = destinations (hover for the name) · "
            "orange dot = pending report."
        ),
        # navigation + page titles
        "nav_overview": "Overview", "nav_route": "Route Planner", "nav_report": "Report Obstacle",
        "nav_queue": "Verification Queue", "nav_footfall": "Footfall Analytics", "nav_sim": "Upgrade Simulator",
        "nav_dash": "Planner Dashboard", "nav_about": "About",
        "home_title": "Township Overview",
        "route_title": "Route Planner",
        "report_title": "Report an Obstacle",
        "queue_title": "Verification Queue",
        "footfall_title": "Footfall Analytics",
        "sim_title": "Upgrade Simulator",
        "dash_title": "Planner Dashboard",
        "about_title": "About AccessTwin",
        "origin": "Origin (residential)",
        "destination": "Destination",
        "include_unverified": "Include unverified segments (not recommended)",
        # personas
        "p_wheelchair": "Wheelchair user", "p_elderly": "Older adult", "p_stroller": "Parent with stroller",
        "p_visually_impaired": "Low vision",
        "stage_network": "Network",
        "stage_compare": "Compare",
        "stage_deliver": "Deliver",
        "more": "More",
        "planning_aid": "Planning aid, not a safety certification.",
        "access_score": "Access Score",
        "score_support": "Township-wide · higher is better",
        "by_profile": "By journey profile",
        "p_short_wheelchair": "Wheelchair",
        "p_short_elderly": "Older adult",
        "p_short_stroller": "Stroller",
        "p_short_visually_impaired": "Low vision",
        "network_study": "Network study",
        "assessment_title": "Access assessment",
        "assessment_sub": "Everyday journeys. A more connected township.",
        "priority_locations": "Priority locations",
        "location_details": "Location details",
        "existing_condition": "Existing condition",
        "journey_head": "journey",
        "shortest_reference": "Shortest reference path",
        "available_route": "Available route",
        "interrupted": "Currently interrupted",
        "affected_profiles": "Affected profiles",
        "evidence_origin": "Evidence & origin",
        "condition_record": "Condition record",
        "next_action": "Next action",
        "preview_ramp": "Preview ramp",
        "return_baseline": "Return to baseline",
        "sim_only": "Simulation only. Existing conditions stay unchanged.",
        "not_assessed": "Not assessed",
        "needs_inspection": "Needs inspection",
        "confirm_site": "Confirm site conditions",
        "not_estimated": "Not estimated",
        "open_queue": "Open the verification queue",
        "street_map": "Street map",
        "compare_title": "Scenario study",
        "deliver_title": "Study output",
        "newly_reachable": "Newly reachable combinations (modelled)",
        "est_residents": "Estimated residents (model)",
        "priority_score": "Upgrade priority score",
    },
    # REVIEW: machine-drafted Bahasa Malaysia — please proofread.
    "ms": {
        "tagline": "Kembar digital kebolehcapaian perbandaran — segmen mana perlu dibaiki dahulu, pada tahap kos apa, dan siapa yang mendapat akses.",
        "fictional": "Susun atur demo rekaan (Perbandaran Demo gaya Elmina). Bukan tapak sebenar.",
        "persona": "Persona",
        "language": "Bahasa",
        "mock_badge": "MOD DEMO — AI foto menggunakan pengelas demo (tiada kunci API)",
        "live_badge": "AI langsung — penglihatan Groq dikonfigurasi",
        "persona_assumption": "Peraturan persona ialah andaian demo — bukan piawaian reka bentuk.",
        "disclaimer": (
            "AccessTwin ialah alat bantu perancangan, bukan bukti pematuhan piawaian reka bentuk kebolehcapaian "
            "(cth. MS 1184). Semua laluan dan naik taraf memerlukan pengesahan di tapak. Output AI ialah cadangan "
            "yang menunggu semakan manusia, bukan pensijilan."
        ),
        "pdpa": (
            "Privasi (PDPA): analitik CCTV menghasilkan kiraan agregat sahaja — tiada bingkai disimpan, tiada "
            "pengecaman wajah, tiada penjejakan merentas kamera. Kebenaran hartanah diperlukan sebelum menyambung kamera sebenar."
        ),
        "photo_notice": ("Sila elakkan merakam wajah atau nombor plat. Foto kekal dalam demo ini; hanya apabila AI "
                         "sebenar diaktifkan, salinan kecil dihantar ke Groq untuk cadangan."),
        "onsite": "Memerlukan pengesahan di tapak selepas siap.",
        "unverified_notice": "Segmen bergaris putus kelabu belum disahkan dan dikecualikan daripada laluan secara lalai.",
        "reset": "Set semula data demo",
        "show_ids": "Tunjukkan ID segmen pada peta",
        "guide_start": "▶ Demo berpandu (3 min)",
        "legend": (
            "**Segmen:** biru padu = disahkan boleh diakses · jingga-merah padu dengan ✖ = disekat · kelabu putus-putus = belum disahkan · "
            "titik-titik jingga-merah nipis = tidak boleh dilalui untuk persona dipilih · ambar tebal = dinaik taraf. "
            "**Titik:** bulatan biru muda = kediaman · bulatan berwarna = destinasi · titik jingga = laporan menunggu."
        ),
        "nav_overview": "Gambaran Keseluruhan", "nav_route": "Perancang Laluan", "nav_report": "Lapor Halangan",
        "nav_queue": "Barisan Pengesahan", "nav_footfall": "Analitik Pejalan Kaki", "nav_sim": "Simulator Naik Taraf",
        "nav_dash": "Papan Pemuka Perancang", "nav_about": "Perihal",
        "home_title": "Gambaran Keseluruhan Perbandaran",
        "route_title": "Perancang Laluan",
        "report_title": "Lapor Halangan",
        "queue_title": "Barisan Pengesahan",
        "footfall_title": "Analitik Pejalan Kaki",
        "sim_title": "Simulator Naik Taraf",
        "dash_title": "Papan Pemuka Perancang",
        "about_title": "Perihal AccessTwin",
        "origin": "Asal (kediaman)",
        "destination": "Destinasi",
        "include_unverified": "Sertakan segmen belum disahkan (tidak disyorkan)",
        "p_wheelchair": "Pengguna kerusi roda", "p_elderly": "Warga emas", "p_stroller": "Ibu bapa dengan kereta sorong",
        "p_visually_impaired": "Cacat penglihatan",
        "stage_network": "Rangkaian",
        "stage_compare": "Banding",
        "stage_deliver": "Serahan",
        "more": "Lagi",
        "planning_aid": "Alat bantu perancangan, bukan pensijilan keselamatan.",
        "access_score": "Skor Akses",
        "score_support": "Seluruh perbandaran · lebih tinggi lebih baik",
        "by_profile": "Mengikut profil perjalanan",
        "p_short_wheelchair": "Kerusi roda",
        "p_short_elderly": "Warga emas",
        "p_short_stroller": "Kereta sorong",
        "p_short_visually_impaired": "Penglihatan terhad",
        "network_study": "Kajian rangkaian",
        "assessment_title": "Penilaian akses",
        "priority_locations": "Lokasi keutamaan",
        "location_details": "Butiran lokasi",
        "existing_condition": "Keadaan sedia ada",
        "affected_profiles": "Profil terjejas",
        "evidence_origin": "Bukti & asal",
        "next_action": "Tindakan seterusnya",
        "preview_ramp": "Pratonton tanjakan",
        "return_baseline": "Kembali ke garis dasar",
        "sim_only": "Simulasi sahaja. Keadaan sedia ada tidak berubah.",
        "not_assessed": "Belum dinilai",
        "needs_inspection": "Perlu pemeriksaan",
    },
    # REVIEW: machine-drafted 中文 — please proofread.
    "zh": {
        "tagline": "城镇无障碍数字孪生——先修哪一段、属于哪个成本等级、谁能因此到达目的地。",
        "fictional": "虚构的演示布局（Elmina 风格演示城镇），不是真实地点。",
        "persona": "人群",
        "language": "语言",
        "mock_badge": "演示模式——照片 AI 使用演示分类器（无 API key）",
        "live_badge": "真实 AI——已配置 Groq 视觉模型",
        "persona_assumption": "人群规则是演示假设，不是设计标准。",
        "disclaimer": (
            "AccessTwin 是规划辅助工具，不能证明符合无障碍设计标准（如 MS 1184）。所有路线和改造都需要现场核实。"
            "AI 输出只是待人工审核的建议，绝不是认证。"
        ),
        "pdpa": (
            "隐私（PDPA）：CCTV 分析只输出汇总人数——不保存画面、不做人脸识别、不跨摄像头追踪。"
            "接入真实摄像头前需获得物业授权。"
        ),
        "photo_notice": "请避免拍到人脸或车牌。照片只留在本演示中；只有启用真实 AI 时，才会把缩小后的副本发送给 Groq 生成建议。",
        "onsite": "完工后需现场核实。",
        "unverified_notice": "灰色虚线路段尚未核实，默认不参与路线计算（待核实）。",
        "reset": "重置演示数据",
        "show_ids": "在地图上显示路段编号",
        "guide_start": "▶ 引导演示（3 分钟）",
        "legend": (
            "**路段：**蓝色实线 = 已核实可通行 · 橙红实线加 ✖ = 被阻断 · 灰色虚线 = 未核实 · "
            "细橙红点线 = 所选人群无法通行 · 琥珀色粗线 = 已改造（模拟器）。"
            "**点：**浅蓝圆点 = 住宅 · 彩色圆点 = 目的地（悬停查看名称）· 橙色圆点 = 待审核报告。"
        ),
        "nav_overview": "总览", "nav_route": "路线规划", "nav_report": "报告障碍", "nav_queue": "审核队列",
        "nav_footfall": "人流分析", "nav_sim": "改造模拟", "nav_dash": "规划仪表盘", "nav_about": "关于",
        "home_title": "城镇总览",
        "route_title": "路线规划",
        "report_title": "报告障碍",
        "queue_title": "审核队列",
        "footfall_title": "人流分析",
        "sim_title": "改造模拟",
        "dash_title": "规划仪表盘",
        "about_title": "关于 AccessTwin",
        "origin": "起点（住宅）",
        "destination": "目的地",
        "include_unverified": "包含未核实路段（不推荐）",
        "p_wheelchair": "轮椅使用者", "p_elderly": "长者", "p_stroller": "推婴儿车的家长", "p_visually_impaired": "低视力人士",
        "stage_network": "路网",
        "stage_compare": "比较",
        "stage_deliver": "交付",
        "more": "更多",
        "planning_aid": "规划辅助工具，不是安全认证。",
        "access_score": "可达性得分",
        "score_support": "全城镇 · 越高越好",
        "by_profile": "按出行人群",
        "p_short_wheelchair": "轮椅",
        "p_short_elderly": "长者",
        "p_short_stroller": "婴儿车",
        "p_short_visually_impaired": "低视力",
        "network_study": "路网研究",
        "assessment_title": "可达性评估",
        "priority_locations": "优先地点",
        "location_details": "地点详情",
        "existing_condition": "现状条件",
        "affected_profiles": "受影响人群",
        "evidence_origin": "证据与来源",
        "next_action": "下一步",
        "preview_ramp": "预览坡道",
        "return_baseline": "回到基线",
        "sim_only": "仅为模拟，现状不变。",
        "not_assessed": "未评估",
        "needs_inspection": "待现场检查",
    },
}


def current_lang() -> str:
    try:
        import streamlit as st

        lang = st.session_state.get("lang", LANG)
    except Exception:  # outside a Streamlit run
        lang = LANG
    return lang if lang in LABELS else "en"


def t(key: str, lang: str | None = None) -> str:
    lang = lang or current_lang()
    return LABELS.get(lang, {}).get(key) or LABELS["en"].get(key, key)
