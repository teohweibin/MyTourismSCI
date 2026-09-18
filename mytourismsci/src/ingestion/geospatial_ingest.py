"""Ingest and preprocess geospatial datasets for environmental pillar indicators.

Computes two state-level tourism pressure proxy indicators via spatial
overlay of state boundaries with coastline and WDPA protected area buffers:
  - coastal_area_fraction: share of state area within 5 km of coastline
  - pa_area_fraction: share of state area within 5 km of any WDPA polygon

These fractions are multiplied by per-state MOTAC hotel counts to derive
estimated coastal-hotel and PA-hotel counts per state.

Methodology note: Individual hotel geocoding was infeasible due to
Nominatim/Photon rate limits within datathon timeline; state-level
buffer-coverage aggregation used as approximation. This follows the OECD/JRC
2008 Handbook guidance on using available administrative-level proxies when
micro-level spatial data is unavailable (§6.2).

Inputs:
    data/raw/geospatial/WDPA.zip — WDPA Malaysia shapefiles (nested ZIPs)
    data/raw/geospatial/dosm_boundaries/states.geojson.zip — 16 state polygons
    data/raw/motac/motac_hotels_rated.parquet — 757 rated hotels with state codes

Outputs:
    data/processed/geospatial/state_geospatial_indicators.parquet

Dependencies: geopandas, shapely, pandas, pyarrow
"""

from __future__ import annotations

import logging
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiLineString, MultiPolygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from src.harmonization.state_codes import normalize_state_name

logger = logging.getLogger(__name__)

CRS_WGS84 = "EPSG:4326"
CRS_UTM48N = "EPSG:32648"
BUFFER_METERS = 5_000

STATE_CODES = [
    "JOH", "KDH", "KTN", "MLK", "NSN", "PHG", "PNG", "PRK",
    "PLS", "SGR", "TRG", "SBH", "SWK", "KUL", "LBN", "PJY",
]

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw"
PROC_DIR = BASE_DIR / "data" / "processed" / "geospatial"

WDPA_ZIP = RAW_DIR / "geospatial" / "WDPA.zip"
STATES_ZIP = RAW_DIR / "geospatial" / "dosm_boundaries" / "states.geojson.zip"
HOTELS_PARQUET = RAW_DIR / "motac" / "motac_hotels_rated.parquet"

INDICATORS_OUT = PROC_DIR / "state_geospatial_indicators.parquet"


def _ensure_dirs() -> None:
    PROC_DIR.mkdir(parents=True, exist_ok=True)


def load_states(path: Path = STATES_ZIP) -> gpd.GeoDataFrame:
    """Load 16 Malaysian state polygons from zipped GeoJSON."""
    if not path.exists():
        raise FileNotFoundError(f"States boundary not found: {path}")

    with zipfile.ZipFile(path) as zf:
        geojson_name = next(
            (n for n in zf.namelist() if "admin1" in n and n.endswith(".geojson")),
            next((n for n in zf.namelist() if n.endswith(".geojson")), None),
        )
        if geojson_name is None:
            raise RuntimeError(f"No GeoJSON found in {path}: {zf.namelist()}")
        with zf.open(geojson_name) as f:
            gdf = gpd.read_file(f)

    gdf = gdf.to_crs(CRS_WGS84)

    name_col = next((c for c in ("adm1_name", "name", "NAME") if c in gdf.columns), None)
    if name_col:
        gdf["state_code"] = gdf[name_col].apply(normalize_state_name)
    logger.info("States: %d features, CRS=%s, bounds=%s", len(gdf), gdf.crs, gdf.total_bounds.tolist())
    return gdf


def load_wdpa(path: Path = WDPA_ZIP) -> gpd.GeoDataFrame:
    """Load WDPA protected area polygons from nested ZIP archive."""
    if not path.exists():
        raise FileNotFoundError(f"WDPA archive not found: {path}")

    frames = []
    with zipfile.ZipFile(path) as outer:
        inner_zips = [n for n in outer.namelist() if n.endswith(".zip")]
        for inner_name in inner_zips:
            inner_bytes = outer.read(inner_name)
            with tempfile.TemporaryDirectory() as tmpdir:
                inner_path = Path(tmpdir) / inner_name
                inner_path.write_bytes(inner_bytes)
                with zipfile.ZipFile(inner_path) as iz:
                    polygon_shps = [n for n in iz.namelist() if "polygons" in n and n.endswith(".shp")]
                    if polygon_shps:
                        iz.extractall(tmpdir)
                        shp_path = Path(tmpdir) / polygon_shps[0]
                        gdf = gpd.read_file(shp_path)
                        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
                        frames.append(gdf)
                        logger.info("  WDPA inner %s: %d polygon features", inner_name, len(gdf))

    if not frames:
        raise RuntimeError("No WDPA polygon features loaded from any inner ZIP")

    wdpa = pd.concat(frames, ignore_index=True)
    wdpa = gpd.GeoDataFrame(wdpa, geometry="geometry")
    wdpa = wdpa.to_crs(CRS_WGS84)
    wdpa["geometry"] = wdpa["geometry"].apply(make_valid)
    logger.info("WDPA total: %d polygon features, CRS=%s, bounds=%s",
                len(wdpa), wdpa.crs, wdpa.total_bounds.tolist())
    return wdpa


def derive_coastline_from_states(states: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Derive approximate coastline from state boundaries.

    Takes the exterior boundary of the dissolved union of all state polygons.
    This includes both coastline and international land borders (Thailand,
    Indonesia), which is an acceptable approximation for 5 km buffer fractions.
    """
    states_proj = states.to_crs(CRS_UTM48N)
    dissolved = unary_union(states_proj.geometry)
    dissolved = make_valid(dissolved)

    if isinstance(dissolved, MultiPolygon):
        boundaries = [poly.exterior for poly in dissolved.geoms]
    else:
        boundaries = [dissolved.exterior]

    coastline = gpd.GeoDataFrame(
        geometry=[MultiLineString(boundaries)],
        crs=CRS_UTM48N,
    )
    logger.info("Derived coastline from state boundaries: %d line segments", len(boundaries))
    return coastline


def get_hotel_counts_by_state(path: Path = HOTELS_PARQUET) -> pd.Series:
    """Count MOTAC rated hotels per state from parquet."""
    if not path.exists():
        raise FileNotFoundError(f"Hotels parquet not found: {path}")
    df = pd.read_parquet(path, columns=["state_code"])
    counts = df["state_code"].value_counts()
    logger.info("Hotel counts by state: %d total across %d states", counts.sum(), len(counts))
    return counts


def compute_state_buffer_indicators(
    states: gpd.GeoDataFrame,
    coastline: gpd.GeoDataFrame,
    wdpa: gpd.GeoDataFrame,
    hotel_counts: pd.Series,
) -> pd.DataFrame:
    """Compute coastal and PA buffer area fractions per state.

    For each state polygon, computes the fraction of state area that falls
    within 5 km of (a) the coastline and (b) any WDPA protected area.
    Multiplies each fraction by the state's total hotel count to estimate
    how many hotels are within each buffer zone.
    """
    states_proj = states.to_crs(CRS_UTM48N)
    wdpa_proj = wdpa.to_crs(CRS_UTM48N)
    coast_proj = coastline.to_crs(CRS_UTM48N)

    coast_buffer_union = unary_union(coast_proj.geometry.buffer(BUFFER_METERS))
    logger.info("Coastal buffer (5 km) computed")

    wdpa_valid = wdpa_proj.copy()
    wdpa_valid["geometry"] = wdpa_valid["geometry"].apply(make_valid)
    pa_buffer_union = unary_union(wdpa_valid.geometry.buffer(BUFFER_METERS))
    logger.info("Protected area buffer (5 km) computed")

    rows = []
    for _, state_row in states_proj.iterrows():
        sc = state_row["state_code"]
        state_geom = make_valid(state_row.geometry)
        state_area = state_geom.area

        coastal_intersection = state_geom.intersection(coast_buffer_union)
        coastal_frac = round(coastal_intersection.area / state_area, 6) if state_area > 0 else 0.0

        pa_intersection = state_geom.intersection(pa_buffer_union)
        pa_frac = round(pa_intersection.area / state_area, 6) if state_area > 0 else 0.0

        n_hotels = int(hotel_counts.get(sc, 0))

        rows.append({
            "state_code": sc,
            "coastal_area_fraction": coastal_frac,
            "pa_area_fraction": pa_frac,
            "total_hotels": n_hotels,
            "estimated_coastal_hotels": round(coastal_frac * n_hotels),
            "estimated_pa_hotels": round(pa_frac * n_hotels),
        })

    result = pd.DataFrame(rows)
    logger.info("Indicator summary:\n%s", result.to_string(index=False))
    return result


def run() -> pd.DataFrame:
    """Run the geospatial ingestion pipeline (state-buffer aggregation)."""
    _ensure_dirs()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    logger.info("=== CRS setup ===")
    logger.info("Storage CRS: %s (WGS84)", CRS_WGS84)
    logger.info("Projected CRS: %s (UTM 48N) for distance calculations", CRS_UTM48N)

    logger.info("=== Load sources ===")
    states = load_states()
    wdpa = load_wdpa()
    hotel_counts = get_hotel_counts_by_state()

    logger.info("=== Derive coastline ===")
    coastline = derive_coastline_from_states(states)

    logger.info("=== Compute state-level buffer indicators ===")
    indicators = compute_state_buffer_indicators(states, coastline, wdpa, hotel_counts)

    logger.info("=== Save outputs ===")
    indicators.to_parquet(INDICATORS_OUT, index=False)
    logger.info("Saved indicators to %s", INDICATORS_OUT)

    return indicators


if __name__ == "__main__":
    run()
