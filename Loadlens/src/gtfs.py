"""Optional static GTFS feed loader and schedule-aware journey search.

When official GTFS files (``stops.txt``, ``routes.txt``, ``trips.txt``,
``stop_times.txt``) are supplied in ``data/gtfs/``, this module computes
real scheduled stop sequences and travel durations from ``stop_times.txt``
and joins them with historical ticket-derived segment loads.

When any required GTFS file is missing or invalid, callers fall back
gracefully to ticket-derived topology and disable schedule-based metrics.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional

import numpy as np
import pandas as pd

from .data_loader import normalize_stop

REQUIRED_GTFS_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")

_REQUIRED_COLUMNS = {
    "stops.txt": {"stop_id", "stop_name"},
    "routes.txt": {"route_id"},
    "trips.txt": {"route_id", "trip_id"},
    "stop_times.txt": {"trip_id", "stop_id", "stop_sequence"},
}


def gtfs_status(folder: Path) -> Dict[str, Any]:
    """Inspect *folder* for the required GTFS files and validate headers."""
    if not folder.exists() or not folder.is_dir():
        return {
            "available": False,
            "missing_files": list(REQUIRED_GTFS_FILES),
            "present_files": [],
            "error": f"GTFS directory not found: {folder}",
        }

    present = [f for f in REQUIRED_GTFS_FILES if (folder / f).is_file()]
    missing = [f for f in REQUIRED_GTFS_FILES if f not in present]
    if missing:
        return {
            "available": False,
            "missing_files": missing,
            "present_files": present,
            "error": f"Missing required GTFS file(s): {', '.join(missing)}",
        }

    for fname, req_cols in _REQUIRED_COLUMNS.items():
        try:
            hdr = pd.read_csv(folder / fname, nrows=0)
        except Exception as exc:
            return {
                "available": False,
                "missing_files": [],
                "present_files": present,
                "error": f"Unable to read {fname}: {exc}",
            }
        cols = {c.strip() for c in hdr.columns}
        if not req_cols.issubset(cols):
            return {
                "available": False,
                "missing_files": [],
                "present_files": present,
                "error": f"{fname} missing required columns {sorted(req_cols - cols)}",
            }

    return {
        "available": True,
        "missing_files": [],
        "present_files": present,
        "error": None,
    }


def extract_gtfs_zip(file_obj: BinaryIO, target_dir: Path) -> Dict[str, Any]:
    """Extract required GTFS ``.txt`` files from an uploaded zip archive."""
    target_dir.mkdir(parents=True, exist_ok=True)
    raw_bytes = file_obj.read()
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            base = Path(member.filename).name
            if base.endswith(".txt"):
                (target_dir / base).write_bytes(zf.read(member))
    return gtfs_status(target_dir)


def _parse_gtfs_seconds(val: Any) -> Optional[int]:
    """Convert GTFS ``HH:MM:SS`` (supports hours >= 24) to seconds since midnight."""
    if not isinstance(val, str):
        if pd.isna(val):
            return None
        val = str(val)
    s = val.strip()
    if not s:
        return None
    parts = s.split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    return h * 3600 + m * 60 + sec


def load_gtfs_feed(folder: Path) -> Dict[str, pd.DataFrame]:
    """Read and minimally normalise the four core GTFS tables."""
    status = gtfs_status(folder)
    if not status["available"]:
        raise FileNotFoundError(status["error"] or "GTFS feed incomplete")

    stops = pd.read_csv(folder / "stops.txt", dtype={"stop_id": str})
    routes = pd.read_csv(folder / "routes.txt", dtype={"route_id": str})
    trips = pd.read_csv(folder / "trips.txt", dtype={"route_id": str, "trip_id": str})
    stop_times = pd.read_csv(folder / "stop_times.txt", dtype={"trip_id": str, "stop_id": str})

    stops["stop_id"] = stops["stop_id"].astype(str).str.strip()
    stops["stop_norm"] = stops["stop_name"].astype(str).map(normalize_stop)
    routes["route_id"] = routes["route_id"].astype(str).str.strip()
    if "route_short_name" not in routes.columns:
        routes["route_short_name"] = routes.get("route_long_name", routes["route_id"])
    routes["route_label"] = (
        routes["route_short_name"].fillna(routes["route_id"]).astype(str).str.strip()
    )
    trips["route_id"] = trips["route_id"].astype(str).str.strip()
    trips["trip_id"] = trips["trip_id"].astype(str).str.strip()
    if "direction_id" not in trips.columns:
        trips["direction_id"] = np.nan

    stop_times["trip_id"] = stop_times["trip_id"].astype(str).str.strip()
    stop_times["stop_id"] = stop_times["stop_id"].astype(str).str.strip()
    stop_times["stop_sequence"] = pd.to_numeric(stop_times["stop_sequence"], errors="coerce")
    stop_times = stop_times.dropna(subset=["stop_sequence"]).copy()
    stop_times["stop_sequence"] = stop_times["stop_sequence"].astype(int)
    stop_times["arr_sec"] = (
        stop_times["arrival_time"].map(_parse_gtfs_seconds)
        if "arrival_time" in stop_times.columns
        else None
    )
    stop_times["dep_sec"] = (
        stop_times["departure_time"].map(_parse_gtfs_seconds)
        if "departure_time" in stop_times.columns
        else None
    )

    return {
        "stops": stops,
        "routes": routes,
        "trips": trips,
        "stop_times": stop_times,
    }


def search_gtfs_direct_options(
    folder: Path,
    segments: pd.DataFrame,
    origin_norm: str,
    dest_norm: str,
    *,
    max_options: int = 5,
) -> Dict[str, Any]:
    """Find direct GTFS routes from *origin_norm* to *dest_norm* with real schedule times."""
    feed = load_gtfs_feed(folder)
    stops = feed["stops"]
    routes = feed["routes"]
    trips = feed["trips"]
    st_df = feed["stop_times"]

    orig_ids = set(stops.loc[stops["stop_norm"] == origin_norm, "stop_id"])
    dest_ids = set(stops.loc[stops["stop_norm"] == dest_norm, "stop_id"])
    if not orig_ids or not dest_ids:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "Origin or destination stop not found in GTFS stops.txt.",
        }

    st_orig = st_df[st_df["stop_id"].isin(orig_ids)][
        ["trip_id", "stop_sequence", "dep_sec", "arr_sec"]
    ].rename(columns={"stop_sequence": "seq_o", "dep_sec": "dep_o", "arr_sec": "arr_o"})
    st_dest = st_df[st_df["stop_id"].isin(dest_ids)][
        ["trip_id", "stop_sequence", "arr_sec", "dep_sec"]
    ].rename(columns={"stop_sequence": "seq_d", "arr_sec": "arr_d", "dep_sec": "dep_d"})

    pairs = st_orig.merge(st_dest, on="trip_id", how="inner")
    pairs = pairs[pairs["seq_o"] < pairs["seq_d"]].copy()
    if len(pairs) == 0:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "No direct GTFS trip connects the selected stops in that direction.",
        }

    pairs["start_sec"] = pairs["dep_o"].fillna(pairs["arr_o"])
    pairs["end_sec"] = pairs["arr_d"].fillna(pairs["dep_d"])
    pairs["dur_min"] = (pairs["end_sec"] - pairs["start_sec"]) / 60.0
    pairs.loc[pairs["dur_min"] < 0, "dur_min"] = np.nan

    pairs = pairs.merge(trips[["trip_id", "route_id", "direction_id"]], on="trip_id", how="left")
    pairs = pairs.merge(routes[["route_id", "route_label"]], on="route_id", how="left")

    stop_name_map = dict(zip(stops["stop_id"], stops["stop_norm"]))
    has_coords = {"stop_lat", "stop_lon"}.issubset(stops.columns)
    coord_map: Dict[str, tuple[float, float]] = {}
    if has_coords:
        stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
        stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
        valid_c = stops.dropna(subset=["stop_lat", "stop_lon"])
        coord_map = {
            r.stop_id: (float(r.stop_lat), float(r.stop_lon))
            for r in valid_c.itertuples(index=False)
        }

    seg_lookup = {}
    if segments is not None and len(segments) > 0:
        for row in segments.itertuples(index=False):
            key = (str(row.route).upper(), str(row.from_norm), str(row.to_norm))
            if key not in seg_lookup:
                seg_lookup[key] = (
                    float(row.segment_load),
                    int(row.ticket_count),
                    float(row.relative_load_index),
                )
        pair_lookup = (
            segments.groupby(["from_norm", "to_norm"], as_index=False)
            .agg(
                segment_load=("segment_load", "sum"),
                ticket_count=("ticket_count", "sum"),
                relative_load_index=("relative_load_index", "mean"),
            )
        )
        od_lookup = {
            (r.from_norm, r.to_norm): (
                float(r.segment_load),
                int(r.ticket_count),
                float(r.relative_load_index),
            )
            for r in pair_lookup.itertuples(index=False)
        }
    else:
        od_lookup = {}

    options: List[Dict[str, Any]] = []
    for (route_id, route_label, dir_id), grp in pairs.groupby(
        ["route_id", "route_label", "direction_id"], dropna=False
    ):
        rep = grp.sort_values("dur_min", na_position="last").iloc[len(grp) // 2]
        trip_id = rep["trip_id"]
        trip_stops = (
            st_df[(st_df["trip_id"] == trip_id) &
                  (st_df["stop_sequence"] >= rep["seq_o"]) &
                  (st_df["stop_sequence"] <= rep["seq_d"])]
            .sort_values("stop_sequence")
        )
        stop_ids = list(trip_stops["stop_id"])
        norms = [stop_name_map.get(sid, sid) for sid in stop_ids]
        if len(norms) < 2:
            continue

        seg_rows = []
        r_upper = str(route_label).upper()
        for a, b in zip(norms[:-1], norms[1:]):
            load_val, t_cnt, rli_val = seg_lookup.get(
                (r_upper, a, b),
                od_lookup.get((a, b), (0.0, 0, 0.0)),
            )
            seg_rows.append({
                "from_norm": a,
                "to_norm": b,
                "segment_load": load_val,
                "ticket_count": t_cnt,
                "relative_load_index": rli_val,
            })
        seg_df = pd.DataFrame(seg_rows)
        seg_load = float(seg_df["segment_load"].sum())
        rel = float(seg_df["relative_load_index"].mean()) if len(seg_df) else 0.0
        med_dur = grp["dur_min"].median()
        est_dur = round(float(med_dur), 1) if pd.notna(med_dur) else None
        direction_str = (
            "up" if dir_id == 0 else ("down" if dir_id == 1 else "gtfs")
        )
        stop_coords = None
        if coord_map and all(sid in coord_map for sid in stop_ids):
            stop_coords = [
                {"stop": stop_name_map.get(sid, sid), "lat": coord_map[sid][0], "lon": coord_map[sid][1]}
                for sid in stop_ids
            ]
        options.append({
            "route": str(route_label),
            "direction": direction_str,
            "origin": origin_norm,
            "destination": dest_norm,
            "segment_count": len(seg_df),
            "historical_segment_load": seg_load,
            "relative_load_index": round(rel, 3),
            "estimated_duration_min": est_dur,
            "duration_source": "GTFS stop_times.txt" if est_dur is not None else "Unavailable",
            "stop_coords": stop_coords,
            "segments": seg_df,
        })

    if not options:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "No direct GTFS route matched between the selected stops.",
        }

    options.sort(key=lambda o: (o["relative_load_index"], o["segment_count"]))
    return {"options": options[:max_options], "mode": "gtfs", "message": ""}
