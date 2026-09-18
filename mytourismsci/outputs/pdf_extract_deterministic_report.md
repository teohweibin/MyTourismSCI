# Deterministic PDF Table Extraction Report

## Summary

- **doe_wqi_by_state_year**: 182 records, 16 states, 12 years
- **swcorp_waste_by_state**: 14 records, 9 states, 2 years

## Per-Source Detail

### doe_wqi_by_state_year

- Years covered: 2014-2025
- States present (16): JOH, KDH, KTN, KUL, LBN, MLK, NSN, PHG, PJY, PLS, PNG, PRK, SBH, SGR, SWK, TRG
- mean_wqi: min=55.78, max=4399.79, mean=101.75, missing=0

**Coverage matrix (states x years):**

|   year |   JOH |   KDH |   KTN |   KUL |   LBN |   MLK |   NSN |   PHG |   PJY |   PLS |   PNG |   PRK |   SBH |   SGR |   SWK |   TRG |
|-------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|
|   2014 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     0 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2015 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     0 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2016 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     0 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2017 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2018 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2019 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2020 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2021 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     0 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2022 |     1 |     1 |     1 |     0 |     1 |     1 |     1 |     1 |     0 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2023 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2024 |     1 |     1 |     1 |     0 |     0 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |
|   2025 |     1 |     1 |     1 |     0 |     0 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |

### swcorp_waste_by_state

- Years covered: 2019-2022
- States present (9): JOH, KDH, KUL, MLK, PHG, PJY, PLS, PRK, TRG
- **Missing states (7)**: KTN, LBN, NSN, PNG, SBH, SGR, SWK
- value: min=1.00, max=68.00, mean=8.71, missing=0

**Warnings:**
- swcorp_waste_by_state: missing 7 states: KTN, LBN, NSN, PNG, SBH, SGR, SWK

**Coverage matrix (states x years):**

|   year |   JOH |   KDH |   KUL |   MLK |   PHG |   PJY |   PLS |   PRK |   TRG |
|-------:|------:|------:|------:|------:|------:|------:|------:|------:|------:|
|   2019 |     1 |     1 |     0 |     1 |     1 |     0 |     1 |     0 |     1 |
|   2022 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     1 |     0 |
