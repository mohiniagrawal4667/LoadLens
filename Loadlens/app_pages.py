"""Renderers for the five LoadLens pages (Passenger & Operator experiences)."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analytics, ui_theme
from src.gtfs import gtfs_status
from src.journey_planner import (
    search_options_topology,
    search_options_with_gtfs,
    stop_index,
    suggest_stop,
)
from src.ui_theme import (
    ACCENT_AMBER,
    ACCENT_BLUE,
    ACCENT_RED,
    ACCENT_TEAL,
    BORDER_SUBTLE,
    LOAD_SCALE,
    NAVY_DEEP,
    ROUTES_SCALE,
    TEAL_PRIMARY,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

GTFS_DIR = Path(__file__).resolve().parent / "data" / "gtfs"
_GRID_COLOR = "rgba(11, 38, 56, 0.07)"


# ---------------------------------------------------------------------------
# Shared Plotly light-mobility theme
# ---------------------------------------------------------------------------
def _plotly_defaults():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font=dict(color=TEXT_PRIMARY, family="Inter, -apple-system, sans-serif", size=12),
        title_font=dict(color=NAVY_DEEP, family="DM Sans, Inter, sans-serif", size=15),
        margin=dict(l=12, r=12, t=38, b=12),
        colorway=ROUTES_SCALE,
        hoverlabel=dict(bgcolor=NAVY_DEEP, font_color="#FFFFFF", bordercolor=NAVY_DEEP),
    )


def _grid(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(
        gridcolor=_GRID_COLOR,
        linecolor=BORDER_SUBTLE,
        zerolinecolor=_GRID_COLOR,
        tickfont=dict(color=TEXT_SECONDARY),
        title_font=dict(color=TEXT_SECONDARY),
    )
    fig.update_yaxes(
        gridcolor=_GRID_COLOR,
        linecolor=BORDER_SUBTLE,
        zerolinecolor=_GRID_COLOR,
        tickfont=dict(color=TEXT_SECONDARY),
        title_font=dict(color=TEXT_SECONDARY),
    )
    return fig


def _hour_chart(tickets: pd.DataFrame, title: str, highlight_peak: bool = False) -> go.Figure:
    if tickets is None or len(tickets) == 0:
        counts = pd.Series(0, index=range(24))
    else:
        h = tickets["ticket_hour"].astype(int)
        counts = tickets.groupby(h)["passenger_count"].sum().reindex(range(24), fill_value=0)

    if highlight_peak:
        colors = [
            ACCENT_AMBER if (8 <= hr <= 11 or 17 <= hr <= 21) else TEAL_PRIMARY
            for hr in counts.index
        ]
    else:
        colors = TEAL_PRIMARY

    fig = go.Figure(
        go.Bar(
            x=list(counts.index),
            y=list(counts.values),
            marker_color=colors,
            hovertemplate="Hour %{x:02d}:00 IST<br>Passengers: %{y:,}<extra></extra>",
        )
    )
    fig.update_layout(
        **_plotly_defaults(),
        title=title,
        xaxis_title="Hour of day (IST)",
        yaxis_title="Passenger volume",
    )
    return fig


def _nav_to(page_name: str) -> None:
    st.session_state["nav_radio"] = page_name


def _quick_plan_callback() -> None:
    o_val = st.session_state.get("ov_from", "")
    d_val = st.session_state.get("ov_to", "")
    if o_val:
        st.session_state["jp_query_o"] = o_val
    if d_val:
        st.session_state["jp_query_d"] = d_val
    st.session_state["nav_radio"] = "Journey Planner"


def _swap_jp_queries() -> None:
    qo = st.session_state.get("jp_query_o", "")
    qd = st.session_state.get("jp_query_d", "")
    st.session_state["jp_query_o"] = qd
    st.session_state["jp_query_d"] = qo


# ---------------------------------------------------------------------------
# 1. Overview / Home
# ---------------------------------------------------------------------------
def render_overview(tickets, segments, topology, dq, ds_info=None):
    badge = ds_info["label"] if ds_info else "October 2026 Dataset"
    ui_theme.hero(
        "LoadLens Mobility Intelligence",
        "Crowdedness-aware bus journey planner and historical segment demand analytics for Delhi",
        badge=badge,
    )

    ui_theme.limitation_banner(
        "<strong>Data transparency:</strong> Displayed figures represent "
        "<strong>historical ticket-derived passenger demand</strong> from October 2026 ONDC "
        "e-ticketing records (IST). Live bus occupancy, seat availability, and per-vehicle "
        "loads are never fabricated."
    )

    pq = analytics.peak_vs_offpeak(tickets)
    cov = analytics.coverage_summary(tickets, segments, topology)
    unique_routes = dq.get(
        "unique_routes",
        int(tickets["route"].nunique()) if len(tickets) else 0,
    )

    kpis = [
        ("Cleaned Tickets", f"{len(tickets):,}", f"of {dq.get('raw_rows', len(tickets)):,} raw rows"),
        ("Active Routes", f"{unique_routes:,}", f"{len(topology):,} directional chains"),
        ("Segments Mapped", f"{len(segments):,}", "consecutive stop pairs"),
        ("Vehicle ID Coverage", f"{cov['tickets_with_vehicle_pct']:.1f}%",
         f"{cov['distinct_vehicles']:,} distinct vehicles"),
        ("Peak Window Share", f"{pq['peak_share_pct']:.1f}%", pq["peak_window_label"]),
    ]
    ui_theme.kpi_row(kpis)

    # Embedded Quick Journey Search Card (Metro & Bus UI inspired)
    idx = stop_index(tickets)
    st.markdown("#### Quick journey search")
    with st.container():
        st.markdown(
            f'<div class="ll-card" style="padding:1rem 1.2rem 0.6rem 1.2rem;">'
            f'<div style="font-size:0.86rem;font-weight:600;color:{NAVY_DEEP};margin-bottom:0.35rem;">'
            f'Plan a bus trip using historical segment demand</div></div>',
            unsafe_allow_html=True,
        )
        stop_opts = idx["stop_norm"].tolist()[:150] if len(idx) else []
        def_o = stop_opts[0] if len(stop_opts) > 0 else ""
        def_d = stop_opts[1] if len(stop_opts) > 1 else ""
        qc1, qc2, qc3 = st.columns([5, 5, 2])
        with qc1:
            st.selectbox(
                "From stop",
                options=stop_opts,
                index=0 if def_o else None,
                format_func=lambda s: s.title() if s else "",
                key="ov_from",
            )
        with qc2:
            st.selectbox(
                "To stop",
                options=stop_opts,
                index=1 if len(stop_opts) > 1 else 0,
                format_func=lambda s: s.title() if s else "",
                key="ov_to",
            )
        with qc3:
            st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
            st.button(
                "Find Routes →",
                type="primary",
                use_container_width=True,
                on_click=_quick_plan_callback,
                key="ov_go_jp",
            )

    # Main 2-column overview charts & shortcuts
    c_left, c_right = st.columns([3, 2])
    with c_left:
        st.markdown("#### Peak-hour demand profile (IST)")
        fig = _grid(_hour_chart(tickets, "Hourly passenger volume (amber = peak 08–11 & 17–21 IST)", highlight_peak=True))
        fig.update_layout(height=360)
        st.plotly_chart(fig, width="stretch")

    with c_right:
        st.markdown("#### Route demand overview (Top 8)")
        ranking = analytics.route_demand_ranking(tickets)
        if len(ranking) > 0:
            top8 = ranking.head(8).copy()
            top8["label"] = top8["route"] + " (" + top8["direction"] + ")"
            fig_r = px.bar(
                top8.sort_values("passenger_volume"),
                x="passenger_volume",
                y="label",
                orientation="h",
                color="direction",
                color_discrete_map={"up": TEAL_PRIMARY, "down": NAVY_DEEP, "unknown": TEXT_MUTED},
                labels={"passenger_volume": "Passengers", "label": ""},
            )
            fig_r.update_layout(**_plotly_defaults(), height=360, showlegend=True, legend_title_text="Dir")
            st.plotly_chart(_grid(fig_r), width="stretch")
        else:
            st.info("No route volume data available.")

    # High-demand segment highlights + quick shortcuts
    col_hl, col_sc = st.columns([3, 2])
    with col_hl:
        st.markdown("#### High-demand segment highlights")
        top_seg = analytics.top_segments(segments, n=5)
        if len(top_seg) == 0:
            st.info("No segments aggregated yet.")
        else:
            cards_html = []
            for row in top_seg.itertuples(index=False):
                rel = float(row.relative_load_index)
                lbl, col, bg = ui_theme.demand_tier(rel)
                cards_html.append(
                    f'<div class="ll-card" style="padding:0.75rem 1rem;margin-bottom:0.55rem;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:0.75rem;flex-wrap:wrap;">'
                    f'<div><span class="ll-route-pill" style="font-size:0.82rem;padding:0.25rem 0.55rem;">{html.escape(str(row.route))}</span> '
                    f'<span style="font-weight:600;color:{NAVY_DEEP};margin-left:0.4rem;">{html.escape(str(row.segment_label))}</span></div>'
                    f'<div style="display:flex;align-items:center;gap:0.6rem;">'
                    f'<span style="font-weight:700;color:{NAVY_DEEP};font-variant-numeric:tabular-nums;">{int(row.segment_load):,} pax</span>'
                    f'<span class="ll-demand-pill" style="color:{col};background:{bg};padding:0.2rem 0.6rem;font-size:0.76rem;">'
                    f'<span class="ll-demand-dot" style="background:{col};"></span>{lbl}</span>'
                    f'</div></div></div>'
                )
            st.markdown("".join(cards_html), unsafe_allow_html=True)

    with col_sc:
        st.markdown("#### Workspace shortcuts")
        ui_theme.card(
            f"<div style='font-size:0.9rem;color:{TEXT_SECONDARY};margin-bottom:0.3rem;'>"
            "Jump directly into commuter trip comparison or operator diagnostics:</div>"
        )
        b1, b2 = st.columns(2)
        b1.button("Journey Planner", use_container_width=True, on_click=_nav_to, args=("Journey Planner",), key="sc_jp")
        b2.button("Segment Explorer", use_container_width=True, on_click=_nav_to, args=("Segment Explorer",), key="sc_se")
        b3, b4 = st.columns(2)
        b3.button("Route Analytics", use_container_width=True, on_click=_nav_to, args=("Route Analytics",), key="sc_ra")
        b4.button("Data Quality", use_container_width=True, on_click=_nav_to, args=("Data Quality",), key="sc_dq")


# ---------------------------------------------------------------------------
# 2. Journey Planner (Flagship Commuter Screen)
# ---------------------------------------------------------------------------
def render_journey_planner(
    tickets,
    segments,
    topology,
    *,
    gtfs_dir: Path = GTFS_DIR,
    gtfs_info: Optional[Dict] = None,
):
    status = gtfs_info if gtfs_info is not None else gtfs_status(gtfs_dir)
    use_gtfs = bool(status["available"])

    ui_theme.hero(
        "Journey Planner",
        "Compare direct bus routes by historical segment demand and stop-by-stop load",
        badge="GTFS Schedule Active" if use_gtfs else "Ticket-Derived Topology",
    )

    if use_gtfs:
        st.success(
            f"Official GTFS dataset active ({gtfs_dir.name}). Scheduled durations are computed "
            "from `stop_times.txt` and paired with historical ticket segment demand."
        )
    else:
        missing_list = ", ".join(status.get("missing_files", []))
        detail = f"Missing {missing_list}" if missing_list else (status.get("error") or "No GTFS directory")
        ui_theme.limitation_banner(
            f"<strong>Schedule &amp; map notice:</strong> GTFS files unavailable ({html.escape(detail)}). "
            "Showing direct routes from ticket-derived stop topology with <strong>relative passenger demand</strong>. "
            "Scheduled travel durations, geographic route maps, and multi-leg transfers are disabled rather than fabricated."
        )

    idx = stop_index(tickets)
    if len(idx) < 2:
        st.warning("At least two distinct stops in the dataset are required to plan journeys.")
        return

    default_origin = idx["stop_norm"].iloc[0]
    dest_pool = idx[idx["stop_norm"] != default_origin]
    default_destination = dest_pool["stop_norm"].iloc[0]

    # Search Card
    st.markdown(
        f'<div class="ll-card" style="padding:0.9rem 1.2rem 0.5rem 1.2rem;margin-bottom:0.7rem;">'
        f'<div style="font-size:0.84rem;font-weight:700;color:{NAVY_DEEP};text-transform:uppercase;letter-spacing:0.04em;">'
        f'Route Search · From &amp; To Stops</div></div>',
        unsafe_allow_html=True,
    )

    c1, c_swap, c2, c3 = st.columns([5, 1, 5, 2])
    with c1:
        query_o = st.text_input("From (search boarding stop)", value="", placeholder="e.g. Badarpur Border", key="jp_query_o")
        suggestions_o = suggest_stop(query_o, idx, k=8)
        if query_o.strip() and len(suggestions_o) == 0:
            st.warning(f"No stops matched origin query: '{query_o.strip()}'")
            choice_o = None
        else:
            opts_o = suggestions_o["stop_norm"].tolist()
            default_idx_o = opts_o.index(default_origin) if (not query_o.strip() and default_origin in opts_o) else 0
            choice_o = st.selectbox(
                "Boarding stop",
                options=opts_o,
                index=default_idx_o,
                format_func=lambda n: n.title() if n else "",
                key="origin_choice",
            )

    with c_swap:
        st.markdown("<div style='height:1.75rem;'></div>", unsafe_allow_html=True)
        st.button("⇄", help="Swap origin and destination searches", on_click=_swap_jp_queries, use_container_width=True, key="jp_swap")

    with c2:
        query_d = st.text_input("To (search destination stop)", value="", placeholder="e.g. Kalkaji Mandir", key="jp_query_d")
        suggestions_d = suggest_stop(query_d, idx, k=8)
        if query_d.strip() and len(suggestions_d) == 0:
            st.warning(f"No stops matched destination query: '{query_d.strip()}'")
            choice_d = None
        else:
            opts_d = suggestions_d["stop_norm"].tolist()
            if choice_o and choice_o in opts_d and len(opts_d) > 1:
                opts_d = [s for s in opts_d if s != choice_o]
            default_idx_d = (
                opts_d.index(default_destination)
                if (not query_d.strip() and default_destination in opts_d)
                else 0
            )
            choice_d = st.selectbox(
                "Destination stop",
                options=opts_d,
                index=default_idx_d,
                format_func=lambda n: n.title() if n else "",
                key="destination_choice",
            )

    with c3:
        max_opts = st.slider("Max options", 1, 10, 5)

    if not choice_o or not choice_d:
        st.info("Select matching boarding and destination stops above to compare routes.")
        return

    if choice_o == choice_d:
        st.warning("Origin and destination are the same stop. Choose two distinct stops.")
        return

    if use_gtfs:
        result = search_options_with_gtfs(
            gtfs_dir, segments, choice_o, choice_d, max_options=max_opts
        )
    else:
        result = search_options_topology(
            tickets, segments, choice_o, choice_d, topology=topology, max_options=max_opts
        )

    if not result["options"]:
        st.info(result["message"])
        return

    opts = result["options"]
    best_rli = min(o["relative_load_index"] for o in opts)
    min_segs = min(o["segment_count"] for o in opts)
    dur_vals = [o["estimated_duration_min"] for o in opts if o.get("estimated_duration_min") is not None]
    dur_summary = f"{min(dur_vals):.1f} min min" if dur_vals else "Requires GTFS"

    ui_theme.kpi_row([
        ("Direct Options", str(len(opts)), f"{choice_o.title()} → {choice_d.title()}"),
        ("Lowest Relative Load", f"{best_rli:.2f}", ui_theme.demand_tier(best_rli)[0]),
        ("Fewest Segments", f"{min_segs}", "shortest stop span"),
        ("Travel Duration", dur_summary, "GTFS stop_times.txt" if dur_vals else "Disabled without GTFS"),
    ])

    st.markdown("### Recommended direct routes (sorted by lowest historical load)")
    for idx_, opt in enumerate(opts, start=1):
        _render_option_card(idx_, opt)


def _render_option_card(rank: int, opt: dict):
    rel = float(opt["relative_load_index"])
    tier_lbl, color, bg = ui_theme.demand_tier(rel)
    seg = opt["segments"]
    seg_cnt = int(opt["segment_count"])
    cum_load = float(opt["historical_segment_load"])
    avg_seg_load = cum_load / max(seg_cnt, 1)
    dur = opt.get("estimated_duration_min")
    dur_str = f"{dur:.1f} min" if dur is not None else "Unavailable"

    r_tickets = opt.get("route_tickets")
    r_veh_pct = opt.get("route_vehicle_coverage_pct")
    conf_parts = [f"Mean Relative Load Index across {seg_cnt} traversed segment(s) on {opt['route']} ({opt['direction']})"]
    if r_tickets is not None:
        conf_parts.append(f"backed by {r_tickets:,} ticket records on this route chain")
    if r_veh_pct is not None:
        conf_parts.append(f"{r_veh_pct:.1f}% vehicle ID coverage")
    conf_text = "; ".join(conf_parts) + "."

    st.markdown(
        f'<div class="ll-route-card" style="border-left: 4px solid {color};">'
        f'<div class="ll-route-head">'
        f'<div class="ll-route-left">'
        f'<span class="ll-route-pill">#{rank} · {html.escape(str(opt["route"]))}</span>'
        f'<span class="ll-dir-pill">{html.escape(str(opt["direction"]))}</span>'
        f'<div><div class="ll-route-od">{html.escape(str(opt["origin"]).title())} → {html.escape(str(opt["destination"]).title())}</div></div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<span class="ll-demand-pill" style="color:{color};background:{bg};">'
        f'<span class="ll-demand-dot" style="background:{color};"></span>{tier_lbl} · RLI {rel:.2f}</span>'
        f'</div>'
        f'</div>'
        f'<div class="ll-route-metrics">'
        f'<div><div class="ll-rm-label">Estimated Duration</div><div class="ll-rm-val">{html.escape(dur_str)}</div></div>'
        f'<div><div class="ll-rm-label">Segments Crossed</div><div class="ll-rm-val">{seg_cnt} stops</div></div>'
        f'<div><div class="ll-rm-label">Avg Segment Demand</div><div class="ll-rm-val">{avg_seg_load:,.0f} pax</div></div>'
        f'<div><div class="ll-rm-label">Cumulative Pax-Segs</div><div class="ll-rm-val">{cum_load:,.0f}</div></div>'
        f'</div>'
        f'<div style="margin-top:0.75rem;font-size:0.82rem;color:{TEXT_MUTED};">'
        f'<strong>How estimated:</strong> {html.escape(conf_text)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.expander(f"Stop-by-stop timeline, segment demand & map · Route {opt['route']}", expanded=(rank == 1)):
        tab_tl, tab_chart, tab_map = st.tabs(["Stop-by-Stop Timeline", "Segment Load Breakdown", "Route Map / Geometry"])
        with tab_tl:
            st.markdown(
                ui_theme.stop_timeline_html(seg, opt["origin"], opt["destination"]),
                unsafe_allow_html=True,
            )
        with tab_chart:
            fig = px.bar(
                seg,
                x="from_norm",
                y="segment_load",
                color="relative_load_index",
                color_continuous_scale=LOAD_SCALE,
                range_color=[0, 1],
                labels={"from_norm": "Boarding / Segment Start", "segment_load": "Historical pax volume", "relative_load_index": "RLI"},
                title=f"Segment demand along Route {opt['route']}",
            )
            fig.update_layout(**_plotly_defaults(), height=300)
            st.plotly_chart(_grid(fig), width="stretch")

            cols_to_show = {
                "From Stop": seg["from_norm"].astype(str).str.title(),
                "To Stop": seg["to_norm"].astype(str).str.title(),
                "Passenger Volume": seg["segment_load"].astype(int),
                "Relative Load Index": seg["relative_load_index"].round(3),
            }
            if "ticket_count" in seg.columns:
                cols_to_show["Tickets"] = seg["ticket_count"].astype(int)
            st.dataframe(pd.DataFrame(cols_to_show), width="stretch", hide_index=True)

        with tab_map:
            coords = opt.get("stop_coords")
            if coords and len(coords) >= 2:
                cdf = pd.DataFrame(coords)
                fig_map = px.line_map(
                    cdf,
                    lat="lat",
                    lon="lon",
                    hover_name="stop",
                    zoom=11,
                    height=340,
                )
                fig_map.update_traces(line=dict(width=4, color=NAVY_DEEP))
                fig_map.add_trace(
                    go.Scattermap(
                        lat=cdf["lat"],
                        lon=cdf["lon"],
                        mode="markers",
                        marker=dict(size=9, color=TEAL_PRIMARY),
                        text=cdf["stop"].str.title(),
                        hoverinfo="text",
                        name="Stops",
                    )
                )
                fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_map, width="stretch")
            else:
                st.info(
                    "Geographic route map is unavailable because the active dataset does not include "
                    "stop coordinates (`stop_lat`, `stop_lon` in GTFS `stops.txt`). LoadLens never draws "
                    "synthetic geographic coordinates — inspect the Stop-by-Stop Timeline tab for exact topology."
                )


# ---------------------------------------------------------------------------
# 3. Route Analytics (Operator Intelligence)
# ---------------------------------------------------------------------------
def render_route_analytics(tickets, segments, topology):
    ui_theme.hero(
        "Route Analytics",
        "Operator view of aggregate passenger demand, peak windows, and weekday vs. weekend profiles",
        badge="Operator Intelligence",
    )

    if tickets is None or len(tickets) == 0:
        st.warning("No cleaned ticket rows available for the current dataset.")
        return

    ranking_all = analytics.route_demand_ranking(tickets)
    if len(ranking_all) == 0:
        st.warning("No route records available.")
        return

    # Filter Bar
    fc1, fc2, fc3 = st.columns([3, 2, 3])
    with fc1:
        route_filter = st.text_input("Filter routes by number / label", value="", placeholder="e.g. 717 or 543", key="ra_filter")
    with fc2:
        dir_options = ["All"] + sorted(ranking_all["direction"].unique().tolist())
        dir_filter = st.selectbox("Direction filter", dir_options, key="ra_dir")
    ranking = ranking_all.copy()
    if dir_filter != "All":
        ranking = ranking[ranking["direction"] == dir_filter]
    if route_filter.strip():
        q = route_filter.strip().upper()
        ranking = ranking[ranking["route"].str.upper().str.contains(q, regex=False)]

    if len(ranking) == 0:
        st.info("No routes match the active filters. Clear the route or direction filter above.")
        return

    with fc3:
        max_slider = min(len(ranking), 100)
        if max_slider <= 5:
            top_n = max_slider
            st.caption(f"Showing all {max_slider} matching route(s)")
        else:
            top_n = st.slider("Top N routes displayed", 5, max_slider, min(20, max_slider))

    filtered_tickets = tickets[tickets["route"].isin(ranking["route"])]
    if dir_filter != "All":
        filtered_tickets = filtered_tickets[filtered_tickets["direction"] == dir_filter]

    pq = analytics.peak_vs_offpeak(filtered_tickets)
    ui_theme.kpi_row([
        ("Matching Routes", f"{len(ranking):,}", "route+direction combinations"),
        ("Filtered Passengers", f"{int(filtered_tickets['passenger_count'].sum()):,}", f"{len(filtered_tickets):,} tickets"),
        ("Peak Share", f"{pq['peak_share_pct']:.1f}%", pq["peak_window_label"]),
        ("Top Route Volume", f"{int(ranking['passenger_volume'].iloc[0]):,}",
         f"{ranking['route'].iloc[0]} ({ranking['direction'].iloc[0]})"),
    ])

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("#### Route-wise passenger volume")
        top = ranking.head(top_n).copy()
        top["label"] = top["route"] + " · " + top["direction"]
        top["veh_cov_pct"] = (top["vehicle_coverage"] * 100).round(1)
        fig = px.bar(
            top.sort_values("passenger_volume"),
            x="passenger_volume",
            y="label",
            orientation="h",
            color="direction",
            hover_data={"ticket_count": ":,", "avg_passenger_count": ":.2f", "veh_cov_pct": ":.1f", "label": False},
            color_discrete_map={"up": TEAL_PRIMARY, "down": NAVY_DEEP, "unknown": TEXT_MUTED},
            labels={"passenger_volume": "Passenger volume", "label": "Route · Direction", "veh_cov_pct": "Vehicle ID %"},
        )
        fig.update_layout(**_plotly_defaults(), height=540)
        st.plotly_chart(_grid(fig), width="stretch")

    with c2:
        st.markdown("#### Peak vs. Off-peak split")
        fig_pk = go.Figure(
            go.Pie(
                labels=["Peak (08–11, 17–21 IST)", "Off-peak"],
                values=[pq["peak_passenger_volume"], pq["offpeak_passenger_volume"]],
                hole=0.62,
                marker=dict(colors=[ACCENT_AMBER, TEAL_PRIMARY]),
                textinfo="label+percent",
                textfont=dict(color=TEXT_PRIMARY),
            )
        )
        fig_pk.update_layout(
            **_plotly_defaults(),
            height=260,
            showlegend=False,
            annotations=[dict(
                text=f"<b>{pq['peak_share_pct']:.1f}%</b><br>Peak",
                x=0.5, y=0.5, font_size=14, font_color=NAVY_DEEP, showarrow=False,
            )],
        )
        st.plotly_chart(fig_pk, width="stretch")

        st.markdown("#### Vehicle ID coverage (Top 12 routes)")
        cov_route = ranking.head(12).sort_values("vehicle_coverage", ascending=False).copy()
        cov_route["label"] = cov_route["route"] + " · " + cov_route["direction"]
        cov_route["pct"] = (cov_route["vehicle_coverage"] * 100).round(1)
        fig_cov = px.bar(
            cov_route, x="label", y="pct",
            color="pct", color_continuous_scale=LOAD_SCALE, range_color=[0, 100],
            labels={"label": "Route", "pct": "Has vehicle ID (%)"},
        )
        fig_cov.update_layout(**_plotly_defaults(), height=250, showlegend=False, xaxis_tickangle=-35)
        st.plotly_chart(_grid(fig_cov), width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("#### Weekday vs. Weekend hourly demand")
        wd_we = analytics.weekday_weekend_hourly(filtered_tickets)
        wd_we["day_type"] = wd_we["ticket_is_weekend"].map({True: "Weekend", False: "Weekday"})
        fig_wd = px.line(
            wd_we, x="ticket_hour", y="passenger_volume", color="day_type", markers=True,
            color_discrete_map={"Weekday": NAVY_DEEP, "Weekend": ACCENT_AMBER},
            labels={"ticket_hour": "Hour of day (IST)", "passenger_volume": "Passenger volume", "day_type": "Day type"},
        )
        fig_wd.update_layout(**_plotly_defaults(), height=360)
        st.plotly_chart(_grid(fig_wd), width="stretch")

    with c4:
        st.markdown("#### Daily passenger volume (October 2026)")
        daily = analytics.weekday_daily_volume(filtered_tickets)
        daily["day_type"] = daily["is_weekend"].map({True: "Weekend", False: "Weekday"})
        fig_day = px.bar(
            daily, x="ticket_date", y="passenger_volume", color="day_type",
            color_discrete_map={"Weekday": TEAL_PRIMARY, "Weekend": ACCENT_AMBER},
            labels={"ticket_date": "Date", "passenger_volume": "Passenger volume", "day_type": "Day type"},
        )
        fig_day.update_layout(**_plotly_defaults(), height=360, xaxis_tickangle=-30)
        st.plotly_chart(_grid(fig_day), width="stretch")

    st.markdown("#### Route demand heatmap (Top 15 matching routes × Hour IST)")
    top_routes = ranking["route"].drop_duplicates().head(15).tolist()
    sub = filtered_tickets[filtered_tickets["route"].isin(top_routes)]
    if len(sub) > 0:
        hm = sub.groupby(["route", "ticket_hour"], as_index=False)["passenger_count"].sum()
        pivot = (
            hm.pivot(index="route", columns="ticket_hour", values="passenger_count")
            .reindex(columns=range(24), fill_value=0)
            .fillna(0)
        )
        fig_hm = px.imshow(
            pivot.values, x=list(pivot.columns), y=list(pivot.index),
            color_continuous_scale=LOAD_SCALE,
            labels=dict(x="Hour (IST)", y="Route", color="Passengers"),
            aspect="auto",
        )
        fig_hm.update_layout(**_plotly_defaults(), height=460)
        st.plotly_chart(_grid(fig_hm), width="stretch")

    st.markdown("#### Route ranking table")
    rank_disp = ranking.head(50).copy()
    rank_disp["vehicle_coverage"] = (rank_disp["vehicle_coverage"] * 100).round(1)
    rank_disp["avg_passenger_count"] = rank_disp["avg_passenger_count"].round(2)
    st.dataframe(
        rank_disp[[
            "demand_rank", "route", "direction", "passenger_volume",
            "ticket_count", "avg_passenger_count", "vehicle_coverage", "unique_stops",
        ]].rename(columns={
            "demand_rank": "Rank",
            "route": "Route",
            "direction": "Direction",
            "passenger_volume": "Passengers",
            "ticket_count": "Tickets",
            "avg_passenger_count": "Avg Pax/Ticket",
            "vehicle_coverage": "Vehicle ID %",
            "unique_stops": "Boarding Stops",
        }),
        width="stretch",
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# 4. Segment Explorer (Signature Feature)
# ---------------------------------------------------------------------------
def render_segment_explorer(tickets, segments, topology):
    ui_theme.hero(
        "Segment Explorer",
        "Inspect stop-to-stop corridor demand and pinpoint peak bottleneck segments per route",
        badge="Corridor Diagnostics",
    )

    if segments is None or len(segments) == 0:
        st.warning("No segments available for the current dataset.")
        return

    routes = sorted(segments["route"].unique())
    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        route = st.selectbox("Select route", routes, index=0, key="se_route")
    avail_dirs = sorted(segments.loc[segments["route"] == route, "direction"].unique())
    with c2:
        sel_dir = st.selectbox("Direction", avail_dirs, index=0, key="se_dir")
    with c3:
        sort_metric = st.selectbox(
            "Sort table by",
            ["rank (stop order)", "segment_load", "relative_load_index"],
            key="se_sort",
        )

    seg_route = analytics.route_segments(segments, route, sel_dir)
    if len(seg_route) == 0:
        st.warning(f"No segments for {route} ({sel_dir}).")
        return

    peak_row = seg_route.loc[seg_route["segment_load"].idxmax()]
    avg_load = float(seg_route["segment_load"].mean())
    route_tickets = tickets[(tickets["route"] == route) & (tickets["direction"] == sel_dir)]
    veh_cov = float(route_tickets["has_vehicle"].mean() * 100) if len(route_tickets) else 0.0

    ui_theme.kpi_row([
        ("Corridor Segments", f"{len(seg_route)}", f"{route} · {sel_dir.upper()}"),
        ("Peak Segment Load", f"{int(peak_row['segment_load']):,}",
         f"{str(peak_row['from_norm']).title()} → {str(peak_row['to_norm']).title()}"),
        ("Avg Segment Load", f"{avg_load:,.1f}", "historical passengers / segment"),
        ("Route Vehicle Coverage", f"{veh_cov:.1f}%", f"{len(route_tickets):,} observed tickets"),
    ])

    # Signature Stop-to-Stop Visual Corridor
    st.markdown("#### Visual stop-to-stop demand corridor")
    st.caption("Stops are ordered by reconstructed topology rank; bar thickness and color reflect segment load (Teal = low, Amber = moderate, Coral = high).")
    st.markdown(ui_theme.corridor_strip_html(seg_route), unsafe_allow_html=True)

    # Bar chart along route order
    hover_labels = (
        seg_route["from_norm"].astype(str).str.title()
        + " → "
        + seg_route["to_norm"].astype(str).str.title()
    )
    bar_colors = [ui_theme.demand_tier(float(r))[1] for r in seg_route["relative_load_index"]]
    fig = go.Figure(
        go.Bar(
            x=seg_route["rank_a"].astype(str) + "→" + seg_route["rank_b"].astype(str),
            y=seg_route["segment_load"],
            customdata=hover_labels,
            marker_color=bar_colors,
            hovertemplate="Rank %{x}<br>%{customdata}<br>Historical volume: %{y:,}<extra></extra>",
        )
    )
    fig.update_layout(
        **_plotly_defaults(),
        title=f"Segment load profile · {route} ({sel_dir.upper()})",
        xaxis_title="Consecutive stop rank pair",
        yaxis_title="Historical passenger volume",
        height=390,
    )
    st.plotly_chart(_grid(fig), width="stretch")

    # Top Bottlenecks + Hourly Profile
    cb1, cb2 = st.columns([1, 1])
    with cb1:
        st.markdown("#### Highest-demand segments on this route")
        top3 = seg_route.nlargest(3, "segment_load")
        for row in top3.itertuples(index=False):
            rel = float(row.relative_load_index)
            lbl, col, bg = ui_theme.demand_tier(rel)
            st.markdown(
                f'<div class="ll-card" style="padding:0.75rem 1rem;margin-bottom:0.5rem;border-left:4px solid {col};">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">'
                f'<div><strong>{html.escape(str(row.from_norm).title())} → {html.escape(str(row.to_norm).title())}</strong><br>'
                f'<span class="ll-muted">Rank {int(row.rank_a)}→{int(row.rank_b)} · {int(row.ticket_count):,} tickets</span></div>'
                f'<div style="text-align:right;"><strong style="color:{NAVY_DEEP};">{int(row.segment_load):,} pax</strong><br>'
                f'<span class="ll-demand-pill" style="color:{col};background:{bg};padding:0.15rem 0.5rem;font-size:0.74rem;">{lbl} ({rel:.2f})</span></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    with cb2:
        st.markdown(f"#### Hourly profile · {route} ({sel_dir.upper()})")
        fig_h = _grid(_hour_chart(route_tickets, f"{route} · {sel_dir.upper()} hourly demand (IST)", highlight_peak=True))
        fig_h.update_layout(height=300)
        st.plotly_chart(fig_h, width="stretch")

    # Per-segment table
    st.markdown("#### Complete segment breakdown")
    if sort_metric == "segment_load":
        seg_view = seg_route.sort_values("segment_load", ascending=False)
    elif sort_metric == "relative_load_index":
        seg_view = seg_route.sort_values("relative_load_index", ascending=False)
    else:
        seg_view = seg_route.copy()

    disp = seg_view.copy()
    disp["from"] = disp["from_norm"].astype(str).str.title()
    disp["to"] = disp["to_norm"].astype(str).str.title()
    disp["tier"] = disp["relative_load_index"].map(lambda r: ui_theme.demand_tier(float(r))[0])
    disp["relative_load_index"] = disp["relative_load_index"].astype(float).round(3)
    st.dataframe(
        disp[["rank_a", "rank_b", "from", "to", "segment_load", "ticket_count", "relative_load_index", "tier"]].rename(columns={
            "rank_a": "Rank A",
            "rank_b": "Rank B",
            "from": "From stop",
            "to": "To stop",
            "segment_load": "Volume",
            "ticket_count": "Tickets",
            "relative_load_index": "Relative Load Index",
            "tier": "Demand Tier",
        }),
        width="stretch",
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# 5. Data Quality / Confidence
# ---------------------------------------------------------------------------
def render_data_quality(tickets, segments, topology, dq, seg_meta=None):
    ui_theme.hero(
        "Data Quality & Confidence",
        "Row-level audit trail, missing vehicle coverage, and observed vs. inferred boundaries",
        badge="Audit & Methodology",
    )

    if not dq:
        st.warning("Quality report not available for the active dataset.")
        return

    meta = seg_meta if seg_meta is not None else _meta()

    ui_theme.kpi_row([
        ("Raw Ticket Rows", f"{dq['raw_rows']:,}", "ingested from source"),
        ("Kept Rows", f"{dq['kept_rows']:,}", f"{dq['kept_rows']/max(dq['raw_rows'],1)*100:.1f}% retained"),
        ("Missing Vehicle ID", f"{dq['missing_vehicle_number_pct']:.2f}%",
         f"{dq.get('missing_vehicle_number_count', 0):,} rows without vehicle_number"),
        ("Topology Chains", f"{len(topology):,}", f"across {dq['unique_routes']:,} unique route labels"),
        ("Back-Tracked Rejected", f"{meta.get('skipped_backward_journeys', 0):,}",
         f"{meta.get('skipped_unknown_stops', 0):,} unmatched stop rows"),
    ])

    # Observed vs Inferred vs Unavailable transparency panel
    st.markdown("#### What is directly observed vs. inferred vs. unavailable")
    o1, o2, o3 = st.columns(3)
    with o1:
        ui_theme.card(
            f"<h4 style='margin-top:0;color:{TEAL_PRIMARY};'>Directly Observed</h4>"
            "<ul style='padding-left:1.1rem;margin-bottom:0;font-size:0.88rem;'>"
            "<li><code>route</code>, <code>start_stop_name</code>, <code>end_stop_name</code></li>"
            "<li><code>passenger_count</code> (exact ticket count, never extrapolated)</li>"
            "<li><code>created_at</code> (normalised to IST, treated as ticket creation time)</li>"
            "<li>Partial <code>vehicle_number</code> (kept as coverage statistic only)</li>"
            "</ul>"
        )
    with o2:
        ui_theme.card(
            f"<h4 style='margin-top:0;color:{ACCENT_AMBER};'>Derived / Estimated</h4>"
            "<ul style='padding-left:1.1rem;margin-bottom:0;font-size:0.88rem;'>"
            "<li>Directional stop order via cycle-broken OD DAG when GTFS is absent</li>"
            "<li>Consecutive segment passenger sums (<code>start_rank &lt; end_rank</code>)</li>"
            "<li>Within-route 0–1 <strong>Relative Load Index</strong> &amp; Low/Moderate/High tiers</li>"
            "</ul>"
        )
    with o3:
        ui_theme.card(
            f"<h4 style='margin-top:0;color:{ACCENT_RED};'>Unavailable (Never Fabricated)</h4>"
            "<ul style='padding-left:1.1rem;margin-bottom:0;font-size:0.88rem;'>"
            "<li>Live GPS vehicle locations &amp; real-time bus occupancy</li>"
            "<li>Seat capacity / physical bus fullness (&ldquo;overcrowded&rdquo; flags)</li>"
            "<li>Scheduled travel times &amp; transfers without supplied GTFS</li>"
            "<li>Trip-level loads on rows missing <code>vehicle_number</code></li>"
            "</ul>"
        )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Row accounting & exclusions")
        rows = [
            ("Missing core fields", dq.get("dropped_missing_core", 0)),
            ("Invalid / empty stop names", dq.get("dropped_invalid_stop_names", 0)),
            ("Non-positive passenger_count", dq.get("dropped_nonpositive_passenger_count", 0)),
            ("Same origin == destination", dq.get("dropped_same_origin_and_destination", 0)),
            ("Back-tracked in topology (start_rank > end_rank)", meta.get("skipped_backward_journeys", 0)),
            ("Same rank in topology", meta.get("skipped_same_stop", 0)),
            ("Unknown / unmatched stop in topology", meta.get("skipped_unknown_stops", 0)),
        ]
        df_excl = pd.DataFrame(rows, columns=["Exclusion Reason", "Rows Excluded"])
        df_excl["Rows Excluded"] = df_excl["Rows Excluded"].map(lambda v: f"{int(v):,}")
        st.dataframe(df_excl, width="stretch", hide_index=True)

    with c2:
        st.markdown("#### Passengers per ticket distribution")
        if len(tickets) > 0:
            ct = tickets["passenger_count"].astype(int).value_counts().sort_index().reset_index()
            ct.columns = ["passenger_count", "n_tickets"]
            fig = px.bar(
                ct, x="passenger_count", y="n_tickets",
                color_discrete_sequence=[NAVY_DEEP],
                labels={"passenger_count": "Passengers on ticket", "n_tickets": "Ticket count"},
            )
            fig.update_layout(**_plotly_defaults(), height=320, showlegend=False)
            st.plotly_chart(_grid(fig), width="stretch")
        else:
            st.info("No cleaned ticket rows to display.")

    st.markdown("#### Vehicle ID coverage by hour-of-day (IST)")
    if len(tickets) > 0:
        cov_hour = (
            tickets.assign(has_veh=tickets["has_vehicle"].astype(int))
            .groupby("ticket_hour", as_index=False)["has_veh"]
            .mean()
        )
        cov_hour["pct"] = (cov_hour["has_veh"] * 100).round(1)
        fig = px.bar(
            cov_hour, x="ticket_hour", y="pct",
            color="pct", color_continuous_scale=LOAD_SCALE, range_color=[0, 100],
            labels={"ticket_hour": "Hour of day (IST)", "pct": "% with vehicle_number"},
        )
        fig.update_layout(**_plotly_defaults(), height=320, showlegend=False)
        st.plotly_chart(_grid(fig), width="stretch")


@st.cache_data
def _meta() -> dict:
    p = Path(__file__).resolve().parent / "data" / "cache" / "segment_meta.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
