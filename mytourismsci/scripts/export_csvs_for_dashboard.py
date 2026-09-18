"""Export parquet files to CSV for Power BI convenience.

Inputs:  outputs/mytourismsci_scores.parquet
         outputs/ao3_gap_analysis.parquet
         data/final/state_year_indicators.parquet
         data/final/state_year_indicators_long.parquet
         data/processed/geospatial/state_geospatial_indicators.parquet
         data/processed/policy_commitments.parquet
Outputs: outputs/csv/*.csv
Dependencies: pandas, pyarrow
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = PROJECT_ROOT / "outputs" / "csv"

EXPORTS = [
    ("outputs/mytourismsci_scores.parquet", "mytourismsci_scores.csv"),
    ("outputs/ao3_gap_analysis.parquet", "ao3_gap_analysis.csv"),
    ("data/final/state_year_indicators.parquet", "state_year_indicators.csv"),
    ("data/final/state_year_indicators_long.parquet", "state_year_indicators_long.csv"),
    ("data/processed/geospatial/state_geospatial_indicators.parquet", "state_geospatial_indicators.csv"),
    ("data/processed/policy_commitments.parquet", "policy_commitments.csv"),
]


def main() -> None:
    OUT_CSV.mkdir(parents=True, exist_ok=True)
    for src_rel, dst_name in EXPORTS:
        src = PROJECT_ROOT / src_rel
        dst = OUT_CSV / dst_name
        df = pd.read_parquet(src)
        df.to_csv(dst, index=False)
        print(f"{src_rel} -> outputs/csv/{dst_name}  ({len(df)} rows)")


if __name__ == "__main__":
    main()
