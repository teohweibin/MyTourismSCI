# MyTourismSCI — Weekend Handoff

Last updated: 18 Sep 2026 (Day 6 of datathon)

---

## 1. Current State

### Completed (committed)

| Date       | SHA       | What                                                              |
|------------|-----------|-------------------------------------------------------------------|
| 16 Sep     | `8f650df` | OpenDOSM ingestion + state-code harmonisation                     |
| 17 Sep     | `b2f5502` | DTS state Excel and TSA national Excel ingestion                  |
| 17 Sep     | `9684444` | PDF triage utility (keyword-based target-page identification)     |
| 17 Sep     | `58fc9c7` | OCR fallback for scanned PDFs; 4 priority documents recovered     |
| 18 Sep     | `5e2b7a8` | MOTAC hotels (registered/rated/green) + ASEAN Green Hotel scraper |
| 18 Sep     | `ba46a3c` | PDF triage for Johor, Sabah, Sarawak master plans                 |
| 18 Sep     | `c3fb1b5` | Processed parquets + triage JSON tracked for teammate access      |
| 18 Sep     | `c0bfa2f` | DOE WQI range-filter fix + SWCorp waste table detection fix       |
| 18 Sep     | `cf9bfcd` | AO3 policy commitment extraction (Path B, Claude Code as LLM)    |
| 18 Sep     | `e61f17d` | Geospatial indicators via state-buffer aggregation                |
| 18 Sep     | `e7421a6` | Harmonise all processed parquets into unified state-year table    |
| 18 Sep     | `4de91a7` | AO1 composite index + PCA validation + Monte Carlo sensitivity    |

### Remaining work

- **AO2 — Forecasting** (spec in `docs/ao2_spec.md`): naive baseline,
  ARIMA, XGBoost horse-race; SHAP interpretability; 3-year projection per
  state. This is the highest-priority analytical task.
- **AO3 — Gap analysis**: compare extracted policy commitments
  (`data/processed/policy_commitments.parquet`) against current
  MyTourismSCI trajectories; produce per-state gap table and visuals.
- **Dashboard**: Power BI build (see `docs/dashboard_data_dictionary.md`).
- **Report**: draft in `report/draft.md`; needs methodology write-up,
  results narrative, visuals, limitations section, bibliography.
- **Video**: 5-min presentation video (due Day 12).

---

## 2. Repo Layout

`src/` contains all Python source organised into subpackages: `ingestion/`
(OpenDOSM API, Excel, PDF, MOTAC scraper, geospatial), `harmonization/`
(state-code mapping, unified-table builder), `analysis/` (AO1 composite
index, AO2 forecast, AO3 LLM extraction), and `dashboard/` (data-export
helpers). `data/` holds three tiers — `raw/` (gitignored originals),
`processed/` (gitignored cleaned intermediates), and `final/` (committed
unified tables). `outputs/` stores committed analysis artefacts (scores
parquet, PCA/Monte Carlo reports, figures). `config/` has indicator
definitions (`indicators.yaml`) and PDF-triage configuration. `docs/`
holds methodology notes and specs. `tests/` has pytest unit tests.

---

## 3. Getting Started (5 min)

```bash
git clone <repo-url>
cd mytourismsci
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

If `pytest` passes, your environment is ready. The `.env` file (not
committed) is only needed for LLM API calls (AO3); all other pipelines
run without secrets.

---

## 4. Key Data Files

| File | Contents | Primary consumer |
|------|----------|-----------------|
| `data/final/state_year_indicators.parquet` | Wide-format unified table: 96 rows (16 states × 6 years), 24 indicators | AO2 forecast input, dashboard drill-down |
| `data/final/state_year_indicators_long.parquet` | Long format (2 208 rows): `state_code`, `year`, `indicator_name`, `value`, `pillar` | Dashboard pillar-filtered views |
| `outputs/mytourismsci_scores.parquet` | Composite scores: `state_code`, `year`, `economic_score`, `environmental_score`, `social_score`, `mytourismsci_score`, `rank`, `median_rank`, `rank_5th`, `rank_95th`, `rank_stability` | Dashboard headline metric, AO3 gap analysis |
| `data/processed/policy_commitments.parquet` | 51 extracted commitments: `source_doc`, `source_page`, `state`, `commitment_type`, `target_value`, `target_unit`, `target_year`, `baseline_value`, `baseline_year`, `sustainability_dimension`, `verbatim_quote`, `confidence` | AO3 gap analysis |
| `data/processed/geospatial/state_geospatial_indicators.parquet` | Per-state geospatial pressure metrics: `coastal_area_fraction`, `pa_area_fraction`, `total_hotels`, `estimated_coastal_hotels`, `estimated_pa_hotels` | Dashboard map overlays |
| `outputs/pillar_pca_validation.md` | PCA loadings per pillar confirming indicator coherence | Report methodology section |
| `outputs/monte_carlo_summary.md` | Weight-sensitivity analysis; rank stability across 1 000 random weight draws | Report methodology section |
| `outputs/figures/composite_heatmap_2025.png` | State × pillar heatmap for 2025 | Dashboard + report |
| `outputs/figures/rank_trajectory_2020_2025.png` | Rank trajectories 2020–2025 for all 16 states | Dashboard + report |

---

## 5. Known Limitations (Disclose in Report)

1. **Sarawak Environmental pillar underestimation** — The buffer-fraction
   method for coastal and protected-area hotel counts uses a fixed 10 km
   buffer. For geographically large states (especially Sarawak), this
   produces a lower fraction of hotels within buffers relative to total
   area, underestimating environmental pressure. Acknowledge as a
   limitation of the geospatial proxy approach.

2. **Forestry data gap** — The 2024 Forestry Department annual statistics
   PDF is a scanned document. OCR recovery was partial; forest-cover
   indicators are not included in the current composite. If a clean
   source becomes available, it should be added to the Environmental
   pillar.

3. **Salaries & Wages data skipped** — The DOSM Salaries & Wages Survey
   report was deprioritised due to extraction complexity relative to its
   marginal contribution to the Social pillar.

4. **Homestay PDF deferred** — MOTAC homestay data extraction was deferred
   (low priority relative to hotel-based indicators already captured).

5. **Nominatim geocoding fallback** — Due to rate limits on the Nominatim
   API, hotel geocoding fell back to state-level centroid aggregation
   rather than individual address geocoding. This reduces granularity of
   coastal/PA hotel estimates.

6. **Population gap 2024–2025** — OpenDOSM population data is available
   only through 2023. Derived per-capita indicators are NaN for 2024–2025.

7. **Waste data limited coverage** — SWCorp waste data covers only 7
   states for 2022. This indicator has high missingness.

8. **International arrivals** — State-level breakdown unavailable;
   `international_arrivals_share` is NaN for all rows.

---

## 6. Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| Data Engineer / Stats Lead | *(fill in)* | *(WhatsApp / phone)* |
| Dashboard Lead | *(fill in)* | *(WhatsApp / phone)* |
| Research Lead / Coordinator | *(fill in)* | *(WhatsApp / phone)* |

---

## 7. Deadline

**Tuesday 22 September 2026, 5:00 PM MYT** — final submission.

Working backwards:
- Mon 21 Sep: report + video finalisation (hard freeze)
- Sun 20 Sep: dashboard integration complete; draft report ready for review
- Sat 19 Sep: AO2 + AO3 analysis complete; dashboard data handoff
