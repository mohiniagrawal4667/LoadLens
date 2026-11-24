# LoadLens — Crowdedness-aware journey planner for Delhi buses

> **Hackathon submission for Transport Stack 2026 · Problem 2**
> Built end-to-end from the October 2026 ONDC e-ticketing stream.

LoadLens estimates **historical passenger demand on every consecutive bus
route segment** in Delhi during October 2026 and uses it to compare direct
journey options between any two stops.

> **No capacity or live occupancy is ever claimed.** Every figure is a
> *historical ticket-derived demand signal* computed strictly from the active
> ticket dataset (and optional supplied GTFS files). Live occupancy, seat
> availability, and per-vehicle loads are never fabricated.

---

## Highlights

* **Zero-fabrication guarantee:** Every metric, chart, and table comes directly
  from the active ticket CSV/Parquet (and supplied GTFS feed when present).
* **Full pipeline & in-UI upload:** Ingests raw October CSV/Parquet via UI
  upload, `LOADLENS_TICKETS`, `data/raw/`, or cached Parquet (`data/cache/`).
* **Auto-fallback sample:** Ships with a 25,000-row sample in
  `data_sample/tickets_sample.csv` so `streamlit run app.py` launches cleanly
  in one command without requiring the ~290 MB full dataset.
* **Five-page Streamlit dashboard:** Overview · Route Analytics · Segment
  Explorer · Journey Planner · Data Quality.
* **Optional GTFS integration:** Drop `stops.txt`, `routes.txt`, `trips.txt`,
  `stop_times.txt` into `data/gtfs/` (or upload a GTFS `.zip` in the sidebar)
  to enable real scheduled durations from `stop_times.txt`. When GTFS is
  missing, scheduled durations and multi-leg transfers are gracefully disabled.

---

## Quick start

### 1. Install Python 3.10+ and dependencies

```bash
cd Loadlens
python -m pip install -r requirements.txt
```

Tested with Python 3.14.3 and the pinned versions in `requirements.txt`:

```
pandas==2.3.3   pyarrow==23.0.0   numpy==2.3.3
streamlit==1.54.0   plotly==7.1.0   networkx==3.7
python-dateutil==2.9.0.post0   pytz==2025.2
```

### 2. Launch the dashboard (one command)

```bash
streamlit run app.py
```

Or on Windows / Linux / macOS:

```bash
run.bat      # Windows
./run.sh     # Linux / macOS
```

Visit <http://localhost:8501>. Out of the box, LoadLens runs on the bundled
25,000-row sample (`data_sample/tickets_sample.csv`) and computes topology and
segment loads directly from it.

To run on the full October dataset:
- **Option A (UI):** Expand **Upload dataset / GTFS** in the sidebar and
  upload your `.csv` or `.parquet` file.
- **Option B (CLI cache build):** Point `LOADLENS_TICKETS` to your full
  CSV/Parquet (or drop it into `data/raw/`), build caches once, then run
  `streamlit run app.py`:

```bash
python scripts/build_processed.py /path/to/october_tickets.parquet --force
streamlit run app.py
```

### 3. Run validation & tests

```bash
python audit.py              # 10-case strict evaluator & edge-case suite
python scripts/validate.py   # Row accounting, non-neg loads & reconciliation
python smoke_test.py         # Renders all 5 Streamlit pages via AppTest
```

---

## Data honesty — explicit limitations

| Concern | What LoadLens does |
|---|---|
| `created_at` not verified as boarding time | Normalised to IST (`Asia/Kolkata`) and labelled as ticket-creation time on all charts. |
| `vehicle_number` missing on ~45–48% of rows | Records with/without a vehicle ID are aggregated together for route/segment demand. Individual vehicle occupancy and missing vehicle IDs are never fabricated or imputed. |
| `passenger_count` aggregation | Aggregates exact `passenger_count` values without extrapolation; non-positive counts, null core fields, punctuation-only stop names, and `origin == destination` rows are excluded and accounted for. |
| Missing GTFS files | Route topology is reconstructed from observed ticket OD pairs (`start_rank < end_rank`). Scheduled travel durations and multi-leg transfers are disabled (shown as unavailable) unless official GTFS `stops.txt`, `routes.txt`, `trips.txt`, and `stop_times.txt` are supplied. |
| Capacity / "overcrowded" call | Never made. Only 0–1 within-route Relative Load Index and raw passenger-segment volume are displayed. |

---

## Static GTFS integration

1. Create `data/gtfs/` at the repository root (or upload a GTFS `.zip` in the
   sidebar).
2. Place `stops.txt`, `routes.txt`, `trips.txt`, and `stop_times.txt` inside
   `data/gtfs/`.
3. Restart or refresh `streamlit run app.py` — the Journey Planner banner
   switches to green (GTFS active) and computes real scheduled durations from
   `stop_times.txt`.

---

## Repository layout

```
Loadlens/
├── app.py                       # Streamlit entry-point & source router
├── app_pages.py                 # Per-tab renderers (5 pages)
├── audit.py                     # 10-case evaluator & edge-case test suite
├── smoke_test.py                # Headless Streamlit AppTest for all 5 pages
├── requirements.txt
├── README.md
├── run.bat / run.sh             # One-command launchers
├── .gitignore
│
├── src/
│   ├── data_loader.py           # CSV/Parquet ingestion, IST tz fix, cleaning & DQ report
│   ├── topology.py              # Route direction + DAG stop ordering
│   ├── load_engine.py           # Vectorised segment-load aggregator
│   ├── analytics.py             # KPIs, time patterns, route heatmaps
│   ├── gtfs.py                  # Static GTFS validation & scheduled duration lookup
│   ├── journey_planner.py       # Stop autocomplete + direct-option search
│   └── ui_theme.py              # Colour palette + CSS injection
│
├── scripts/
│   ├── build_processed.py       # Cache builder for full datasets
│   ├── make_sample.py           # Sample-data builder
│   ├── validate.py              # Sanity & reconciliation checks
│   └── _stdout_compat.py        # UTF-8 Windows console helper
│
├── data/cache/                  # Generated caches (gitignored)
└── data_sample/                 # Bundled 25k-row sample for immediate launch
```
