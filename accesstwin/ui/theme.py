"""V2 design tokens and the shared stylesheet (architectural / urban-planning direction, plan §4.1).

One place for colours, type and spacing. The base colours are mirrored in .streamlit/config.toml.
Selectors are stable data-testid attributes only — never Streamlit's hashed class names.
"""
from __future__ import annotations

TOKENS: dict[str, str] = {
    "surface-page": "#F7F7F2",
    "surface-panel": "#FBFBF8",
    "surface-map": "#E9ECE1",
    "text-primary": "#242824",
    "text-secondary": "#586151",
    "border-default": "#DCDED5",
    "accent": "#B75D37",
    "accent-strong": "#8E4326",
    "surface-selected": "#F0EEE6",
    "route-alternative": "#526E70",
    "state-blocked": "#A63429",
    "state-pending": "#765818",
    "state-verified": "#345F4C",
    "state-unknown": "#687064",
    "network-line": "#A9A595",  # muted warm grey for the base walkway network (map only)
}

FONT_STACK = '"Segoe UI", Arial, "Microsoft YaHei", sans-serif'

# Foreground / background pairs actually used for text, checked by contrast() (see tests + DECISIONS).
TEXT_PAIRS = [
    ("text-primary", "surface-page"), ("text-primary", "surface-panel"), ("text-secondary", "surface-panel"),
    ("text-secondary", "surface-page"), ("accent-strong", "surface-panel"), ("state-blocked", "surface-panel"),
    ("state-pending", "surface-panel"), ("state-verified", "surface-panel"), ("state-unknown", "surface-panel"),
    ("route-alternative", "surface-panel"), ("text-primary", "surface-selected"), ("text-primary", "surface-map"),
]


def _lum(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two hex colours (or token names)."""
    fg, bg = TOKENS.get(fg, fg), TOKENS.get(bg, bg)
    a, b = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def css() -> str:
    t = TOKENS
    root = ";".join(f"--{k}:{v}" for k, v in t.items())
    return f"""
<style>
:root {{{root};--font:{FONT_STACK}}}
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{background:var(--surface-page);color:var(--text-primary);font-family:var(--font)}}
/* Text uses the system stack; Material icon glyphs keep their own font (no raw ligature names). */
[data-testid="stAppViewContainer"] *:not([data-testid="stIconMaterial"]):not([class*="material-symbols"]) {{font-family:var(--font)}}
/* Chrome: our own project bar replaces the default header and page list. */
header[data-testid="stHeader"] {{background:transparent;height:0;min-height:0}}
[data-testid="stSidebarNav"], [data-testid="stSidebarNavSeparator"] {{display:none}}
[data-testid="stToolbar"] {{right:8px}}
.block-container, [data-testid="stMainBlockContainer"] {{padding-top:0.6rem;padding-bottom:72px;max-width:100%}}
[data-testid="stSidebar"] {{background:var(--surface-panel);border-right:1px solid var(--border-default)}}
h1,h2,h3 {{font-weight:500;letter-spacing:-.4px;color:var(--text-primary)}}
h1 {{font-size:1.65rem}} h2 {{font-size:1.35rem}} h3 {{font-size:1.1rem}}
p, li, label, [data-testid="stMarkdownContainer"] {{font-size:15px}}
[data-testid="stCaptionContainer"], .at-muted {{font-size:13px;color:var(--text-secondary)}}
[data-testid="stMetricValue"] {{font-variant-numeric:tabular-nums;font-weight:400}}
/* Controls: 4 px radius, hairline borders, ≥ 44 px targets, visible focus. */
button, [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {{border-radius:4px !important;min-height:44px}}
[data-testid="stBaseButton-primary"] {{background:var(--accent-strong) !important;border-color:var(--accent-strong) !important;color:#fff !important}}
[data-testid="stBaseButton-secondary"] {{background:var(--surface-panel);border:1px solid var(--border-default)}}
a:focus-visible, button:focus-visible, [role="tab"]:focus-visible, input:focus-visible, [tabindex]:focus-visible
  {{outline:2px solid var(--accent-strong) !important;outline-offset:2px}}
[data-testid="stPageLink"] a {{min-height:44px;display:flex;align-items:center;border-radius:4px}}
[data-testid="stVerticalBlockBorderWrapper"] {{border-radius:4px}}
/* Project bar */
.at-bar {{display:flex;align-items:center;gap:18px;border-bottom:1px solid var(--border-default);background:var(--surface-panel);
  padding:10px 4px 10px 4px;margin:0 0 4px 0;min-height:56px;flex-wrap:wrap}}
.at-brand {{display:flex;align-items:center;gap:10px;font-size:19px;font-weight:600;letter-spacing:-.6px;color:var(--text-primary)}}
.at-brand svg {{width:28px;height:28px;fill:none;stroke:#394338;stroke-width:1.3}}
.at-project {{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--text-primary)}}
.at-tag {{font-size:12px;letter-spacing:.8px;color:var(--text-secondary);border:1px solid var(--border-default);padding:3px 6px;text-transform:uppercase}}
.at-chip {{display:inline-block;font-size:12px;letter-spacing:.6px;text-transform:uppercase;padding:3px 8px;border:1px solid var(--border-default);
  border-radius:2px;color:var(--text-secondary);background:var(--surface-panel)}}
.at-chip.sim {{color:var(--accent-strong);border-color:#D6B8A4;background:#F6EEE6}}
.at-chip.syn {{color:var(--state-pending);border-color:#D9CDAF;background:#F6F2E6}}
.at-eyebrow {{font-size:12px;letter-spacing:1.2px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;margin:4px 0 6px}}
/* Panels */
.at-panel {{background:var(--surface-panel);border:1px solid var(--border-default);padding:16px 18px;border-radius:2px}}
.at-issue {{border-left:2px solid transparent;padding:10px 12px;border-bottom:1px solid #EEEEE7}}
.at-issue.sel {{background:var(--surface-selected);border-left-color:var(--accent)}}
.at-issue b {{font-size:15px;font-weight:600}} .at-issue span {{display:block;font-size:13px;color:var(--text-secondary);margin-top:3px}}
.at-score {{font-size:52px;font-weight:300;letter-spacing:-2.5px;font-variant-numeric:tabular-nums;line-height:1}}
.at-score small {{font-size:17px;letter-spacing:0;color:var(--text-secondary)}}
.at-prow {{display:grid;grid-template-columns:104px 1fr 40px;gap:10px;align-items:center;font-size:13px;margin:9px 0}}
.at-bar-track {{height:4px;background:#E6E8DD}} .at-bar-track i {{display:block;height:4px;background:#7E8C6D}}
.at-num {{font-variant-numeric:tabular-nums;text-align:right}}
.at-status {{display:flex;align-items:center;gap:6px;font-size:13px;font-weight:600}}
.at-status.blocked {{color:var(--state-blocked)}} .at-status.pending {{color:var(--state-pending)}}
.at-status.verified {{color:var(--state-verified)}} .at-status.sim {{color:var(--accent-strong)}}
.at-title {{font-size:30px;line-height:1.12;letter-spacing:-1px;font-weight:400;margin:4px 0 6px}}
.at-sub {{font-size:14px;color:var(--text-secondary)}}
.at-section {{border-top:1px solid #E4E5DC;padding:12px 0 6px}}
.at-big {{font-size:24px;font-weight:400;letter-spacing:-.5px;font-variant-numeric:tabular-nums}}
.at-big small {{font-size:13px;color:var(--text-secondary);letter-spacing:0}}
.at-grid2 {{display:grid;grid-template-columns:1fr 1fr;gap:14px}} .at-grid2>div+div {{border-left:1px solid #E2E5D9;padding-left:14px}}
.at-tags span {{display:inline-block;font-size:12px;padding:4px 7px;background:#EEEFE7;color:#4F5A44;border-radius:2px;margin:0 4px 4px 0}}
.at-kv {{display:flex;justify-content:space-between;font-size:13px;color:var(--text-secondary);margin:6px 0}}
.at-statusbar {{display:flex;gap:18px;flex-wrap:wrap;justify-content:space-between;border-top:1px solid var(--border-default);
  background:#F6F7F0;padding:8px 6px;margin-top:10px;font-size:12px;color:var(--text-secondary)}}
table.at-cmp {{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}}
table.at-cmp th {{text-align:left;font-size:12px;letter-spacing:.6px;color:var(--text-secondary);font-weight:600;padding:10px 8px;border-bottom:1px solid #CBD1C0}}
table.at-cmp td {{padding:11px 8px;border-bottom:1px solid #E4E7DB}}
table.at-cmp td.sc {{color:var(--accent-strong);background:#F6F0E6}}
.at-cmp-wrap {{overflow-x:auto;max-width:100%;-webkit-overflow-scrolling:touch}}
.at-h2 {{font-size:24px;font-weight:400;letter-spacing:-.5px;line-height:1.2;margin:2px 0 6px;color:var(--text-primary)}}
.at-mobile-only, .st-key-ws_mobile_action {{display:none}}
/* Secondary navigation links look like outlined buttons (stage tabs in the project bar stay plain). */
[data-testid="stMain"] [data-testid="stPageLink"] a {{border:1px solid var(--border-default);background:var(--surface-panel);padding:0 12px}}
[data-testid="stHorizontalBlock"]:has(.at-tabs) [data-testid="stPageLink"] a {{border:none;background:transparent}}
[data-testid="stHorizontalBlock"]:has(.at-tabs) [data-testid="stColumn"] > div {{justify-content:center}}
[data-testid="stHorizontalBlock"]:has(.at-tabs) [data-testid="stPageLink"] a {{min-height:44px;margin:0;justify-content:center;
  border-bottom:2px solid transparent !important}}
[data-testid="stHorizontalBlock"]:has(.at-tabs) [data-testid="stPopover"] {{display:flex;justify-content:flex-end}}
/* Legacy cards keep working, restyled with hairlines */
.at-card {{border:1px solid var(--border-default);border-radius:2px;padding:14px 16px;background:var(--surface-panel);margin-bottom:10px}}
.at-bad {{border-left:3px solid var(--state-blocked)}} .at-good {{border-left:3px solid var(--state-verified)}}
.at-warn {{border-left:3px solid var(--state-pending)}}
.at-badge {{display:inline-block;padding:2px 10px;border-radius:2px;font-size:12px;font-weight:600}}
/* ≤ 850 px: one column — context → conclusion → action → map → details */
@media (max-width: 850px) {{
  [data-testid="stHorizontalBlock"] {{flex-wrap:wrap}}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{min-width:100% !important;flex:1 1 100% !important}}
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .at-tabs) > [data-testid="stColumn"]
    {{min-width:0 !important;flex:1 1 0 !important}}
  /* phone order: compact summary + action (inside the map column) → map → Inspector details → list */
  [data-testid="stColumn"]:has(.at-ws-map) {{order:-2}}
  [data-testid="stColumn"]:has(.at-ws-inspector) {{order:-1}}
  [data-testid="stColumn"]:has(.at-ws-score) {{order:-3}}
  .at-mobile-only, .st-key-ws_mobile_action {{display:block}}
  .st-key-ws_top_action {{display:none}}
  [data-testid="stColumn"]:has(.at-brand) {{display:none}}
  table.at-cmp {{min-width:620px}}
  .at-title {{font-size:26px}} .at-score {{font-size:44px}}
  .at-bar {{gap:10px}} .at-project, .at-brand-text {{display:none}}
  [data-testid="stPageLink"] a {{justify-content:center;padding:0 2px}} [data-testid="stPageLink"] p {{font-size:13px}}
  [data-testid="stPopover"] button {{padding:0 6px}} [data-testid="stPopover"] button p {{white-space:nowrap;font-size:14px}}
}}
</style>
"""
