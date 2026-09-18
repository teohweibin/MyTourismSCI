# Dashboard Data Dictionary

Spec for the Power BI dashboard build. All file paths are relative to the
`mytourismsci/` project root. CSV versions of all data files are available
at `outputs/csv/` for Power BI convenience; parquet remains canonical.

---

## 1. Primary Data Files

### `outputs/mytourismsci_scores.parquet`

Headline composite scores. One row per state-year (96 rows).

| Column | Type | Description |
|--------|------|-------------|
| `state_code` | string | 3-letter state code (JOH, KDH, KTN, MLK, NSN, PHG, PNG, PRK, PLS, SGR, TRG, SBH, SWK, KUL, LBN, PJY) |
| `year` | int | 2020–2025 |
| `economic_score` | float | Normalised Economic pillar score (0–1) |
| `environmental_score` | float | Normalised Environmental pillar score (0–1) |
| `social_score` | float | Normalised Social pillar score (0–1) |
| `mytourismsci_score` | float | Geometric-mean composite index (0–1) |
| `rank` | int | State rank by `mytourismsci_score` within year (1 = best) |
| `median_rank` | float | Median rank across 1 000 Monte Carlo weight draws |
| `rank_5th` | float | 5th-percentile rank (optimistic bound) |
| `rank_95th` | float | 95th-percentile rank (pessimistic bound) |
| `rank_stability` | float | Fraction of Monte Carlo draws where rank equals base-case rank |

### `data/final/state_year_indicators.parquet`

Wide-format indicator table. One row per state-year (96 rows, 24 indicator
columns). Use for driver drill-down — lets users see which raw indicators
drive a state's score.

| Column | Type | Pillar | Description |
|--------|------|--------|-------------|
| `state_code` | string | — | 3-letter state code |
| `year` | int | — | 2020–2025 |
| `alos_nights` | float | Economic | Average length of stay (nights) |
| `avg_expenditure_rm` | float | Economic | Average expenditure per trip (RM) |
| `domestic_visitors_000` | float | Social | Domestic visitors (thousands) |
| `tourism_receipts_rm_mil` | float | Economic | Tourism receipts (RM millions) |
| `tourism_trips_000` | float | Economic | Tourism trips (thousands) |
| `dts_hotels_count` | float | Economic | Hotels counted in DTS |
| `dts_rooms_count` | float | Economic | Hotel rooms counted in DTS |
| `population` | float | Social | State population (thousands); NaN for 2024–2025 |
| `hh_water_access` | float | Social | % households with piped water |
| `wqi_annual` | float | Environmental | Mean Water Quality Index |
| `n_rivers` | float | Environmental | Number of monitored rivers |
| `waste_tonnes` | float | Environmental | Construction waste disposed (tonnes); sparse |
| `coastal_area_fraction` | float | Environmental | Fraction of state area within 10 km of coast |
| `pa_area_fraction` | float | Environmental | Fraction of state area covered by protected areas |
| `estimated_coastal_hotels` | int | Environmental | Hotels estimated within coastal buffer |
| `estimated_pa_hotels` | int | Environmental | Hotels estimated within PA buffer |
| `motac_hotels_rated_count` | int | Social | MOTAC-rated hotels |
| `green_hotel_count` | float | Environmental | ASEAN Green Hotel–certified hotels; NaN if none |
| `tourism_concentration_ratio` | float | Economic | Visitors / population |
| `expenditure_per_visitor` | float | Economic | RM per visitor |
| `hotel_density_per_capita` | float | Social | Hotels per 100 000 population |
| `green_hotel_share` | float | Environmental | Green hotels / total rated hotels |
| `international_arrivals_share` | float | Economic | NaN (no state-level data available) |

### `data/final/state_year_indicators_long.parquet`

Long format (2 208 rows). Better for pillar-filtered slicers and
indicator-comparison visuals in Power BI.

| Column | Type | Description |
|--------|------|-------------|
| `state_code` | string | 3-letter state code |
| `year` | int | 2020–2025 |
| `indicator_name` | string | Indicator column name from the wide table |
| `value` | float | Indicator value |
| `pillar` | string | `economic`, `environmental`, or `social` |

### `data/processed/geospatial/state_geospatial_indicators.parquet`

Static geospatial pressure metrics (16 rows, one per state).

| Column | Type | Description |
|--------|------|-------------|
| `state_code` | string | 3-letter state code |
| `coastal_area_fraction` | float | Fraction of state area within coastal buffer |
| `pa_area_fraction` | float | Fraction of state area under protected-area coverage |
| `total_hotels` | int | Total OSM-sourced hotel count |
| `estimated_coastal_hotels` | int | Hotels within coastal buffer |
| `estimated_pa_hotels` | int | Hotels within PA buffer |

### `data/raw/geospatial/dosm_boundaries/states.geojson.zip`

DOSM Kawasanku state boundary polygons. Unzip and load in Power BI for
the choropleth map visual. Geometry is in WGS84 (EPSG:4326).

### `data/processed/policy_commitments.parquet`

LLM-extracted policy commitments (51 rows). Used on Page 4 (Policy Watch).

| Column | Type | Description |
|--------|------|-------------|
| `source_doc` | string | Source document name (e.g., RMK13, state master plan) |
| `source_page` | int | Page number in source PDF |
| `state` | string | State name or "National" |
| `commitment_type` | string | Type of commitment (target, strategy, allocation) |
| `target_value` | float | Quantitative target value |
| `target_unit` | string | Unit of target (e.g., "million arrivals", "RM billion") |
| `target_year` | int | Target year for the commitment |
| `baseline_value` | float | Baseline value (if stated) |
| `baseline_year` | int | Baseline year (if stated) |
| `sustainability_dimension` | string | Mapped sustainability dimension |
| `verbatim_quote` | string | Verbatim excerpt from source document |
| `confidence` | string | Extraction confidence: `high`, `medium`, or `low` |

---

## 2. Recommended Dashboard Architecture (4 pages)

### Page 1 — Executive Overview

- **National KPI tiles**: national average MyTourismSCI (2025), year-on-year
  change, number of states improving
- **State choropleth map**: states coloured by `mytourismsci_score` for the
  selected year (default 2025), using the DOSM boundary GeoJSON
- **Top / bottom 5 leaderboard**: horizontal bar chart showing highest and
  lowest scoring states

### Page 2 — State Deep Dive

- **State filter** (single-select slicer)
- **Pillar sub-score line chart**: `economic_score`, `environmental_score`,
  `social_score` over 2020–2025 for the selected state
- **Indicator drill-down table**: from the long-format table, filtered to
  selected state + year, grouped by pillar; shows each indicator name and
  value

### Page 3 — Sustainability Diagnosis

- **Pillar comparison heatmap**: states (rows) × pillars (columns), cell
  colour intensity = score value; 2025 default, year-selectable
- **Sensitivity ribbon chart**: for each state, plot `median_rank` as the
  centre line with a ribbon from `rank_5th` to `rank_95th` — shows which
  states have stable vs. volatile rankings under weight perturbation
- **Coastal / PA overlay** (optional): if mapping is feasible, overlay
  `coastal_area_fraction` and `pa_area_fraction` on the state map as a
  bivariate layer

### Page 4 — Policy Watch

- **Commitments table**: from `policy_commitments.parquet`, showing
  `state`, `commitment_type`, `target_value` + `target_unit`,
  `target_year`, `sustainability_dimension`, `confidence`
- **Gap indicator**: where a commitment has a `target_year` ≤ 2025 and a
  corresponding indicator exists, show current value vs. target as a
  bullet chart or progress bar
- **Source citation**: tooltip or detail row showing `verbatim_quote` and
  `source_doc` + `source_page`

---

## 3. Key Visuals

| Visual | Data source | Notes |
|--------|-------------|-------|
| State choropleth | `mytourismsci_scores.parquet` + GeoJSON | Colour by `mytourismsci_score`; use sequential palette |
| Grouped bar (pillar sub-scores) | `mytourismsci_scores.parquet` | 3 bars per state: economic, environmental, social |
| Line chart (rank trajectory) | `mytourismsci_scores.parquet` | `rank` by `year`, one line per state; invert y-axis (rank 1 at top) |
| Heatmap (state × pillar) | `mytourismsci_scores.parquet` | Conditional formatting on cell values |
| Sensitivity ribbon | `mytourismsci_scores.parquet` | Centre = `median_rank`, band = `rank_5th` to `rank_95th` |
| Indicator drill-down | `state_year_indicators_long.parquet` | Filter by pillar slicer |

Pre-rendered figures are also available in `outputs/figures/`:
- `composite_heatmap_2025.png` — state × pillar heatmap
- `rank_trajectory_2020_2025.png` — rank lines for all states

These can be embedded directly in the report if preferred over Power BI
recreations.

---

## 4. Filters

| Filter | Applies to | Values |
|--------|-----------|--------|
| Year | All pages | 2020, 2021, 2022, 2023, 2024, 2025 (default: 2025) |
| State | Page 2 primarily; cross-filter on others | 16 states by `state_code` |
| Pillar | Page 2 drill-down, Page 3 heatmap | Economic, Environmental, Social |

---

## 5. Design Cues

- **Colour palette**: use a colorblind-safe sequential palette (viridis or
  ColorBrewer "YlGnBu") for choropleth and heatmap. For categorical state
  comparisons, assign a consistent colour key to each state across all
  pages.
- **Pillar colours**: use a fixed 3-colour categorical scheme for the
  pillars (e.g., blue = Economic, green = Environmental, orange = Social)
  and maintain consistently across all visuals.
- **Tooltips**: show the verbatim indicator name and a short methodology
  description on hover (source these from `config/indicators.yaml`
  descriptions if available).
- **Number formatting**: scores to 3 decimal places; ranks as integers;
  monetary values with RM prefix and comma separators.
- **Rank axis**: always invert y-axis for rank visuals (1 at top).

---

## 6. Publishing

1. Build in Power BI Desktop (`.pbix` file saved to `dashboard/`)
2. Publish to Power BI Service (team workspace)
3. Generate a public sharing link
4. Paste the link into the report (Section 5: Dashboard) and the
   submission form
