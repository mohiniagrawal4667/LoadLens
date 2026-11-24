"""Aggregate analytics — route rankings, time patterns, heat-maps."""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


# ---- Route-level ranking --------------------------------------------------

def route_demand_ranking(tickets: pd.DataFrame) -> pd.DataFrame:
    """Rank every route by aggregate passenger demand and volume."""
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=[
            "route", "direction", "passenger_volume", "ticket_count",
            "avg_passenger_count", "vehicle_coverage", "unique_stops", "demand_rank",
        ])
    g = tickets.groupby(["route", "direction"], as_index=False).agg(
        passenger_volume=("passenger_count", "sum"),
        ticket_count=("passenger_count", "count"),
        avg_passenger_count=("passenger_count", "mean"),
        vehicle_coverage=("has_vehicle", "mean"),
        unique_stops=("start_norm", "nunique"),
    )
    g = g.sort_values("passenger_volume", ascending=False).reset_index(drop=True)
    g["demand_rank"] = g["passenger_volume"].rank(method="dense", ascending=False).astype(int)
    return g


# ---- Time patterns --------------------------------------------------------

def hour_of_day_demand(tickets: pd.DataFrame) -> pd.DataFrame:
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=["ticket_hour", "passenger_volume", "ticket_count"])
    return (tickets.groupby(["ticket_hour"], as_index=False)
            .agg(passenger_volume=("passenger_count", "sum"),
                 ticket_count=("passenger_count", "count"))
            .sort_values("ticket_hour"))


def weekday_weekend_hourly(tickets: pd.DataFrame) -> pd.DataFrame:
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=["ticket_is_weekend", "ticket_hour", "passenger_volume", "ticket_count"])
    return (tickets.groupby(["ticket_is_weekend", "ticket_hour"], as_index=False)
            .agg(passenger_volume=("passenger_count", "sum"),
                 ticket_count=("passenger_count", "count")))


def weekday_daily_volume(tickets: pd.DataFrame) -> pd.DataFrame:
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=["ticket_date", "passenger_volume", "ticket_count", "dow", "is_weekend"])
    daily = (tickets.groupby(["ticket_date"], as_index=False)
             .agg(passenger_volume=("passenger_count", "sum"),
                  ticket_count=("passenger_count", "count")))
    daily["dow"] = pd.to_datetime(daily["ticket_date"]).dt.dayofweek
    daily["is_weekend"] = daily["dow"].isin([5, 6])
    return daily


def peak_vs_offpeak(tickets: pd.DataFrame) -> Dict:
    """Compare peak windows (08-11, 17-21) with off-peak hours."""
    if tickets is None or len(tickets) == 0:
        return {
            "peak_passenger_volume": 0,
            "offpeak_passenger_volume": 0,
            "peak_share_pct": 0.0,
            "peak_window_label": "08:00–11:00 and 17:00–21:00 IST",
        }
    h = tickets["ticket_hour"]
    peak_mask = ((h >= 8) & (h <= 11)) | ((h >= 17) & (h <= 21))
    peak = int(tickets.loc[peak_mask, "passenger_count"].sum())
    off = int(tickets.loc[~peak_mask, "passenger_count"].sum())
    pct_peak = peak / max(peak + off, 1) * 100
    return {
        "peak_passenger_volume": peak,
        "offpeak_passenger_volume": off,
        "peak_share_pct": round(pct_peak, 1),
        "peak_window_label": "08:00–11:00 and 17:00–21:00 IST",
    }


# ---- Segment-level --------------------------------------------------------

def route_segments(segments: pd.DataFrame, route: str, direction: str = "") -> pd.DataFrame:
    """Return segments for a route (and optionally a direction)."""
    if segments is None or len(segments) == 0:
        return pd.DataFrame(columns=[
            "route", "direction", "rank_a", "rank_b", "from_norm", "to_norm",
            "segment_load", "ticket_count", "relative_load_index",
        ])
    sel = segments[segments["route"] == route]
    if direction:
        sel = sel[sel["direction"] == direction]
    return sel.sort_values("rank_a").reset_index(drop=True)


def top_segments(segments: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    if segments is None or len(segments) == 0:
        return pd.DataFrame(columns=[
            "route", "direction", "segment_label",
            "segment_load", "ticket_count", "relative_load_index",
        ])
    s = segments.copy()
    s["segment_label"] = s["from_norm"].astype(str).str.title() + " → " + s["to_norm"].astype(str).str.title()
    return (s.nlargest(n, "segment_load")
            .loc[:, ["route", "direction", "segment_label",
                    "segment_load", "ticket_count", "relative_load_index"]]
            .reset_index(drop=True))


def route_hour_heatmap(tickets: pd.DataFrame, route: str) -> pd.DataFrame:
    sub = tickets[tickets["route"] == route]
    return (sub.groupby([sub["ticket_date"].astype(str), "ticket_hour"], as_index=False)
            ["passenger_count"].sum()
            .pivot_table(index="ticket_date", columns="ticket_hour", values="passenger_count", fill_value=0))


def route_peak_compare(tickets: pd.DataFrame, routes: List[str]) -> pd.DataFrame:
    rows = []
    for r in routes:
        sub = tickets[tickets["route"] == r]
        h = sub["ticket_hour"]
        peak_mask = ((h >= 8) & (h <= 11)) | ((h >= 17) & (h <= 21))
        rows.append({
            "route": r,
            "peak": int(sub.loc[peak_mask, "passenger_count"].sum()),
            "offpeak": int(sub.loc[~peak_mask, "passenger_count"].sum()),
        })
    return pd.DataFrame(rows)


# ---- Coverage / quality ----------------------------------------------------

def coverage_summary(tickets: pd.DataFrame, segments: pd.DataFrame, topology: Dict) -> Dict:
    n_ticket = len(tickets)
    n_with_vehicle = int(tickets["has_vehicle"].sum())
    distinct_vehicles = int(tickets.loc[tickets["has_vehicle"], "vehicle_number"].nunique())
    n_routes_topology = len(topology)
    n_segment_rows = len(segments)
    seg_load_max = float(segments["segment_load"].max()) if len(segments) else 0.0
    return {
        "n_tickets": int(n_ticket),
        "tickets_with_vehicle_pct": round(n_with_vehicle / max(n_ticket, 1) * 100, 2),
        "distinct_vehicles": distinct_vehicles,
        "n_route_directions_in_topology": n_routes_topology,
        "n_segments_aggregated": n_segment_rows,
        "max_segment_load": seg_load_max,
    }
