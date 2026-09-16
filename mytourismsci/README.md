# MyTourismSCI

**Malaysia's State-Level Sustainable Tourism Composite Index**

Developed for the Department of Statistics Malaysia (DOSM) Datathon 2026.
Designed as an inheritable artefact for consideration by DOSM in support
of Malaysia's UN Tourism Measuring the Sustainability of Tourism (MST)
commitment and RMK13 Strategy A1.10 tourism sustainability mandate.

---

## Team StatsPower

| Role | Name |
|------|------|
| Data Engineer | [Name] |
| Stats/ML Lead | [Name] |
| Dashboard Lead | [Name] |
| Research Lead / Coordinator | [Name] |

---

## Analytical Objectives

**AO1 — Composite Index Construction.**
Construct and validate MyTourismSCI, a state-level composite index of
tourism sustainability aligned to the UN MST pillar structure, using
DOSM-native data and integrated geospatial pressure indicators, following
international composite-index methodological best practice (OECD/JRC 2008
Handbook, UNDP HDI methodology, OPHI MPI as adopted by DOSM).

**AO2 — State-Level Forecasting.**
Project each state's MyTourismSCI three years forward and diagnose
state-specific pressures shaping projected change (naive baseline vs.
ARIMA vs. XGBoost horse-race, SHAP for interpretability).

**AO3 — Policy Gap Analysis.**
Extract quantitative tourism commitments from Malaysian government policy
documents (RMK13, state tourism master plans) through structured
LLM-assisted extraction with human validation, enabling per-state gap
analysis between sustainability trajectory and committed policy targets.

---

## How to Reproduce

### Environment Setup

```bash
# Clone the repository
git clone <repo-url>
cd mytourismsci

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Running the Pipeline

```bash
# Step 1: Data ingestion — OpenDOSM API
python -m src.ingestion.opendosm_api

# Step 2: Harmonisation
# python -m src.harmonization.build_unified_table

# Step 3: Analysis
# python -m src.analysis.ao1_composite_index
# python -m src.analysis.ao2_forecast
# python -m src.analysis.ao3_llm_extraction

# Step 4: Dashboard export
# python -m src.dashboard.data_export
```

### Running Tests

```bash
pytest tests/ -v
```

---

## Repository Structure

```
mytourismsci/
├── config/              # Indicator definitions (indicators.yaml)
├── data/
│   ├── raw/             # Raw ingested data (gitignored)
│   ├── processed/       # Cleaned and harmonised data (gitignored)
│   └── final/           # Unified state-year table (committed)
├── src/
│   ├── ingestion/       # Data ingestion: API, PDF, HTML, geospatial
│   ├── harmonization/   # State code mapping, unified table builder
│   ├── analysis/        # AO1 composite index, AO2 forecast, AO3 LLM
│   └── dashboard/       # Power BI data export utilities
├── outputs/             # Analysis outputs and figures (committed)
├── report/              # Final report draft and appendices
├── dashboard/           # Power BI dashboard files
├── docs/                # Methodology documentation
│   └── policy_documents/  # Source PDFs for AO3 (gitignored)
└── tests/               # Unit and integration tests
```

---

## Data Sources

All data sources are Malaysian-origin and publicly accessible. A
comprehensive listing is maintained in `docs/data_availability_report.md`.
Key sources include:

- **OpenDOSM API** and DOSM storage (population, water quality, amenities)
- **DOSM surveys** (Domestic Tourism Survey, Tourism Satellite Account,
  Salaries & Wages Survey)
- **data.gov.my** (international arrivals by entry point)
- **MOTAC** (registered hotels, homestays, ASEAN Green Hotel awardees)
- **DOE** (Environmental Quality Reports, Water Quality Index)
- **Jabatan Warisan Negara** (national heritage register)
- **WDPA / Protected Planet** (protected area boundaries)
- **DOSM Kawasanku** (state and district boundary GeoJSON)
- **OpenStreetMap** Malaysia extract (tourism POI density)

Full data source documentation and availability status are provided in
Appendix A of the final report.

---

## Deliverables

- [ ] Final report (PDF): `report/draft.md` (rendered)
- [ ] Interactive dashboard: [Dashboard URL placeholder]
- [ ] Presentation video: [Video URL placeholder]

---

## Acknowledgements

Built for DOSM Datathon 2026. Analysis pipeline developed with
Claude Code assistance.

Methodological framework draws on the OECD/JRC (2008) Handbook on
Constructing Composite Indicators, UNDP Human Development Index
methodology, OPHI Multidimensional Poverty Index (as adopted by DOSM),
and the UN Tourism MST framework.
