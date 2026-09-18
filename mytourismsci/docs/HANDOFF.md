# MyTourismSCI — Weekend Handoff

Last updated: 19 Sep 2026 (Day 7 of datathon)

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
| 18 Sep     | `1845f4b` | Handoff docs + dashboard data dictionary for weekend execution    |
| 19 Sep     | `074d52f` | ✅ AO3 policy-commitment gap analysis: 4 of 51 commitments mapped, state briefs + national synthesis in `outputs/` |
| 19 Sep     | `c075f0d` | ✅ CSV versions of all key parquets available at `outputs/csv/` for teammates using Excel/Power BI without native parquet support |

### Remaining work

- **AO2 — Forecasting** (spec in `docs/ao2_spec.md`, Stats/ML Lead):
  naive baseline, ARIMA, XGBoost horse-race; SHAP interpretability;
  3-year projection per state; WEF T&TDI validation. Highest-priority
  analytical task remaining.
- **Dashboard** (Dashboard Lead): Power BI build (see
  `docs/dashboard_data_dictionary.md`). All data files ready including
  CSV exports.
- **Report Sections 4, 5, 6** (Research Lead): Section 4 (AO2 + AO3
  findings integration), Section 5 (dashboard link + walkthrough),
  Section 6 (synthesis + limitations). Sections 1, 2, 3, 7 are drafted.
- **Video**: 5-min presentation video (due Day 12).

---

## Quick Start by Role

Find your role below and follow the numbered pathway. Every file path is
clickable in most editors (VS Code, GitHub web). Everything you need is
in this repo — no need to ask the primary developer during the weekend.

---

### For the Stats/ML Lead (executing AO2)

**Your one-line mission:** produce a 3-year forecast (2026–2028) of
MyTourismSCI per state + SHAP-based driver diagnosis + WEF T&TDI
national validation.

**Pathway:**

1. **Read first (10 min context):** `docs/ao2_spec.md` — this is your
   full step-by-step execution spec, written specifically for you
2. **Then skim (5 min):** `docs/harmonization_methodology.md` — explains
   how the input data was assembled
3. **Then skim (5 min):** `outputs/pillar_pca_validation.md` and
   `outputs/monte_carlo_summary.md` — AO1 methodology sanity so you
   don't accidentally re-derive it

**Your input files:**
- `outputs/mytourismsci_scores.parquet` — MyTourismSCI scores 2020–2025
  per state (this is what you forecast)
- `data/final/state_year_indicators.parquet` — 25 indicator columns per
  state-year (your feature matrix)
- Optional: `outputs/csv/*.csv` if you prefer CSV over parquet

**Your output files (write these):**
- `outputs/mytourismsci_forecast.parquet` — forecasted scores 2026–2028
- `outputs/shap_drivers.parquet` — SHAP values per state x feature
- `outputs/model_comparison.md` — MAE comparison of baseline/ARIMA/XGBoost
- `outputs/figures/forecast_trajectory.png` — 16-state line chart with CI
  ribbons
- `outputs/wef_ttdi_validation.md` — national aggregate vs WEF trajectory

**Where your outputs get consumed:**
- `outputs/mytourismsci_forecast.parquet` -> Dashboard Lead (Page 3),
  Research Lead (Section 4)
- `outputs/shap_drivers.parquet` -> Research Lead (Section 4
  driver-diagnosis narrative)
- `outputs/wef_ttdi_validation.md` -> Research Lead (Section 3.7
  validation subsection)

**Deadline:** Monday 22 Sep 6:00 PM MYT

---

### For the Dashboard Lead (building Power BI dashboard)

**Your one-line mission:** build a live-hosted 4-page Power BI dashboard
visualising MyTourismSCI scores, pillar drilldowns, forecasts, and policy
commitments — publish the shareable URL for the report.

**Pathway:**

1. **Read first (10 min context):**
   `docs/dashboard_data_dictionary.md` — full schema of every data file
   you'll import, recommended 4-page architecture, key visuals per page
2. **Then look at (5 min):**
   `outputs/figures/composite_heatmap_2025.png` and
   `outputs/figures/rank_trajectory_2020_2025.png` — reference designs
   already produced by AO1
3. **Then skim (5 min):** the Current State section of `docs/HANDOFF.md`
   to understand the pitch the dashboard supports

**Your input files (all in `data/final/`, `outputs/`, or
`outputs/csv/`):**
- `outputs/mytourismsci_scores.parquet` (or
  `outputs/csv/mytourismsci_scores.csv`) — main index scores + rankings
- `data/final/state_year_indicators.parquet` — wide format for indicator
  drilldown
- `data/final/state_year_indicators_long.parquet` — long format for
  pillar-filtered views
- `data/processed/geospatial/state_geospatial_indicators.parquet` —
  coastal + PA buffer indicators
- `data/raw/geospatial/dosm_boundaries/states.geojson.zip` — state
  polygons for choropleth map
- `data/processed/policy_commitments.parquet` — 51 extracted policy
  commitments (feeds Page 4)
- `outputs/ao3_gap_analysis.parquet` — 4 mappable commitments with gap
  classification (feeds Page 4)
- **After Stats/ML Lead delivers:**
  `outputs/mytourismsci_forecast.parquet` — feeds Page 3 forecast ribbon

**Reading parquets in Power BI:** Get Data -> More -> File -> Parquet. If
parquet import fails, use CSV equivalents in `outputs/csv/`.

**Your output:**
- Published Power BI Service URL (shareable link, no login required)
- Post the URL in team chat AND paste it in `report/draft.md` Section 5

**Where your output gets consumed:**
- Research Lead cites the URL in Section 5 of the report
- Judges will click through the dashboard during evaluation

**Deadline:** Monday 22 Sep 6:00 PM MYT

---

### For the Research Lead (writing Report Sections 4, 5, 6)

**Your one-line mission:** finalise the written report by writing
Findings (Section 4), Dashboard (Section 5), and Conclusion (Section 6).
Sections 1, 2, 3, 7 are already drafted — you may revise them for voice
consistency.

**Pathway:**

1. **Read first (15 min context):** `report/draft.md` — the current
   draft. Sections 1 (Introduction), 2 (Literature Review),
   3 (Methodology), and 7 (References) are already written by the
   primary developer. Read them carefully to understand the analytical
   framework and voice.
2. **Then read (10 min):** `outputs/ao3_national_synthesis.md` — the AO3
   gap analysis findings, including two disclosure paragraphs (Baseline
   Effect + Mappability as a Finding) that you should paraphrase into
   Section 4 or Section 6
3. **Then read (15 min):** all files in `outputs/state_briefs/*.md` —
   per-state briefs for Sarawak, Perlis, KL, Johor, National.
   Direct-quote verbatim quotes from these when writing state case
   narratives in Section 4
4. **After Stats/ML Lead delivers:** read `outputs/model_comparison.md`
   and `outputs/wef_ttdi_validation.md` — these feed Section 4 forecast
   findings and Section 3.7 validation subsection respectively
5. **After Dashboard Lead delivers:** grab the Power BI URL and 2–3
   screenshots for Section 5

**Your input files (read to write):**
- `outputs/mytourismsci_scores.parquet` (or
  `outputs/csv/mytourismsci_scores.csv`) — headline numbers per state
- `outputs/pillar_pca_validation.md` — methodology support for
  Section 3.6
- `outputs/monte_carlo_summary.md` — methodology support for Section 3.7
  (rank stability findings)
- `outputs/ao3_gap_analysis.parquet` (or CSV) — 4 mappable commitments
  with status
- `outputs/state_briefs/*.md` — verbatim quotes + per-state findings
- `outputs/ao3_national_synthesis.md` — synthesis + disclosure paragraphs
- `data/processed/policy_commitments.parquet` — all 51 extracted
  commitments (for context)
- `outputs/figures/*.png` — figures for the report body
- **After Stats/ML Lead delivers:**
  `outputs/mytourismsci_forecast.parquet`,
  `outputs/shap_drivers.parquet`, `outputs/wef_ttdi_validation.md`
- **After Dashboard Lead delivers:** Power BI URL + screenshots

**Your output:**
- `report/draft.md` — the final report, with all sections complete

**Report sections to write:**
- **Section 4 (Findings):** MyTourismSCI 2025 rankings + Sarawak
  Environmental caveat + trajectory patterns 2020–2025 + AO2 forecast
  findings + AO2 SHAP drivers per state + AO3 gap analysis findings
  (paraphrase from `ao3_national_synthesis.md`) + state case narratives
  (using `state_briefs/*.md`)
- **Section 5 (Dashboard):** dashboard URL + purpose of each of the 4
  pages + 2–3 screenshots
- **Section 6 (Conclusion):** synthesis of findings + recommendations to
  DOSM/MOTAC/state agencies + limitations (Sarawak Environmental,
  forestry data gap, salaries deferred, homestay deferred, AO3
  mappability) + future work

**Verification tasks in Section 7 (References):**
Look for `[YEAR — VERIFY]` and `[JOURNAL NAME — VERIFY]` flags — these
are load-bearing and MUST be resolved before submission. Full checklist
at end of Section 7.

**Deadline:** Monday 22 Sep 11:00 PM MYT (leaves 18 hours for final
polish before Tuesday 5 PM submission)

---

### For whoever owns the video (10-minute demonstration video)

If nobody is assigned yet, this is highest-risk. Someone must own it by
Sunday.

**Pathway:**
1. Read the Current State section of `docs/HANDOFF.md`
2. Watch the dashboard once Dashboard Lead publishes URL
3. Skim `report/draft.md` Section 4 for the headline findings

**Recommended structure (10 min):**
- 0:00–1:00 — problem statement (from Report Section 1.2)
- 1:00–2:00 — MyTourismSCI concept + 3-pillar structure
- 2:00–4:00 — data pipeline walkthrough (screenshot from HANDOFF.md's
  repo layout)
- 4:00–6:00 — key findings (from Section 4)
- 6:00–8:00 — dashboard demo (live)
- 8:00–10:00 — policy implications + DOSM inheritance story

**Deadline:** Tuesday 22 Sep 3:00 PM MYT (2 hours before submission)

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
| `outputs/ao3_gap_analysis.parquet` (CSV: `outputs/csv/ao3_gap_analysis.csv`) | 4 mapped commitment gaps: state, commitment_type, target, current, status classification | Research Lead for Section 4, Dashboard Lead for Policy Watch page |
| `outputs/state_briefs/*.md` | Per-state policy gap briefs (KUL, PLS, SWK, JOH, national) with verbatim quotes and source citations | Research Lead for state case narratives |
| `outputs/ao3_national_synthesis.md` | National-level AO3 synthesis: status breakdown, key findings, disclosure paragraphs | Research Lead for Sections 4 and 6 |
| `outputs/csv/*.csv` | CSV versions of all key parquets (scores, indicators, gap analysis, geospatial, policy commitments) | All teammates — Power BI / Excel convenience |

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

9. **AO3 mappability** — Only 4 of 51 extracted policy commitments map to
   observable MyTourismSCI indicators; all 4 fall within the Economic
   dimension (visitor arrivals, tourism receipts). Environmental and
   Social commitments cannot be gap-analysed with the current indicator
   set. See `outputs/ao3_national_synthesis.md` for full disclosure.

10. **Post-COVID CAGR baseline effect** — Observed growth rates in AO3
    gap analysis are computed as CAGR over 2020–2025, which includes the
    COVID-19 nadir as baseline. This inflates apparent growth rates during
    the recovery period. `on_track` classifications should be interpreted
    with this baseline effect in mind. Disclosed in
    `outputs/ao3_national_synthesis.md`.

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
- **Mon 21 Sep 6:00 PM MYT**: Stats/ML AO2 deliverables due (forecast + SHAP + WEF validation)
- **Mon 21 Sep 6:00 PM MYT**: Dashboard due (Power BI published link)
- **Mon 21 Sep 11:00 PM MYT**: Report Sections 4, 5, 6 due (Research Lead)
- **Tue 22 Sep**: report + video finalisation (hard freeze)
- **Tue 22 Sep 5:00 PM MYT**: final submission
