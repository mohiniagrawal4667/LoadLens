"""Centralised UI theme & mobility-grade HTML components for LoadLens."""
from __future__ import annotations

import html
from typing import Iterable, Tuple

# ---- Brand Palette (Metro & Bus Mobility System) ---------------------------
NAVY_DEEP     = "#0B2638"
NAVY_MID      = "#143A52"
TEAL_PRIMARY  = "#29B6A4"
TEAL_DARK     = "#1E8E80"
TEAL_SOFT     = "#E6F7F5"

BG_CANVAS     = "#F4F7F6"
BG_SURFACE    = "#FFFFFF"
BG_MUTED      = "#EEF3F2"
BORDER_SUBTLE = "#DCE5E3"

TEXT_PRIMARY   = "#0B2638"
TEXT_SECONDARY = "#475569"
TEXT_MUTED     = "#64748B"

# Demand indicators (Teal -> Amber -> Muted Coral)
ACCENT_TEAL   = TEAL_PRIMARY
ACCENT_GREEN  = "#10B981"
ACCENT_AMBER  = "#D97706"
AMBER_SOFT    = "#FEF3C7"
ACCENT_RED    = "#E05A47"   # Muted Coral for high demand
CORAL_SOFT    = "#FDECEA"
ACCENT_BLUE   = "#2563EB"

# Backwards-compatible aliases used by existing imports
BG_DEEP  = BG_CANVAS
BG_PANEL = BG_SURFACE
BG_CARD  = BG_SURFACE
BORDER   = BORDER_SUBTLE

LOAD_SCALE = [
    [0.0, "#D6F3EE"],
    [0.3, "#29B6A4"],
    [0.6, "#F59E0B"],
    [0.85, "#E05A47"],
    [1.0, "#0B2638"],
]

ROUTES_SCALE = [
    "#0B2638", "#29B6A4", "#E05A47", "#D97706",
    "#2563EB", "#0F766E", "#64748B", "#7C3AED",
]


def demand_tier(rel: float) -> Tuple[str, str, str]:
    """Return (label, text/dot color, pill background) for a 0-1 relative load."""
    if rel < 0.40:
        return "Low demand", TEAL_DARK, TEAL_SOFT
    if rel < 0.75:
        return "Moderate demand", ACCENT_AMBER, AMBER_SOFT
    return "High demand", ACCENT_RED, CORAL_SOFT


def inject_css() -> None:
    """Inject light urban-mobility CSS and Inter / DM Sans typography."""
    import streamlit as st

    css_body = f"""@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');
:root {{
    --ll-navy: {NAVY_DEEP};
    --ll-teal: {TEAL_PRIMARY};
    --ll-canvas: {BG_CANVAS};
    --ll-surface: {BG_SURFACE};
    --ll-border: {BORDER_SUBTLE};
    --ll-text: {TEXT_PRIMARY};
    --ll-text-sec: {TEXT_SECONDARY};
    --ll-muted: {TEXT_MUTED};
    --ll-amber: {ACCENT_AMBER};
    --ll-coral: {ACCENT_RED};
}}

/* Global Canvas & Typography */
html, body, .stApp {{
    background-color: var(--ll-canvas) !important;
    color: var(--ll-text) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 15px;
}}

h1, h2, h3, h4 {{
    font-family: 'DM Sans', 'Inter', sans-serif !important;
    color: var(--ll-navy) !important;
    font-weight: 700 !important;
    letter-spacing: -0.015em;
}}
p, li, span, label, td, th {{
    color: var(--ll-text);
}}
.block-container {{
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1320px;
}}

/* Hide noisy Streamlit default chrome while keeping collapse toggle */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{
    background: transparent !important;
}}

/* Sidebar — Clean elevated white mobility rail */
section[data-testid="stSidebar"] {{
    background-color: var(--ll-surface) !important;
    border-right: 1px solid var(--ll-border) !important;
}}
section[data-testid="stSidebar"] > div {{
    padding-top: 1.25rem;
}}

/* Sidebar radio turned into crisp pill navigation */
section[data-testid="stSidebar"] div[role="radiogroup"] {{
    gap: 0.35rem;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 0.55rem 0.85rem !important;
    margin: 0 !important;
    transition: background-color 140ms ease, border-color 140ms ease;
    cursor: pointer;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
    background: {BG_MUTED};
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
    background: {NAVY_DEEP} !important;
    border-color: {NAVY_DEEP} !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p,
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) span {{
    color: #FFFFFF !important;
    font-weight: 600 !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{
    display: none;
}}

/* Inputs & Selectboxes */
.stTextInput input,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div {{
    background-color: #FFFFFF !important;
    color: var(--ll-navy) !important;
    border: 1px solid var(--ll-border) !important;
    border-radius: 10px !important;
    min-height: 42px;
    box-shadow: 0 1px 2px rgba(11, 38, 56, 0.03);
}}
.stTextInput input:focus,
.stSelectbox div[data-baseweb="select"] > div:focus-within {{
    border-color: var(--ll-teal) !important;
    box-shadow: 0 0 0 2px rgba(41, 182, 164, 0.18) !important;
}}

/* Buttons */
.stButton > button {{
    background-color: var(--ll-navy) !important;
    color: #FFFFFF !important;
    border: 1px solid var(--ll-navy) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1rem !important;
    transition: background-color 150ms ease, transform 120ms ease;
}}
.stButton > button:hover {{
    background-color: {NAVY_MID} !important;
    border-color: {NAVY_MID} !important;
}}
.stButton > button[kind="primary"] {{
    background-color: var(--ll-teal) !important;
    border-color: var(--ll-teal) !important;
    color: #07202E !important;
}}
.stButton > button[kind="secondary"] {{
    background-color: #FFFFFF !important;
    color: var(--ll-navy) !important;
    border: 1px solid var(--ll-border) !important;
}}
.stButton > button[kind="secondary"]:hover {{
    background-color: {BG_MUTED} !important;
}}

/* Expanders & DataFrames */
div[data-testid="stExpander"] {{
    background-color: var(--ll-surface) !important;
    border: 1px solid var(--ll-border) !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 4px rgba(11, 38, 56, 0.04);
}}
.stDataFrame {{
    background-color: var(--ll-surface);
    border: 1px solid var(--ll-border);
    border-radius: 12px;
    overflow: hidden;
}}

/* Custom Mobility Components */
.ll-brand {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.25rem 0 0.75rem 0;
}}
.ll-brand-icon {{
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: {NAVY_DEEP};
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}
.ll-brand-title {{
    font-family: 'DM Sans', sans-serif;
    font-size: 1.2rem;
    font-weight: 700;
    color: {NAVY_DEEP};
    line-height: 1.1;
}}
.ll-brand-sub {{
    font-size: 0.78rem;
    color: {TEXT_MUTED};
    margin-top: 0.15rem;
}}
.ll-divider {{
    border-top: 1px solid var(--ll-border);
    margin: 0.85rem 0;
}}
.ll-muted {{
    color: var(--ll-muted) !important;
    font-size: 0.84rem;
    font-weight: 500;
}}
.ll-secondary {{
    color: var(--ll-text-sec) !important;
    font-size: 0.94rem;
}}

/* Hero Banner */
.ll-hero {{
    background: {NAVY_DEEP};
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.15rem;
    box-shadow: 0 6px 20px rgba(11, 38, 56, 0.10);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
}}
.ll-hero h1 {{
    color: #FFFFFF !important;
    margin: 0 0 0.3rem 0 !important;
    font-size: 1.75rem !important;
    line-height: 1.2;
}}
.ll-hero .sub {{
    color: #B9D0DC !important;
    font-size: 0.96rem;
    margin: 0;
}}
.ll-hero-badge {{
    background: rgba(41, 182, 164, 0.18);
    border: 1px solid rgba(41, 182, 164, 0.45);
    color: #7BE3D4 !important;
    padding: 0.4rem 0.8rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
    white-space: nowrap;
}}

/* KPI Strip */
.ll-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
    gap: 0.85rem;
    margin-bottom: 1.2rem;
}}
.ll-kpi {{
    background: var(--ll-surface);
    border: 1px solid var(--ll-border);
    border-top: 3px solid var(--ll-teal);
    border-radius: 14px;
    padding: 0.95rem 1.1rem;
    box-shadow: 0 2px 8px rgba(11, 38, 56, 0.04);
    transition: transform 140ms ease, box-shadow 140ms ease;
}}
.ll-kpi:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(11, 38, 56, 0.07);
}}
.ll-kpi .label {{
    color: var(--ll-muted) !important;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.ll-kpi .value {{
    color: var(--ll-navy) !important;
    font-family: 'DM Sans', sans-serif;
    font-size: 1.6rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1.15;
    margin-top: 0.3rem;
}}
.ll-kpi .delta {{
    color: var(--ll-text-sec) !important;
    font-size: 0.8rem;
    margin-top: 0.25rem;
}}

/* Elevated Card & Notice Banner */
.ll-card {{
    background: var(--ll-surface);
    border: 1px solid var(--ll-border);
    border-radius: 14px;
    padding: 1.15rem 1.25rem;
    margin-bottom: 0.9rem;
    box-shadow: 0 2px 10px rgba(11, 38, 56, 0.04);
}}
.ll-notice {{
    background: #FFFFFF;
    border: 1px solid var(--ll-border);
    border-left: 4px solid {ACCENT_AMBER};
    border-radius: 12px;
    padding: 0.8rem 1.05rem;
    margin-bottom: 1.1rem;
    font-size: 0.9rem;
    color: var(--ll-text-sec);
    box-shadow: 0 1px 4px rgba(11, 38, 56, 0.03);
}}
.ll-notice strong {{
    color: var(--ll-navy);
}}

/* Journey Option Card */
.ll-route-card {{
    background: var(--ll-surface);
    border: 1px solid var(--ll-border);
    border-radius: 16px;
    padding: 1.2rem 1.35rem;
    margin-bottom: 0.5rem;
    box-shadow: 0 3px 12px rgba(11, 38, 56, 0.05);
}}
.ll-route-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 0.9rem;
}}
.ll-route-left {{
    display: flex;
    align-items: center;
    gap: 0.85rem;
    flex-wrap: wrap;
}}
.ll-route-pill {{
    background: {NAVY_DEEP};
    color: #FFFFFF !important;
    font-family: 'DM Sans', sans-serif;
    font-weight: 700;
    font-size: 1rem;
    padding: 0.42rem 0.85rem;
    border-radius: 10px;
    letter-spacing: 0.01em;
}}
.ll-dir-pill {{
    background: {BG_MUTED};
    color: {NAVY_DEEP} !important;
    font-size: 0.76rem;
    font-weight: 700;
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
    text-transform: uppercase;
}}
.ll-demand-pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.35rem 0.8rem;
    border-radius: 999px;
    font-size: 0.84rem;
    font-weight: 600;
}}
.ll-demand-dot {{
    width: 8px;
    height: 8px;
    border-radius: 999px;
    display: inline-block;
}}
.ll-route-od {{
    font-size: 0.96rem;
    font-weight: 600;
    color: {NAVY_DEEP};
    margin-top: 0.35rem;
}}
.ll-route-metrics {{
    display: grid;
    grid-template-columns: repeat(4, minmax(110px, 1fr));
    gap: 0.75rem;
    margin-top: 1rem;
    padding-top: 0.9rem;
    border-top: 1px solid {BORDER_SUBTLE};
}}
.ll-rm-label {{
    font-size: 0.74rem;
    color: {TEXT_MUTED};
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
}}
.ll-rm-val {{
    font-family: 'DM Sans', sans-serif;
    font-size: 1.08rem;
    font-weight: 700;
    color: {NAVY_DEEP};
    font-variant-numeric: tabular-nums;
    margin-top: 0.15rem;
}}

/* Stop-by-stop Metro Timeline */
.ll-timeline {{
    padding: 0.4rem 0.25rem;
}}
.ll-tl-step {{
    display: grid;
    grid-template-columns: 24px 1fr auto;
    gap: 0.75rem;
    align-items: start;
}}
.ll-tl-rail {{
    display: flex;
    flex-direction: column;
    align-items: center;
}}
.ll-tl-dot {{
    width: 12px;
    height: 12px;
    border-radius: 999px;
    border: 3px solid {TEAL_PRIMARY};
    background: #FFFFFF;
    margin-top: 3px;
}}
.ll-tl-dot.origin {{
    border-color: {TEAL_PRIMARY};
    background: {TEAL_PRIMARY};
}}
.ll-tl-dot.dest {{
    border-color: {ACCENT_RED};
    background: {ACCENT_RED};
}}
.ll-tl-line {{
    width: 3px;
    min-height: 28px;
    border-radius: 2px;
    margin: 2px 0;
}}
.ll-tl-stop {{
    font-weight: 600;
    color: {NAVY_DEEP};
    font-size: 0.92rem;
    line-height: 1.3;
}}
.ll-tl-seg {{
    font-size: 0.8rem;
    color: {TEXT_MUTED};
    padding: 0.2rem 0 0.55rem 0;
}}
.ll-tl-badge {{
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}

/* Corridor Strip (Segment Explorer) */
.ll-corridor {{
    display: flex;
    align-items: stretch;
    gap: 0;
    overflow-x: auto;
    padding: 0.75rem 0.25rem 1rem 0.25rem;
}}
.ll-corr-item {{
    display: flex;
    align-items: center;
    flex-shrink: 0;
}}
.ll-corr-stop {{
    background: #FFFFFF;
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 10px;
    padding: 0.45rem 0.7rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: {NAVY_DEEP};
    max-width: 145px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(11, 38, 56, 0.04);
}}
.ll-corr-link {{
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0 0.35rem;
    min-width: 78px;
}}
.ll-corr-bar {{
    width: 100%;
    border-radius: 999px;
    margin: 0.2rem 0;
}}
.ll-corr-vol {{
    font-size: 0.74rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}}

/* Mobile Responsiveness */
@media (max-width: 768px) {{
    .block-container {{
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
        padding-top: 1rem !important;
    }}
    .ll-hero {{
        padding: 1.15rem 1.1rem;
    }}
    .ll-hero h1 {{
        font-size: 1.4rem !important;
    }}
    .ll-route-metrics {{
        grid-template-columns: repeat(2, minmax(100px, 1fr));
    }}
    .ll-kpi-grid {{
        grid-template-columns: repeat(2, minmax(130px, 1fr));
    }}
}}
"""
    compact_css = "\n".join(line for line in css_body.splitlines() if line.strip())
    if hasattr(st, "html"):
        st.html(f"<style>{compact_css}</style>")
    else:
        st.markdown(f"<style>{compact_css}</style>", unsafe_allow_html=True)


def brand_header() -> str:
    """Return crisp SVG + wordmark HTML for the sidebar header."""
    return (
        '<div class="ll-brand">'
        '<div class="ll-brand-icon">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<rect x="4" y="3" width="16" height="14" rx="3" stroke="#29B6A4" stroke-width="2"/>'
        '<path d="M4 11H20" stroke="#29B6A4" stroke-width="2"/>'
        '<circle cx="8" cy="14.5" r="1.2" fill="#FFFFFF"/>'
        '<circle cx="16" cy="14.5" r="1.2" fill="#FFFFFF"/>'
        '<path d="M7 17L5.5 20M17 17L18.5 20" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
        '</div>'
        '<div>'
        '<div class="ll-brand-title">LoadLens</div>'
        '<div class="ll-brand-sub">Delhi Bus Demand &amp; Planner</div>'
        '</div>'
        '</div>'
    )


def hero(title: str, subtitle: str, badge: str | None = None) -> None:
    import streamlit as st
    t = html.escape(title)
    s = html.escape(subtitle)
    badge_html = f'<div class="ll-hero-badge">{html.escape(badge)}</div>' if badge else ""
    st.markdown(
        f'<div class="ll-hero"><div><h1>{t}</h1><p class="sub">{s}</p></div>{badge_html}</div>',
        unsafe_allow_html=True,
    )


def card(content_html: str) -> None:
    import streamlit as st
    st.markdown(f'<div class="ll-card">{content_html}</div>', unsafe_allow_html=True)


def kpi(label: str, value: str, delta: str = "") -> str:
    return (
        '<div class="ll-kpi">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>'
        f'<div class="delta">{html.escape(delta)}</div>'
        '</div>'
    )


def kpi_row(items: Iterable[Tuple[str, str, str]]) -> None:
    import streamlit as st
    tiles = "".join(kpi(label, value, delta) for label, value, delta in items)
    st.markdown(f'<div class="ll-kpi-grid">{tiles}</div>', unsafe_allow_html=True)


def muted(text: str) -> str:
    return f'<span class="ll-muted">{html.escape(text)}</span>'


def limitation_banner(text: str) -> None:
    import streamlit as st
    st.markdown(f'<div class="ll-notice">{text}</div>', unsafe_allow_html=True)


def stop_timeline_html(segments_df, origin: str, destination: str) -> str:
    """Render a vertical Metro-style stop-by-stop timeline from real segment rows."""
    if segments_df is None or len(segments_df) == 0:
        return ""
    parts = ['<div class="ll-timeline">']
    n = len(segments_df)
    for i, row in enumerate(segments_df.itertuples(index=False)):
        rel = float(row.relative_load_index)
        tier_lbl, color, bg = demand_tier(rel)
        vol = int(row.segment_load)
        dot_cls = "origin" if i == 0 else ""
        stop_name = html.escape(str(row.from_norm).title())
        tag = "Boarding stop" if i == 0 else f"Stop {i + 1}"
        parts.append(
            f'<div class="ll-tl-step">'
            f'<div class="ll-tl-rail">'
            f'<div class="ll-tl-dot {dot_cls}"></div>'
            f'<div class="ll-tl-line" style="background:{color};"></div>'
            f'</div>'
            f'<div>'
            f'<div class="ll-tl-stop">{stop_name}</div>'
            f'<div class="ll-tl-seg">{tag} · {vol:,} historical pax on next segment ({tier_lbl.lower()})</div>'
            f'</div>'
            f'<div class="ll-tl-badge" style="color:{color};background:{bg};">RLI {rel:.2f}</div>'
            f'</div>'
        )
        if i == n - 1:
            dest_name = html.escape(str(row.to_norm).title())
            parts.append(
                f'<div class="ll-tl-step">'
                f'<div class="ll-tl-rail"><div class="ll-tl-dot dest"></div></div>'
                f'<div><div class="ll-tl-stop">{dest_name}</div>'
                f'<div class="ll-tl-seg">Destination stop ({n} segments traversed)</div></div>'
                f'<div></div>'
                f'</div>'
            )
    parts.append("</div>")
    return "".join(parts)


def corridor_strip_html(segments_df, max_segments: int = 35) -> str:
    """Render a horizontal stop-to-stop demand corridor for Segment Explorer."""
    if segments_df is None or len(segments_df) == 0:
        return ""
    df_view = segments_df.head(max_segments)
    max_load = max(float(df_view["segment_load"].max()), 1.0)
    parts = ['<div class="ll-corridor">']
    for i, row in enumerate(df_view.itertuples(index=False)):
        rel = float(row.relative_load_index)
        _, color, _ = demand_tier(rel)
        vol = int(row.segment_load)
        thickness = max(4, min(12, int(4 + (vol / max_load) * 8)))
        if i == 0:
            parts.append(
                f'<div class="ll-corr-item"><div class="ll-corr-stop">{html.escape(str(row.from_norm).title())}</div></div>'
            )
        parts.append(
            f'<div class="ll-corr-item">'
            f'<div class="ll-corr-link">'
            f'<div class="ll-corr-vol" style="color:{color};">{vol:,}</div>'
            f'<div class="ll-corr-bar" style="height:{thickness}px;background:{color};"></div>'
            f'</div>'
            f'<div class="ll-corr-stop">{html.escape(str(row.to_norm).title())}</div>'
            f'</div>'
        )
    if len(segments_df) > max_segments:
        parts.append(
            f'<div class="ll-corr-item"><div class="ll-corr-link"><span class="ll-muted">+{len(segments_df) - max_segments} more</span></div></div>'
        )
    parts.append("</div>")
    return "".join(parts)
