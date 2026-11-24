"""LoadLens — Crowdedness-aware journey planner & demand intelligence (Streamlit entrypoint).

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# Ensure the src package is importable when launched via `streamlit run`.
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from src import ui_theme
from src.data_loader import (
    DQ_REPORT_JSON,
    RAW_DIR,
    SAMPLE_CSV,
    SEGMENT_META_JSON,
    SEGMENTS_PARQUET,
    TICKETS_PARQUET,
    TRIP_GRAPH_PARQUET,
    clean_with_report,
    load_raw,
    load_raw_buffer,
)
from src.gtfs import extract_gtfs_zip, gtfs_status
from src.load_engine import compute_segment_loads, load_segments
from src.topology import build_route_topology, load_topology
from app_pages import (
    render_data_quality,
    render_journey_planner,
    render_overview,
    render_route_analytics,
    render_segment_explorer,
)


st.set_page_config(
    page_title="LoadLens — Delhi Bus Demand & Journey Planner",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui_theme.inject_css()

GTFS_DIR = PROJECT_ROOT / "data" / "gtfs"
UPLOADED_GTFS_DIR = PROJECT_ROOT / "data" / "gtfs_uploaded"


@st.cache_data(show_spinner="Processing uploaded ticket dataset...")
def _process_uploaded_bytes(raw_bytes: bytes, filename: str):
    import io
    raw_df = load_raw_buffer(io.BytesIO(raw_bytes), filename)
    tickets, dq = clean_with_report(
        raw_df, source_signature=f"uploaded:{filename}", write_dq=False
    )
    topology = build_route_topology(tickets)
    segments, seg_meta = compute_segment_loads(tickets, topology)
    info = {"mode": "uploaded", "label": f"Uploaded: {filename}"}
    return tickets, segments, topology, dq, seg_meta, info


@st.cache_data(show_spinner="Loading ticket dataset & building route topology...")
def _load_default_dataset(cache_sig: str):
    env_src = os.environ.get("LOADLENS_TICKETS", "").strip()
    if env_src:
        p = Path(env_src)
        if not p.exists():
            raise FileNotFoundError(f"LOADLENS_TICKETS points to missing file: {p}")
        raw_df = load_raw(p)
        tickets, dq = clean_with_report(raw_df, source_signature=str(p), write_dq=False)
        topology = build_route_topology(tickets)
        segments, seg_meta = compute_segment_loads(tickets, topology)
        return tickets, segments, topology, dq, seg_meta, {
            "mode": "env",
            "label": f"Env LOADLENS_TICKETS ({p.name})",
        }

    if (
        TICKETS_PARQUET.exists()
        and SEGMENTS_PARQUET.exists()
        and TRIP_GRAPH_PARQUET.exists()
    ):
        tickets = pd.read_parquet(TICKETS_PARQUET)
        segments = load_segments()
        topology = load_topology()
        dq = json.loads(DQ_REPORT_JSON.read_text(encoding="utf-8")) if DQ_REPORT_JSON.exists() else {}
        seg_meta = json.loads(SEGMENT_META_JSON.read_text(encoding="utf-8")) if SEGMENT_META_JSON.exists() else {}
        return tickets, segments, topology, dq, seg_meta, {
            "mode": "cache",
            "label": "Processed cache (data/cache/)",
        }

    if RAW_DIR.exists():
        for ext in ("*.parquet", "*.pq", "*.csv"):
            matches = sorted(RAW_DIR.glob(ext))
            if matches:
                p = matches[0]
                raw_df = load_raw(p)
                tickets, dq = clean_with_report(raw_df, source_signature=str(p), write_dq=False)
                topology = build_route_topology(tickets)
                segments, seg_meta = compute_segment_loads(tickets, topology)
                return tickets, segments, topology, dq, seg_meta, {
                    "mode": "raw",
                    "label": f"Raw file ({p.name})",
                }

    if SAMPLE_CSV.exists():
        raw_df = load_raw(SAMPLE_CSV)
        tickets, dq = clean_with_report(
            raw_df, source_signature="data_sample/tickets_sample.csv", write_dq=False
        )
        topology = build_route_topology(tickets)
        segments, seg_meta = compute_segment_loads(tickets, topology)
        return tickets, segments, topology, dq, seg_meta, {
            "mode": "sample",
            "label": "Bundled sample (25,000 rows)",
        }

    raise FileNotFoundError(
        "No ticket dataset found. Upload a CSV/Parquet in the sidebar, set "
        "LOADLENS_TICKETS, or provide data_sample/tickets_sample.csv."
    )


def _cache_signature() -> str:
    env_src = os.environ.get("LOADLENS_TICKETS", "").strip()
    parts = [env_src]
    for p in (TICKETS_PARQUET, SEGMENTS_PARQUET, TRIP_GRAPH_PARQUET, SAMPLE_CSV):
        if p.exists():
            stat = p.stat()
            parts.append(f"{p.name}:{stat.st_size}:{int(stat.st_mtime)}")
    return "|".join(parts)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(ui_theme.brand_header(), unsafe_allow_html=True)
    st.markdown('<div class="ll-divider"></div>', unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        ["Overview", "Journey Planner", "Route Analytics", "Segment Explorer", "Data Quality"],
        label_visibility="collapsed",
        key="nav_radio",
    )

    st.markdown('<div class="ll-divider"></div>', unsafe_allow_html=True)
    with st.expander("Data & GTFS Sources", expanded=False):
        uploaded_tickets = st.file_uploader(
            "October ticket CSV / Parquet",
            type=["csv", "parquet", "pq"],
            key="ticket_uploader",
        )
        uploaded_gtfs = st.file_uploader(
            "Optional GTFS feed (.zip)",
            type=["zip"],
            key="gtfs_uploader",
        )

    active_gtfs_dir = GTFS_DIR
    if uploaded_gtfs is not None:
        gtfs_hash = hashlib.md5(uploaded_gtfs.getvalue()).hexdigest()[:10]
        target = UPLOADED_GTFS_DIR / gtfs_hash
        if not (target / "stops.txt").exists():
            extract_gtfs_zip(uploaded_gtfs, target)
        active_gtfs_dir = target

    gtfs_info = gtfs_status(active_gtfs_dir)

    try:
        if uploaded_tickets is not None:
            tickets, segments, topology, dq, seg_meta, ds_info = _process_uploaded_bytes(
                uploaded_tickets.getvalue(), uploaded_tickets.name
            )
        else:
            tickets, segments, topology, dq, seg_meta, ds_info = _load_default_dataset(
                _cache_signature()
            )
    except Exception as exc:
        st.error(f"Dataset load error: {exc}")
        st.stop()

    st.markdown('<div class="ll-divider"></div>', unsafe_allow_html=True)
    st.markdown(ui_theme.muted("Active dataset"), unsafe_allow_html=True)
    st.markdown(f"**{ds_info['label']}**")
    if ds_info["mode"] == "sample":
        st.caption("Upload full October CSV/Parquet above or set `LOADLENS_TICKETS` to switch datasets.")

    unique_routes = dq.get("unique_routes", int(tickets["route"].nunique()) if len(tickets) else 0)
    st.markdown(
        f"<div style='font-size:0.84rem;line-height:1.7;color:{ui_theme.TEXT_SECONDARY};margin-top:0.4rem;'>"
        f"<b>{len(tickets):,}</b> cleaned tickets<br>"
        f"<b>{unique_routes:,}</b> routes · <b>{len(topology):,}</b> chains<br>"
        f"<b>{len(segments):,}</b> segments aggregated<br>"
        f"GTFS: <b>{'Active' if gtfs_info['available'] else 'Not supplied'}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
if page == "Overview":
    render_overview(tickets, segments, topology, dq, ds_info)
elif page == "Journey Planner":
    render_journey_planner(tickets, segments, topology, gtfs_dir=active_gtfs_dir, gtfs_info=gtfs_info)
elif page == "Route Analytics":
    render_route_analytics(tickets, segments, topology)
elif page == "Segment Explorer":
    render_segment_explorer(tickets, segments, topology)
elif page == "Data Quality":
    render_data_quality(tickets, segments, topology, dq, seg_meta)
