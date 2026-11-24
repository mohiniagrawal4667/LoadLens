"""Journey planning built on top of the reconstructed route topology or GTFS.

These functions produce *historical ticket-derived* demand estimates for the
segments a candidate trip would traverse. They never invent capacity
thresholds, live occupancy numbers, or fabricated heuristic durations.

When official GTFS files (``stops.txt``, ``routes.txt``, ``trips.txt``,
``stop_times.txt``) are supplied, :func:`search_options_with_gtfs` computes
schedule-accurate durations from ``stop_times.txt`` paired with historical
ticket-derived segment loads. Otherwise, :func:`search_options_topology`
uses the ticket-derived stop ordering and leaves travel duration unavailable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .data_loader import normalize_stop
from .gtfs import gtfs_status, search_gtfs_direct_options
from .topology import load_topology


def _reset_cache() -> None:
    """No-op kept for backward compatibility with callers/tests."""
    return None


def stop_index(tickets: pd.DataFrame) -> pd.DataFrame:
    """Build a ranked list of unique stops for UI autocomplete."""
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=["stop_norm", "as_start", "as_end", "volume", "display"])
    s = tickets["start_norm"].value_counts().rename_axis("stop_norm").reset_index(name="as_start")
    e = tickets["end_norm"].value_counts().rename_axis("stop_norm").reset_index(name="as_end")
    df = s.merge(e, on="stop_norm", how="outer").fillna(0)
    df["volume"] = df["as_start"] + df["as_end"]
    df["display"] = df["stop_norm"].astype(str).str.title()
    return df.sort_values("volume", ascending=False).reset_index(drop=True)


def suggest_stop(query: str, stops: pd.DataFrame, k: int = 8) -> pd.DataFrame:
    """Return up to *k* stop suggestions matching *query*.

    When *query* is empty/blank, returns the top-*k* stops by volume.
    When *query* is non-empty and matches nothing, returns an empty DataFrame
    rather than silently substituting popular unrelated stops.
    """
    if stops is None or len(stops) == 0:
        return pd.DataFrame(columns=["stop_norm", "as_start", "as_end", "volume", "display"])
    if not query or not isinstance(query, str) or not query.strip():
        return stops.head(k)
    q = normalize_stop(query)
    if not q:
        return stops.iloc[0:0]

    def _score(s: str) -> int:
        if not isinstance(s, str) or not s:
            return 0
        if s == q:
            return 100
        if s.startswith(q):
            return 80
        if q in s or s in q:
            return 60
        qs = set(q.split())
        ss = set(s.split())
        overlap = len(qs & ss)
        return 20 * overlap if overlap > 0 else 0

    s = stops.copy()
    s["score"] = s["stop_norm"].map(_score)
    s = s[s["score"] > 0]
    if len(s) == 0:
        return s.drop(columns=["score"])
    sort_cols = ["score", "volume"] if "volume" in s.columns else ["score"]
    return s.sort_values(sort_cols, ascending=False).head(k).reset_index(drop=True)


def _segment_loads_for_route(segments: pd.DataFrame, route: str, direction: str) -> pd.DataFrame:
    if segments is None or len(segments) == 0:
        return pd.DataFrame(columns=[
            "route", "direction", "rank_a", "rank_b", "from_norm", "to_norm",
            "segment_load", "ticket_count", "relative_load_index",
        ])
    sel = segments[(segments["route"] == route) & (segments["direction"] == direction)]
    return sel.sort_values("rank_a").reset_index(drop=True)


def search_options_topology(
    tickets: pd.DataFrame,
    segments: pd.DataFrame,
    origin_norm: str,
    dest_norm: str,
    *,
    topology: Optional[Dict] = None,
    max_options: int = 5,
) -> Dict:
    """Find candidate direct trips using the ticket-derived topology."""
    orig = normalize_stop(origin_norm) if isinstance(origin_norm, str) else ""
    dest = normalize_stop(dest_norm) if isinstance(dest_norm, str) else ""

    if not orig or not dest:
        return {
            "options": [],
            "mode": "topology",
            "message": "Select both a valid origin stop and destination stop.",
        }
    if orig == dest:
        return {
            "options": [],
            "mode": "topology",
            "message": "Origin and destination resolve to the same stop; no trip needed.",
        }

    topo = topology if topology is not None else load_topology()
    if not topo:
        return {
            "options": [],
            "mode": "topology",
            "message": "No route topology is available for the current dataset.",
        }

    known_stops = {stop for ranks in topo.values() for stop in ranks}
    if orig not in known_stops or dest not in known_stops:
        missing = []
        if orig not in known_stops:
            missing.append(f"origin '{orig}'")
        if dest not in known_stops:
            missing.append(f"destination '{dest}'")
        return {
            "options": [],
            "mode": "topology",
            "message": (
                f"Stop not found in route topology ({', '.join(missing)}). "
                "No direct options can be computed."
            ),
        }

    route_cov: Dict[tuple[str, str], tuple[int, float]] = {}
    if tickets is not None and len(tickets) > 0:
        cov_df = tickets.groupby(["route", "direction"], as_index=False).agg(
            n_t=("passenger_count", "count"),
            veh_pct=("has_vehicle", "mean"),
        )
        for row in cov_df.itertuples(index=False):
            route_cov[(str(row.route), str(row.direction))] = (
                int(row.n_t),
                round(float(row.veh_pct) * 100, 1),
            )

    options: List[Dict] = []
    for (route, direction), ranks in topo.items():
        if orig not in ranks or dest not in ranks:
            continue
        a = ranks[orig]
        b = ranks[dest]
        if a >= b:
            # Same direction: destination must be downstream of boarding stop.
            continue
        segs = _segment_loads_for_route(segments, route, direction)
        segs_window = segs[(segs["rank_a"] >= a) & (segs["rank_b"] <= b)]
        if len(segs_window) == 0:
            continue
        seg_load = float(segs_window["segment_load"].sum())
        seg_count = int(len(segs_window))
        rel = float(segs_window["relative_load_index"].mean())
        r_tickets, r_veh_pct = route_cov.get((route, direction), (0, 0.0))
        options.append({
            "route": route,
            "direction": direction,
            "origin": orig,
            "destination": dest,
            "segment_count": seg_count,
            "historical_segment_load": seg_load,
            "relative_load_index": round(rel, 3),
            "estimated_duration_min": None,
            "duration_source": "Unavailable (GTFS stop_times.txt required)",
            "route_tickets": r_tickets,
            "route_vehicle_coverage_pct": r_veh_pct,
            "stop_coords": None,
            "segments": segs_window[
                ["from_norm", "to_norm", "segment_load", "ticket_count", "relative_load_index"]
            ].reset_index(drop=True),
        })

    if not options:
        return {
            "options": [],
            "mode": "topology",
            "message": (
                "No direct option found between the selected stops in this direction. "
                "Multi-leg transfers are disabled because GTFS schedule data is not supplied."
            ),
        }

    options.sort(key=lambda o: (o["relative_load_index"], o["segment_count"]))
    return {"options": options[:max_options], "mode": "topology", "message": ""}


def search_options_with_gtfs(
    gtfs_dir: Path,
    segments: pd.DataFrame,
    origin_norm: str,
    dest_norm: str,
    *,
    max_options: int = 5,
) -> Dict:
    """Find candidate trips using official GTFS schedules + historical segment loads."""
    orig = normalize_stop(origin_norm) if isinstance(origin_norm, str) else ""
    dest = normalize_stop(dest_norm) if isinstance(dest_norm, str) else ""
    if not orig or not dest:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "Select both a valid origin stop and destination stop.",
        }
    if orig == dest:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "Origin and destination resolve to the same stop; no trip needed.",
        }
    return search_gtfs_direct_options(
        gtfs_dir, segments, orig, dest, max_options=max_options
    )


def gtfs_available(folder: Path) -> bool:
    return bool(gtfs_status(folder)["available"])
