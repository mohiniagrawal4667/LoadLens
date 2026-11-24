"""Passenger segment-load calculation (fully vectorised).

For every valid ticket journey the engine adds ``passenger_count`` to every
consecutive route segment between its boarding stop and intended destination
along the selected direction.

A ticket is *valid* if and only if the boarding stop precedes the destination
in the topology of the route in the selected direction. Opposite-direction
journeys are rejected (counted separately) and we never invent segment
counts for backtracked trips.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple  # noqa

import numpy as np
import pandas as pd

from .data_loader import CACHE_DIR, SEGMENTS_PARQUET


# ---------------------------------------------------------------------------
# Core segment-load aggregator
# ---------------------------------------------------------------------------

def compute_segment_loads(
    tickets: pd.DataFrame,
    topology: Dict[Tuple[str, str], Dict[str, int]],
) -> Tuple[pd.DataFrame, Dict]:
    """Aggregate per-segment passenger demand.

    Returns (segments_df, meta).
    """
    if not topology or tickets is None or len(tickets) == 0:
        n_in = len(tickets) if tickets is not None else 0
        return _empty_segments(), {
            "used_ticket_rows": 0,
            "skipped_backward_journeys": 0,
            "skipped_same_stop": 0,
            "skipped_unknown_stops": int(n_in),
            "segments_aggregated": 0,
            "input_rows": int(n_in),
        }

    # ---- 1. Vectorised lookup of start/end ranks ----------------------------
    rk = pd.DataFrame(
        [(route, dire, stop, int(rank))
         for (route, dire), ranks in topology.items()
         for stop, rank in ranks.items()],
        columns=["route", "direction", "stop_norm", "rank"],
    )

    sub = tickets[["route", "direction", "start_norm", "end_norm",
                   "passenger_count", "has_vehicle"]].copy()
    sub = sub.merge(
        rk.rename(columns={"stop_norm": "start_norm", "rank": "start_rank"}),
        on=["route", "direction", "start_norm"], how="left",
    ).merge(
        rk.rename(columns={"stop_norm": "end_norm", "rank": "end_rank"}),
        on=["route", "direction", "end_norm"], how="left",
    )

    n_total = len(sub)
    both_known = sub["start_rank"].notna() & sub["end_rank"].notna()
    valid_mask = both_known & (sub["start_rank"] < sub["end_rank"])
    back_mask = both_known & (sub["start_rank"] > sub["end_rank"])
    same_mask = both_known & (sub["start_rank"] == sub["end_rank"])
    n_valid = int(valid_mask.sum())
    n_back = int(back_mask.sum())
    n_same = int(same_mask.sum())
    n_unknown = int(n_total - n_valid - n_back - n_same)

    sel = sub.loc[valid_mask, ["route", "direction", "start_rank", "end_rank", "passenger_count"]].copy()
    sel["start_rank"] = sel["start_rank"].astype(np.int32)
    sel["end_rank"] = sel["end_rank"].astype(np.int32)

    if len(sel) == 0:
        return _empty_segments(), {
            "used_ticket_rows": n_valid,
            "skipped_backward_journeys": n_back,
            "skipped_same_stop": n_same,
            "skipped_unknown_stops": n_unknown,
            "segments_aggregated": 0,
            "input_rows": int(n_total),
        }

    # ---- 2. Expand each ticket into N consecutive segments ------------------
    # seg_count[i] = end_rank - start_rank (number of edges crossed)
    seg_count = (sel["end_rank"].values - sel["start_rank"].values).astype(np.int32)
    # cumulative offsets for np.repeat expansion
    total = int(seg_count.sum())
    # row index per output segment
    row_idx = np.repeat(np.arange(len(sel), dtype=np.int32), seg_count)
    # offsets per original ticket
    offsets = np.concatenate(([0], np.cumsum(seg_count[:-1]))).astype(np.int32)
    # local segment index 0..seg_count-1 for each expanded row
    local_idx = np.arange(total, dtype=np.int32) - np.repeat(offsets, seg_count)
    rank_a = sel["start_rank"].values[row_idx] + local_idx
    rank_b = rank_a + 1
    pass_per_seg = np.repeat(sel["passenger_count"].values.astype(np.int32), seg_count)

    segs = pd.DataFrame({
        "route": np.repeat(sel["route"].values, seg_count),
        "direction": np.repeat(sel["direction"].values, seg_count),
        "rank_a": rank_a,
        "rank_b": rank_b,
        "seg_passengers": pass_per_seg,
        "seg_tickets": 1,
    })

    # ---- 3. Aggregate by (route, direction, rank pair) ----------------------
    agg = segs.groupby(["route", "direction", "rank_a", "rank_b"], as_index=False).agg(
        segment_load=("seg_passengers", "sum"),
        ticket_count=("seg_tickets", "sum"),
    )

    # ---- 4. Map rank -> stop names ------------------------------------------
    name_map = rk.set_index(["route", "direction", "rank"])["stop_norm"]
    agg_index = list(zip(agg["route"], agg["direction"], agg["rank_a"]))
    agg["from_norm"] = [name_map.get(k, "") for k in agg_index]
    agg["to_norm"]   = [name_map.get((r, d, rb), "") for r, d, _, rb in zip(
        agg["route"], agg["direction"], agg["rank_a"], agg["rank_b"])]

    # ---- 5. Relative Load Index per (route, direction) ---------------------
    agg["relative_load_index"] = agg.groupby(["route", "direction"])["segment_load"].transform(
        lambda s: (s - s.min()) / max(s.max() - s.min(), 1)
    ).astype(float)

    agg = agg.sort_values(["route", "direction", "rank_a"]).reset_index(drop=True)

    meta = {
        "used_ticket_rows": int(n_valid),
        "skipped_backward_journeys": int(n_back),
        "skipped_same_stop": int(n_same),
        "skipped_unknown_stops": int(n_unknown),
        "segments_aggregated": int(len(agg)),
        "input_rows": int(n_total),
    }
    return agg, meta


def _empty_segments() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "route", "direction", "rank_a", "rank_b", "from_norm", "to_norm",
        "segment_load", "ticket_count", "relative_load_index",
    ])


def save_segments(tickets: pd.DataFrame, topology) -> Dict:
    segs, meta = compute_segment_loads(tickets, topology)
    segs.to_parquet(SEGMENTS_PARQUET, index=False)
    (CACHE_DIR / "segment_meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def load_segments() -> pd.DataFrame:
    return pd.read_parquet(SEGMENTS_PARQUET)
