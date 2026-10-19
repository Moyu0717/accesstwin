"""All UI labels in one place so Bahasa Malaysia / Chinese can be added later (spec section 6)."""
from __future__ import annotations

LANG = "en"

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "AccessTwin",
        "tagline": "A township accessibility digital twin — which segment to fix first, at what cost tier, and who gains access.",
        "fictional": "Fictional demo layout (Elmina-style Demo Township). Not a real site.",
        "persona": "Persona",
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
        "photo_notice": "Please avoid capturing faces or licence plates. Photos are stored locally only.",
        "onsite": "Requires on-site verification after completion.",
        "unverified_notice": "Grey dashed segments are unverified and excluded from routing by default (pending verification).",
        "reset": "Reset demo data",
        "legend": "Map legend",
        # pages
        "home_title": "Township Overview",
        "route_title": "Route Planner",
        "report_title": "Report an Obstacle",
        "queue_title": "Verification Queue",
        "sim_title": "Upgrade Simulator",
        "origin": "Origin (residential)",
        "destination": "Destination",
        "include_unverified": "Include unverified segments (not recommended)",
    }
}


def t(key: str) -> str:
    return LABELS.get(LANG, LABELS["en"]).get(key, LABELS["en"].get(key, key))
