"""Route topology reconstruction from ticket OD pairs.

When official GTFS files are unavailable, we still recover a usable stop
ordering for every route+direction by mining observed start→end ticket pairs.

The mining algorithm:
    1.  Build a weighted directed multigraph G per (route, direction):
        nodes = normalised stop names, edges = observed (start, end) pairs,
        weight = number of tickets.
    2.  Drop self-loops (already filtered upstream).
    3.  Compute a robust linear ordering *rank(stop)*

        For each directed edge (A, B):
            confidence(A before B) = weight(A,B) / (weight(A,B) + weight(B,A))

        The final ordering is computed by:

        (a) For each strongly connected component (SCC), collapse the nodes.
            Cycle-breaking is done implicitly: the largest "back edge" inside
            the SCC (one with the smallest weight) is removed iteratively
            until the residual graph is acyclic.

        (b) Kahn's topological sort on the resulting DAG. Ties are broken
            by per-stop ticket-bearing volume (a stop that appears in many
            tickets tends to be a major hub and is anchored).

        (c) The output rank is a *partial* order expressed as a sequence
            indexed 0, 1, 2, ... — gaps are intentional proxies for unknown
            intermediate stops.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx
import numpy as np
import pandas as pd

from .data_loader import CACHE_DIR, SEGMENTS_PARQUET, TRIP_GRAPH_PARQUET


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------

def _build_graphs(tickets: pd.DataFrame) -> Dict[Tuple[str, str], nx.DiGraph]:
    """Return ``{(route, direction) : weighted DiGraph}``."""
    out: Dict[Tuple[str, str], nx.DiGraph] = {}
    grouped = tickets.groupby(["route", "direction"], sort=False)
    for (route, direction), sub in grouped:
        g = nx.DiGraph()
        # Aggregate edge weights quickly with value_counts on a tuple column.
        if len(sub) == 0:
            continue
        s = sub.groupby(["start_norm", "end_norm"]).size()
        for (a, b), w in s.items():
            if not a or not b or a == b:
                continue
            if g.has_edge(a, b):
                g[a][b]["weight"] += int(w)
            else:
                g.add_edge(a, b, weight=int(w))
        out[(route, direction)] = g
    return out


# ---------------------------------------------------------------------------
# Cycle removal + topological ordering
# ---------------------------------------------------------------------------

def _acyclicise(g: nx.DiGraph) -> nx.DiGraph:
    """Return a copy of *g* with the smallest-weight back edges repeatedly
    removed until the graph is a DAG. This is a fast approximation of
    the minimum feedback arc set problem that works for transit-style
    graphs because cycle edges are dominated by the forward arc count."""
    h = g.copy()
    while True:
        try:
            cycle = nx.find_cycle(h, orientation="original")
        except nx.NetworkXNoCycle:
            return h
        # Pick the minimum-weight edge from the cycle (weakest signal).
        weakest = min(cycle, key=lambda e: h[e[0]][e[1]]["weight"])
        h.remove_edge(weakest[0], weakest[1])


def _topo_with_ties(g: nx.DiGraph, hub_score: Dict[str, float]) -> List[str]:
    """Kahn's algorithm with hub-score tie-breaking."""
    indeg = dict(g.in_degree())
    ready = sorted([n for n, d in indeg.items() if d == 0],
                   key=lambda n: -hub_score.get(n, 0))
    order: List[str] = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        succ = sorted(g.successors(n), key=lambda m: -hub_score.get(m, 0))
        for m in succ:
            indeg[m] -= 1
            if indeg[m] == 0:
                # insert preserving hub ranking
                idx = 0
                while idx < len(ready) and hub_score.get(ready[idx], 0) >= hub_score.get(m, 0):
                    idx += 1
                ready.insert(idx, m)
    return order


def _hubs(g: nx.DiGraph) -> Dict[str, float]:
    """Return a per-stop score combining total incident weight + degree.

    The score is used as a tie-breaker inside topological sort so that busier
    hubs (terminals, interchanges) naturally anchor the ordering.
    """
    score: Dict[str, float] = {}
    for n in g.nodes:
        w_out = sum(d["weight"] for _, _, d in g.out_edges(n, data=True))
        w_in = sum(d["weight"] for _, _, d in g.in_edges(n, data=True))
        score[n] = w_out + w_in
    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_route_topology(tickets: pd.DataFrame) -> Dict[Tuple[str, str], Dict[str, int]]:
    """Return ``{(route, direction): {stop_norm: rank}}`` for every route."""
    if tickets is None or len(tickets) == 0:
        return {}
    graphs = _build_graphs(tickets)
    ordering: Dict[Tuple[str, str], Dict[str, int]] = {}
    for key, g in graphs.items():
        if g.number_of_edges() == 0:
            continue
        g_acyclic = _acyclicise(g)
        h = _hubs(g_acyclic)
        topo = _topo_with_ties(g_acyclic, h)
        ordering[key] = {stop: i for i, stop in enumerate(topo)}
    return ordering


# Cached artefact helpers ---------------------------------------------------

def save_topology(tickets: pd.DataFrame) -> Dict[Tuple[str, str], Dict[str, int]]:
    """Compute topology, and persist a tidy trip-graph frame to parquet."""
    ordering = build_route_topology(tickets)
    rows = []
    for key, ranks in ordering.items():
        route, direction = key
        for stop, rank in ranks.items():
            rows.append({"route": route, "direction": direction,
                         "stop_norm": stop, "rank": int(rank)})
    df = pd.DataFrame(rows, columns=["route", "direction", "stop_norm", "rank"])
    df.to_parquet(TRIP_GRAPH_PARQUET, index=False)
    return ordering


def load_topology() -> Dict[Tuple[str, str], Dict[str, int]]:
    """Re-hydrate topology ordering from the parquet cache."""
    if not TRIP_GRAPH_PARQUET.exists():
        raise FileNotFoundError(
            "Trip-graph cache missing — run scripts/build_processed.py first."
        )
    df = pd.read_parquet(TRIP_GRAPH_PARQUET)
    if len(df) == 0:
        return {}
    out: Dict[Tuple[str, str], Dict[str, int]] = {}
    for (route, direction), sub in df.groupby(["route", "direction"], sort=False):
        out[(route, direction)] = dict(zip(sub["stop_norm"], sub["rank"].astype(int)))
    return out
