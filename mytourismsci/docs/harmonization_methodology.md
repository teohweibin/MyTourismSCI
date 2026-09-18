# Harmonization Methodology

This document describes how the unified state-year indicator table
(`data/final/state_year_indicators.parquet`) is assembled from the
ingestion pipeline outputs.

## Target Dimensions

- **States:** 16 (all Malaysian states and federal territories)
- **Years:** 2020–2025 (6 years)
- **Expected rows:** 96 (16 × 6)

## Source Mapping

| Source file | Indicators extracted | Coverage |
|---|---|---|
| `dts/dts_jadual1.parquet` | `domestic_visitors_000`, `tourism_receipts_rm_mil`, `tourism_trips_000`, `alos_nights`, `avg_expenditure_rm` | 16 states, 2020–2025 |
| `dts/dts_jadual14_15_hotels.parquet` | `dts_hotels_count`, `dts_rooms_count` (aggregated across star ratings/categories) | 16 states, 2020–2025 |
| `opendosm/population_state_raw.parquet` | `population` (thousands) | 16 states, 2020–2023 |
| `opendosm/hh_access_amenities_raw.parquet` | `hh_water_access` (% households with piped water) | 16 states, survey years 2016/2019/2022/2024 |
| `pdf_tables/doe_wqi_by_state_year.parquet` | `wqi_annual` (mean Water Quality Index), `n_rivers` | 16 states, 2020–2025 |
| `pdf_tables/swcorp_waste_by_state.parquet` | `waste_tonnes` (construction waste disposed) | 7 states, 2022 only |
| `geospatial/state_geospatial_indicators.parquet` | `coastal_area_fraction`, `pa_area_fraction`, `estimated_coastal_hotels`, `estimated_pa_hotels` | 16 states, static |
| `raw/motac/motac_hotels_rated.parquet` | `motac_hotels_rated_count` (count of MOTAC-rated hotels) | 16 states, current snapshot |
| `raw/motac/motac_hotels_green.parquet` | `green_hotel_count` (count of ASEAN Green Hotel–certified hotels) | 8 states, current snapshot |

## Time-Expansion Decisions

Sources without a year dimension are replicated across all 6 target years
(2020–2025). This applies to:

- **Geospatial indicators** (`coastal_area_fraction`, `pa_area_fraction`,
  `estimated_coastal_hotels`, `estimated_pa_hotels`): Geographic features
  are effectively static over this period. Values represent point-in-time
  geospatial analysis using DOSM Kawasanku boundaries, OSM hotel
  locations, and WDPA protected areas.

- **MOTAC hotel counts** (`motac_hotels_rated_count`, `green_hotel_count`):
  The MOTAC registered-hotel register is a current snapshot. These counts
  are replicated across all years as a structural indicator; year-on-year
  changes cannot be captured from a single snapshot.

**Household access amenities** (`hh_water_access`): The source has data
for survey years 2016, 2019, 2022, and 2024 only. For target years, the
nearest preceding survey year is used (forward-fill):
- 2020–2021 ← 2019 survey values
- 2022–2023 ← 2022 survey values
- 2024–2025 ← 2024 survey values

## Derived Indicators

| Indicator | Formula | Notes |
|---|---|---|
| `tourism_concentration_ratio` | `domestic_visitors_000 / population` | Both in thousands; ratio of visitor volume to resident population |
| `expenditure_per_visitor` | `tourism_receipts_rm_mil × 1000 / domestic_visitors_000` | RM per domestic visitor (thousands cancel) |
| `hotel_density_per_capita` | `motac_hotels_rated_count / population × 100` | Hotels per 100,000 population (population in thousands) |
| `green_hotel_share` | `green_hotel_count / motac_hotels_rated_count` | Proportion; 0 for states with no green-certified hotels |
| `international_arrivals_share` | N/A | Source data (`arrivals_soe`) is national-level only — no state breakdown available. Column retained as NaN for future data availability. |

## Missingness Handling

- **Missing values are explicit NaN**, never zero. This is critical to
  distinguish "no data available" from "actual zero."
- `population` is missing for 2024–2025 (OpenDOSM data available through
  2023 only); derived indicators depending on population inherit this gap.
- `waste_tonnes` covers only 7 states for 2022 (SWCorp reporting scope).
- `green_hotel_count` is NaN for 8 states where no ASEAN Green Hotel
  certification exists.
- `international_arrivals_share` is NaN for all rows — the available
  arrivals data lacks state-of-entry disaggregation.

## Pillar Assignment

Each indicator is assigned to one of three pillars aligned with the UN
Tourism MST framework:

- **Economic:** `tourism_receipts_rm_mil`, `expenditure_per_visitor`,
  `alos_nights`, `international_arrivals_share`,
  `tourism_concentration_ratio`, `tourism_trips_000`,
  `avg_expenditure_rm`, `dts_hotels_count`, `dts_rooms_count`
- **Environmental:** `wqi_annual`, `waste_tonnes`,
  `coastal_area_fraction`, `pa_area_fraction`, `green_hotel_share`,
  `green_hotel_count`, `estimated_coastal_hotels`,
  `estimated_pa_hotels`, `n_rivers`
- **Social:** `hotel_density_per_capita`, `hh_water_access`,
  `domestic_visitors_000`, `population`, `motac_hotels_rated_count`

## Output Files

- `data/final/state_year_indicators.parquet` — wide format (96 rows ×
  25 columns), one row per (state_code, year)
- `data/final/state_year_indicators_long.parquet` — long format with
  columns: `state_code`, `year`, `indicator_name`, `value`, `pillar`

## Methodological References

- OECD/JRC (2008). *Handbook on Constructing Composite Indicators*
  — outer-join with explicit NaN follows Section 6 on missing data
  treatment.
- UNDP HDI methodology — geometric mean aggregation (applied downstream
  in AO1, informed by the pillar structure established here).
