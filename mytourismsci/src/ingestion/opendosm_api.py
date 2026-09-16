"""Ingest structured data from the OpenDOSM API and data.gov.my data catalogue.

Fetch strategy (determined via API exploration, 2026-09-16):

    Slug                  Base URL         Filter (server-side)        Rows   Notes
    -------------------   --------------   -------------------------   ----   --------------------------
    population_state      opendosm         overall_age/sex/ethnicity   ~64    16 states x 4 years (2020-23)
    water_consumption     opendosm         (none, filter locally)      ~600   15 entities x 2 sectors x 20yr
    hh_access_amenities   opendosm         All Districts@district      ~64    16 states x 4 survey years
    arrivals              data-catalogue   ALL@country                 ~58    National monthly, no state

    population_district   opendosm         SKIPPED — returns 0 rows (empty catalogue)
    water_pollution_basin opendosm         SKIPPED — 404, catalogue does not exist
    arrivals_soe          data-catalogue   SKIPPED — 404; 'arrivals' used instead (national only)

All working datasets are small (<15K rows) and fit in a single request.
No pagination required.

Inputs:  OpenDOSM API (api.data.gov.my/opendosm), data.gov.my data catalogue
Outputs: Parquet files in data/processed/opendosm/
Dependencies: requests, pandas, pyarrow, tqdm, rich
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from time import sleep

import pandas as pd
import requests
from rich.console import Console
from rich.table import Table

from src.harmonization.state_codes import normalize_state_name

logger = logging.getLogger(__name__)

OPENDOSM_BASE = "https://api.data.gov.my/opendosm"
DATA_GOV_MY_BASE = "https://api.data.gov.my/data-catalogue"
OUTPUT_DIR = Path("data/processed/opendosm")

console = Console()


def fetch_opendosm(
    slug: str,
    params: dict | None = None,
    base_url: str = OPENDOSM_BASE,
    max_retries: int = 2,
) -> pd.DataFrame:
    """Fetch a dataset from the OpenDOSM or data.gov.my API.

    Parameters
    ----------
    slug : str
        Catalogue identifier (e.g. "population_state").
    params : dict, optional
        Additional query parameters (filter, limit, sort).
    base_url : str
        API base URL. Defaults to OpenDOSM; use DATA_GOV_MY_BASE for
        data.gov.my catalogue endpoints.
    max_retries : int
        Number of retry attempts on transient network failures.

    Returns
    -------
    pd.DataFrame
        Raw data as returned by the API.

    Raises
    ------
    requests.HTTPError
        If the API returns a non-200 status after retries.
    ValueError
        If the response is not a list of records.
    """
    query = {"id": slug, "limit": 100_000}
    if params:
        query.update(params)

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Fetching %s (attempt %d/%d)", slug, attempt, max_retries)
            resp = requests.get(base_url, params=query, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                raise ValueError(
                    f"Expected list from API for slug={slug!r}, got {type(data).__name__}: "
                    f"{str(data)[:200]}"
                )
            logger.info("Fetched %s: %d rows", slug, len(data))
            return pd.DataFrame(data)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            logger.warning("Transient error on %s attempt %d: %s", slug, attempt, exc)
            if attempt < max_retries:
                sleep(2 * attempt)
    raise last_exc  # type: ignore[misc]


def save_raw(df: pd.DataFrame, slug: str) -> Path:
    """Save a raw DataFrame to parquet in the OpenDOSM output directory.

    Parameters
    ----------
    df : pd.DataFrame
        Data to save.
    slug : str
        Catalogue slug, used as filename stem.

    Returns
    -------
    Path
        Path to the saved parquet file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{slug}_raw.parquet"
    df.attrs["fetch_timestamp"] = datetime.now().isoformat()
    df.attrs["source_slug"] = slug
    df.to_parquet(path, index=False)
    logger.info("Saved %s (%d rows) to %s", slug, len(df), path)
    return path


def _extract_year(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Add an integer 'year' column derived from a date string column."""
    df = df.copy()
    df["year"] = pd.to_datetime(df[date_col]).dt.year
    return df


def _normalize_states(df: pd.DataFrame, state_col: str = "state") -> pd.DataFrame:
    """Replace raw state names with canonical 3-letter codes.

    Rows with unresolvable state names (e.g. 'Malaysia' national totals)
    are dropped with a warning.
    """
    df = df.copy()
    codes = []
    dropped = []
    for val in df[state_col]:
        try:
            codes.append(normalize_state_name(val))
        except ValueError:
            codes.append(pd.NA)
            dropped.append(val)
    df["state_code"] = codes
    if dropped:
        unique_dropped = sorted(set(str(v) for v in dropped))
        logger.info(
            "Dropped %d rows with unresolvable state names: %s",
            len(dropped),
            unique_dropped,
        )
    df = df.dropna(subset=["state_code"])
    return df


def load_population_state() -> pd.DataFrame:
    """Fetch state-level population totals from OpenDOSM.

    Source: https://api.data.gov.my/opendosm?id=population_state
    Filters to overall age/sex/ethnicity aggregates only.

    Returns
    -------
    pd.DataFrame
        Columns: state_code, year, population (in thousands).
    """
    console.print("[bold]Fetching population_state...[/bold]")
    df = fetch_opendosm(
        "population_state",
        params={"filter": "overall_age@age,overall_sex@sex,overall_ethnicity@ethnicity"},
    )
    if df.empty:
        raise ValueError("population_state returned empty data")

    df = _extract_year(df)
    df = _normalize_states(df)
    df = df[["state_code", "year", "population"]].sort_values(
        ["state_code", "year"]
    ).reset_index(drop=True)
    console.print(f"  [green]{len(df)} rows, {df['year'].min()}-{df['year'].max()}[/green]")
    return df


def load_water_consumption() -> pd.DataFrame:
    """Fetch state-level water consumption from OpenDOSM.

    Source: https://api.data.gov.my/opendosm?id=water_consumption
    Contains domestic and non-domestic sectors. National 'Malaysia' rows
    are dropped. W.P. Kuala Lumpur and W.P. Putrajaya are not present
    in this dataset.

    Returns
    -------
    pd.DataFrame
        Columns: state_code, year, sector, value (million litres/day).
    """
    console.print("[bold]Fetching water_consumption...[/bold]")
    df = fetch_opendosm("water_consumption")
    if df.empty:
        raise ValueError("water_consumption returned empty data")

    df = _extract_year(df)
    df = _normalize_states(df)
    df = df[["state_code", "year", "sector", "value"]].sort_values(
        ["state_code", "year", "sector"]
    ).reset_index(drop=True)
    console.print(f"  [green]{len(df)} rows, {df['year'].min()}-{df['year'].max()}[/green]")
    return df


def load_hh_access_amenities() -> pd.DataFrame:
    """Fetch household access to amenities (sanitation, electricity, piped water).

    Source: https://api.data.gov.my/opendosm?id=hh_access_amenities
    Filters to state-level summaries (district == 'All Districts').
    Survey years: 2016, 2019, 2022, 2024.

    Returns
    -------
    pd.DataFrame
        Columns: state_code, year, sanitation, electricity, piped_water
        (all as percentage values 0-100, or NA if unavailable).
    """
    console.print("[bold]Fetching hh_access_amenities...[/bold]")
    df = fetch_opendosm("hh_access_amenities")
    if df.empty:
        raise ValueError("hh_access_amenities returned empty data")

    # Filter to state-level summaries locally (API filter doesn't support spaces).
    # Four small states/territories (Perlis, KL, Labuan, Putrajaya) lack an
    # "All Districts" summary row because each has only one district — use
    # those district-level rows directly for completeness.
    df = _extract_year(df)
    df = _normalize_states(df)
    has_all = df[df["district"] == "All Districts"][["state_code", "year"]].drop_duplicates()
    has_all["_has_summary"] = True
    df = df.merge(has_all, on=["state_code", "year"], how="left")
    df = df[
        (df["district"] == "All Districts")
        | (df["_has_summary"] != True)  # noqa: E712
    ].drop(columns=["_has_summary"])
    # Deduplicate: if a state somehow has both, prefer "All Districts"
    df = df.sort_values("district").drop_duplicates(
        subset=["state_code", "year"], keep="first"
    )
    df = df[["state_code", "year", "sanitation", "electricity", "piped_water"]].sort_values(
        ["state_code", "year"]
    ).reset_index(drop=True)
    console.print(f"  [green]{len(df)} rows, {df['year'].min()}-{df['year'].max()}[/green]")
    return df


def load_arrivals() -> pd.DataFrame:
    """Fetch national-level international arrivals from data.gov.my.

    Source: https://api.data.gov.my/data-catalogue?id=arrivals
    National monthly totals (country=ALL). Aggregated to annual.
    No state breakdown available from this endpoint.

    Returns
    -------
    pd.DataFrame
        Columns: year, arrivals_total, arrivals_male, arrivals_female.
        One row per year, national-level only.
    """
    console.print("[bold]Fetching arrivals (national, data.gov.my)...[/bold]")
    df = fetch_opendosm(
        "arrivals",
        params={"filter": "ALL@country"},
        base_url=DATA_GOV_MY_BASE,
    )
    if df.empty:
        raise ValueError("arrivals returned empty data")

    df = _extract_year(df)
    annual = (
        df.groupby("year")
        .agg(
            arrivals_total=("arrivals", "sum"),
            arrivals_male=("arrivals_male", "sum"),
            arrivals_female=("arrivals_female", "sum"),
        )
        .reset_index()
    )
    console.print(f"  [green]{len(annual)} years, {annual['year'].min()}-{annual['year'].max()}[/green]")
    return annual


def validate_opendosm_outputs() -> bool:
    """Read all saved parquets and validate structural integrity.

    Checks that each file has the expected columns, valid state codes,
    a year column, and no fully-empty rows. Logs row counts.

    Returns
    -------
    bool
        True if all validations pass.
    """
    from src.harmonization.state_codes import VALID_CODES

    checks_passed = True
    expected = {
        "population_state": {"required_cols": ["state_code", "year", "population"], "has_states": True},
        "water_consumption": {"required_cols": ["state_code", "year", "sector", "value"], "has_states": True},
        "hh_access_amenities": {"required_cols": ["state_code", "year", "sanitation", "electricity", "piped_water"], "has_states": True},
        "arrivals": {"required_cols": ["year", "arrivals_total"], "has_states": False},
    }

    for slug, spec in expected.items():
        path = OUTPUT_DIR / f"{slug}_raw.parquet"
        if not path.exists():
            logger.error("VALIDATION FAIL: %s not found at %s", slug, path)
            checks_passed = False
            continue

        df = pd.read_parquet(path)
        logger.info("Validating %s: %d rows", slug, len(df))

        missing_cols = set(spec["required_cols"]) - set(df.columns)
        if missing_cols:
            logger.error("VALIDATION FAIL: %s missing columns %s", slug, missing_cols)
            checks_passed = False

        if "year" in df.columns and df["year"].isna().any():
            logger.error("VALIDATION FAIL: %s has NA values in year column", slug)
            checks_passed = False

        if spec["has_states"] and "state_code" in df.columns:
            invalid = set(df["state_code"].dropna()) - VALID_CODES
            if invalid:
                logger.error("VALIDATION FAIL: %s has invalid state codes %s", slug, invalid)
                checks_passed = False

        empty_rows = df.isna().all(axis=1).sum()
        if empty_rows > 0:
            logger.error("VALIDATION FAIL: %s has %d fully-empty rows", slug, empty_rows)
            checks_passed = False

    return checks_passed


def main() -> None:
    """Run all OpenDOSM loaders and save outputs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    console.rule("[bold blue]OpenDOSM Ingestion Pipeline[/bold blue]")

    loaders: list[tuple[str, callable]] = [
        ("population_state", load_population_state),
        ("water_consumption", load_water_consumption),
        ("hh_access_amenities", load_hh_access_amenities),
        ("arrivals", load_arrivals),
    ]

    results: list[dict] = []

    for slug, loader in loaders:
        try:
            df = loader()
            path = save_raw(df, slug)
            year_min = int(df["year"].min())
            year_max = int(df["year"].max())
            n_states = df["state_code"].nunique() if "state_code" in df.columns else 0
            results.append({
                "slug": slug,
                "rows": len(df),
                "years": f"{year_min}-{year_max}",
                "states": n_states,
                "path": str(path),
                "status": "OK",
            })
        except Exception as exc:
            logger.error("Failed to load %s: %s", slug, exc)
            results.append({
                "slug": slug,
                "rows": 0,
                "years": "-",
                "states": 0,
                "path": "-",
                "status": f"FAILED: {exc}",
            })

    console.rule("[bold blue]Summary[/bold blue]")
    table = Table(title="OpenDOSM Ingestion Results")
    table.add_column("Slug", style="cyan")
    table.add_column("Rows", justify="right")
    table.add_column("Years")
    table.add_column("States", justify="right")
    table.add_column("Status")
    table.add_column("Path", style="dim")

    for r in results:
        status_style = "green" if r["status"] == "OK" else "red"
        table.add_row(
            r["slug"],
            str(r["rows"]),
            r["years"],
            str(r["states"]),
            f"[{status_style}]{r['status']}[/{status_style}]",
            r["path"],
        )
    console.print(table)

    failed = [r for r in results if r["status"] != "OK"]
    if failed:
        console.print(f"\n[red bold]{len(failed)} dataset(s) failed.[/red bold]")
        raise SystemExit(1)
    else:
        console.print(f"\n[green bold]All {len(results)} datasets ingested successfully.[/green bold]")

    console.rule("[bold blue]Validation[/bold blue]")
    if validate_opendosm_outputs():
        console.print("[green bold]All validation checks passed.[/green bold]")
    else:
        console.print("[red bold]Validation failed — see errors above.[/red bold]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
