# MyTourismSCI

**A state-level Sustainable Tourism Composite Index for Malaysia**

MyTourismSCI is a composite index of tourism sustainability for Malaysia's
16 states and federal territories, covering 2020–2025. It was built by
Team StatsPower for the Department of Statistics Malaysia (DOSM) Datathon
2026. It is designed as an inheritable artefact that supports the
operationalisation of Malaysia's UN Tourism *Measuring the Sustainability
of Tourism* (MST) commitment and the RMK13 tourism sustainability mandate.

The index groups indicators into three pillars (Economic, Environmental,
Social). The pillars follow the UN Tourism MST framework as scoped for
Malaysia in the UNESCAP (2020) study. Construction choices trace to the
OECD/JRC (2008) *Handbook on Constructing Composite Indicators* and the
UNDP HDI geometric-mean aggregation.

---

## Analytical Objectives

| | Objective | Status |
|---|---|---|
| **AO1** | Construct and validate the composite index (normalisation, pillar aggregation, PCA coherence check, Monte Carlo weight sensitivity) | Implemented — `src/analysis/ao1_composite_index.py` |
| **AO2** | Forecast each state's score three years ahead (naive vs. ARIMA vs. XGBoost) with SHAP driver diagnosis | Specified in `docs/ao2_spec.md`; module is a stub |
| **AO3** | Extract quantitative commitments from government policy documents and compare them with observed indicator trajectories | Implemented — `src/analysis/ao3_llm_extract.py`, `src/analysis/ao3_gap_analysis.py` |

---

## Repository Layout

```
.
├── CLAUDE.md                     # Project context and conventions for Claude Code
└── mytourismsci/                 # Project root (run all commands from here)
    ├── config/                   # Indicator definitions, PDF keyword sets, commitment JSON schema
    ├── data/
    │   ├── raw/                  # Downloaded source files (gitignored)
    │   ├── processed/            # Cleaned intermediate parquets, PDF triage JSON, policy commitments
    │   └── final/                # Unified state-year indicator table (wide + long)
    ├── src/
    │   ├── ingestion/            # OpenDOSM API, DTS/TSA Excel, MOTAC scraper, PDF triage/extraction, geospatial
    │   ├── harmonization/        # Canonical state codes, unified table builder
    │   ├── analysis/             # AO1 composite index, AO2 (stub), AO3 extraction + gap analysis
    │   └── dashboard/            # Dashboard export helpers (stub)
    ├── scripts/                  # PDF triage runner, OCR re-run, DTS/TSA quality report, CSV export
    ├── outputs/                  # Scores, validation reports, figures, AO3 briefs, CSV exports
    ├── docs/                     # Methodology, handoff, AO2 spec, dashboard data dictionary, benchmarks
    ├── report/                   # Report draft and bibliography
    ├── dashboard/                # Power BI files (placeholder)
    └── tests/                    # pytest suite
```

State codes everywhere use the canonical three-letter form:
`JOH KDH KTN MLK NSN PHG PNG PRK PLS SGR TRG SBH SWK KUL LBN PJY`.

---

## Data Sources

All sources are Malaysian-origin and publicly accessible.

| Source | Used for |
|---|---|
| OpenDOSM API (`population_state`, `hh_access_amenities`, `water_consumption`) and data.gov.my (`arrivals`) | Population, household piped-water access |
| DOSM Domestic Tourism Survey (state Excel tables, 2020–2025) | Visitors, trips, receipts, length of stay, hotels/rooms |
| DOSM Tourism Satellite Account (national Excel tables) | National context and cross-checks |
| DOE Environmental Quality Reports (PDF) | River Water Quality Index by state |
| SWCorp annual report (PDF) | Waste by state (7 states, 2022) |
| MOTAC registries (web) | Registered, rated and green-certified hotels; ASEAN Green Hotel awardees |
| DOSM Kawasanku boundaries, WDPA / Protected Planet | Coastal and protected-area buffer fractions |
| RMK13, MOTAC Annual Report 2024, state tourism master plans (PDF) | AO3 policy commitments |

---

## Key Outputs

| File | Contents |
|---|---|
| `data/final/state_year_indicators.parquet` | Unified wide table: 96 rows (16 states × 2020–2025) |
| `data/final/state_year_indicators_long.parquet` | Same data in long format with pillar labels |
| `outputs/mytourismsci_scores.parquet` | Pillar scores, composite score, rank, Monte Carlo rank bands |
| `outputs/pillar_pca_validation.md` | Within-pillar PCA coherence check |
| `outputs/monte_carlo_summary.md` | Rank sensitivity to pillar weights (1,000 Dirichlet draws) |
| `outputs/figures/` | 2025 pillar heatmap, 2020–2025 rank trajectory |
| `data/processed/policy_commitments.parquet` | 51 extracted policy commitments with page citations |
| `outputs/ao3_gap_analysis.parquet` | Commitments mapped to indicators, with gap status |
| `outputs/state_briefs/`, `outputs/ao3_national_synthesis.md` | AO3 per-state briefs and national synthesis |
| `outputs/csv/` | CSV copies of the main parquets for Power BI / Excel |

Column-level definitions are in `mytourismsci/docs/dashboard_data_dictionary.md`.

---

## Getting Started

Requires Python 3.11+.

```bash
cd mytourismsci
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
cp .env.example .env              # only needed for LLM API calls
pytest
```

OCR fallback for scanned PDFs needs a local Tesseract install (see
`src/ingestion/pdf_triage.py`).

### Running the pipeline

Run from inside `mytourismsci/`. Raw inputs (DTS/TSA Excel files, PDFs,
WDPA and boundary archives) must be placed under `data/raw/` first. They
are not committed.

```bash
# 1. Ingestion
python -m src.ingestion.opendosm_api
python -m src.ingestion.excel_ingest
python -m src.ingestion.motac_scraper
python scripts/run_pdf_triage.py              # required before any PDF extraction
python -m src.ingestion.pdf_extract_deterministic
python -m src.ingestion.geospatial_ingest

# 2. Harmonisation
python -m src.harmonization.build_unified_table

# 3. Analysis
python -m src.analysis.ao1_composite_index
python -m src.analysis.ao3_llm_extract                 # extract target-page text
python -m src.analysis.ao3_llm_extract consolidate     # merge commitment JSON into parquet
python -m src.analysis.ao3_gap_analysis

# 4. Dashboard convenience exports
python scripts/export_csvs_for_dashboard.py
```

Processed parquets and the final tables are committed, so you can run the
analysis steps (3–4) without re-running ingestion.

---

## Methodology Summary

1. **Indicator screening:** indicators with more than 30% missing cells are
   excluded; remaining gaps are filled with the within-state mean.
2. **Outlier treatment:** winsorisation at the 1st/99th percentile within
   each year.
3. **Normalisation:** min-max to [0, 1] within each year.
4. **Pillar aggregation:** geometric mean of normalised indicators.
5. **Composite:** weighted geometric mean of pillars (Economic 0.40,
   Environmental 0.35, Social 0.25).
6. **Validation:** within-pillar PCA (first component ≥ 40% threshold) and
   Monte Carlo weight perturbation.

Further detail: `docs/methodology.md`, `docs/harmonization_methodology.md`,
`docs/benchmarks.md`.

### AO3 extraction approach

PDF triage identifies target pages by keyword before any extraction.
Only those pages are converted to text. Commitments were then structured
into JSON against `config/policy_commitment_schema.json`, with a source
page and verbatim quote for every record. In this version, Claude Code
did the structuring in-session rather than through API calls.

---

## Known Limitations

Documented in full in `mytourismsci/docs/HANDOFF.md` (Section 5) and
`outputs/ao3_national_synthesis.md`. In brief:

- Population is available only through 2023, so per-capita indicators are
  missing for 2024–2025.
- State-level international arrivals are unavailable.
- SWCorp waste data covers 7 states for one year.
- Forestry, Salaries & Wages and homestay sources are not yet integrated.
- Geospatial and MOTAC indicators are single snapshots replicated across
  years.
- Only 4 of 51 extracted commitments map to an observed indicator. All 4
  are Economic. Growth rates use a 2020 (COVID-affected) base year.

---

## Project Documents

- `CLAUDE.md` — project context, conventions and non-negotiable rules
- `mytourismsci/docs/HANDOFF.md` — current state and role-by-role pathways
- `mytourismsci/docs/ao2_spec.md` — AO2 execution spec
- `mytourismsci/docs/dashboard_data_dictionary.md` — schemas and dashboard layout
- `mytourismsci/README.md` — project-level README

---

## Acknowledgements

Built for the DOSM Datathon 2026 by Team StatsPower. Analysis pipeline
developed with Claude Code assistance. Methodological references: OECD/JRC
(2008), UNDP HDI Technical Notes, OPHI MPI as adopted by DOSM, UN Tourism
MST framework, and UNESCAP (2020).
