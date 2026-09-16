# MyTourismSCI — Project Context for Claude Code

## Project Overview

MyTourismSCI is Malaysia's state-level Sustainable Tourism Composite Index,
built for the DOSM (Department of Statistics Malaysia) Datathon 2026.

The project aggregates ~20 indicators across 3 pillars (Economic,
Environmental, Social) — aligned with the UN Tourism Measuring the
Sustainability of Tourism (MST) framework as scoped for Malaysia in the
UNESCAP 2020 study — into a single state-comparable composite index across
Malaysia's 16 states, for the years 2020–2025.

The project is designed as an inheritable artefact for potential DOSM
adoption, supporting the operationalization of Malaysia's UN MST commitment
and RMK13 Strategy A1.10 tourism sustainability mandate.

## Team and Roles

- Data Engineer: data pipeline, geospatial pipeline, annual-refresh script
- Stats/ML Lead: composite index, PCA, Monte Carlo, forecasting, SHAP,
  LLM extraction
- Dashboard Lead: Power BI dashboard, scenario simulator
- Research Lead / Coordinator: benchmarks, validation, coordination, video

## Timeline

- Day 3 (today, 13 Sep 2026): environment setup + ingestion begins
- Days 3–5: ingestion + harmonization
- Day 5: unified table complete; data quality audit
- Days 5–6: AO1 composite index construction + validation
- Days 6–8: AO2 forecast + AO3 LLM policy extraction (parallel)
- Days 8–9: dashboard integration
- Days 9–11: report + video + hostile-judge simulation
- Day 12 (22 Sep 2026): final submission by 5 PM MYT

## Three Analytical Objectives

- AO1: Construct and validate MyTourismSCI, a state-level composite index
  of tourism sustainability aligned to UN MST pillar structure, using
  DOSM-native data + integrated geospatial pressure indicators, following
  international composite-index methodological best practice (OECD/JRC 2008
  Handbook, UNDP HDI methodology, OPHI MPI as adopted by DOSM).

- AO2: Project each state's MyTourismSCI three years forward and diagnose
  state-specific pressures shaping projected change (naive baseline vs.
  ARIMA vs. XGBoost horse-race, SHAP for interpretability).

- AO3: Extract quantitative tourism commitments from Malaysian government
  policy documents (RMK13, state tourism master plans) through structured
  LLM-assisted extraction with human validation, enabling per-state gap
  analysis between sustainability trajectory and committed policy targets.

## Technical Stack

- Python 3.11+
- Data: pandas, numpy, pyarrow (parquet), openpyxl
- Ingestion: requests, beautifulsoup4, pdfplumber, camelot-py
- Geospatial: geopandas, shapely, rtree, pyogrio, contextily
- Stats/ML: scikit-learn, statsmodels, xgboost, shap
- LLM: anthropic (Claude Sonnet 4.5 via API)
- Visualization: matplotlib, plotly (dashboard is Power BI, separate)
- Reproducibility: python-dotenv for secrets, YAML for indicator config

## Data Sources (Malaysian-origin, publicly accessible)

Structured (via API/CSV/parquet):
- OpenDOSM API: https://api.data.gov.my/opendosm
- OpenDOSM storage: https://storage.dosm.gov.my/
- Key catalogue slugs: population_state, population_district,
  water_pollution_basin, water_consumption, hh_access_amenities
- data.gov.my: arrivals, arrivals_soe (immigration)
- Sarawak Open Data (CKAN): catalog.sarawak.gov.my/api/3/action/

Structured but PDF (needs extraction):
- DOSM Domestic Tourism Survey (DTS) by state, 2018–2024
- DOSM Tourism Satellite Account (TSA) 2024, Regional TSA Sabah 2022
- SWCorp waste generation annual reports
- DOE Environmental Quality Reports (WQI)
- Forestry Department annual statistics
- Salaries & Wages Survey reports

HTML scraping:
- MOTAC registered hotels: motac.gov.my/en/check/registered-hotel
- MOTAC registered homestays
- MOTAC ASEAN Green Hotel awardees
- Jabatan Warisan Negara heritage register: heritage.gov.my

Geospatial:
- DOSM Kawasanku boundaries (state + district GeoJSON)
- OpenStreetMap Malaysia (via Geofabrik extract)
- Protected Planet / WDPA (Malaysia protected areas, WGS84)
- JUPEM MyGeoportal, DID flood hazard maps (partial availability)

LLM extraction sources (Malaysian government PDFs):
- RMK13 (Rancangan Malaysia Ke-13)
- MOTAC annual reports
- State tourism master plans (target 6-10 states)

## Coding Conventions

- File organization follows the folder structure in README.md
- Every ingestion script writes raw output to data/raw/ (gitignored)
- Every cleaned output writes to data/processed/ (gitignored)
- Only the final unified table (data/final/state_year_indicators.parquet)
  is committed
- All analysis outputs go to outputs/ (committed)
- Every script has docstring: purpose, inputs, outputs, dependencies
- State codes use canonical form: JOH, KDH, KTN, MLK, NSN, PHG, PNG, PRK,
  PLS, SGR, TRG, SBH, SWK, KUL, LBN, PJY
- Missing values are pandas NA, never -999 or 0
- All computations that could fail silently need validation checks
- All shared indicator definitions live in config/indicators.yaml

## Judge and DOSM Perception

Every code artefact, docstring, and comment must be defensible to a DOSM
Director-level reader. Use passive-neutral institutional language. Never
write comments that criticize DOSM, MOTAC, or any Malaysian agency.
Frame everything as "supporting existing measurement infrastructure."

Every methodological choice must be traceable to:
- OECD/JRC 2008 Handbook (composite index construction), or
- UNDP HDI (geometric mean aggregation), or
- OPHI MPI as adopted by DOSM (sub-national composite), or
- UN Tourism MST framework (pillar structure), or
- WEF T&TDI (external validation reference)

## Non-Negotiable Rules

- Never fabricate data, indicator values, or URLs
- Never commit API keys or credentials
- Never claim novelty without evidence in the novelty verification report
- Never use causal language ("X causes Y") when the analysis supports
  only correlational claims
- Always defer to ARIMA baseline honestly if XGBoost doesn't beat it
- Always validate LLM extractions against source documents (target ≥85%
  precision on stratified sample)