"""Ingest and preprocess geospatial datasets for environmental pillar indicators.

Computes two state-level tourism pressure indicators:
  - Coastal buffer accommodation density (hotels within 5 km of coastline)
  - Protected area buffer accommodation density (hotels within 5 km of WDPA areas)

Inputs:
    data/raw/geospatial/WDPA.zip — WDPA Malaysia shapefiles (nested ZIPs)
    data/raw/geospatial/dosm_boundaries/states.geojson.zip — 16 state polygons
    data/raw/geospatial/OSM/malaysia-singapore-brunei-260916-free.shp.zip — OSM extract
    data/raw/motac/motac_hotels_rated.parquet — 757 rated hotels with addresses

Outputs:
    data/processed/geospatial/state_geospatial_indicators.parquet
    data/processed/geospatial/motac_hotel_geocoded.parquet

Dependencies: geopandas, shapely, geopy, pandas, pyarrow
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import time
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiLineString, MultiPolygon, Point
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
OSM_ZIP = RAW_DIR / "geospatial" / "OSM" / "malaysia-singapore-brunei-260916-free.shp.zip"
HOTELS_PARQUET = RAW_DIR / "motac" / "motac_hotels_rated.parquet"

GEOCODE_CACHE = PROC_DIR / "motac_hotel_geocoded.parquet"
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


def load_osm_coastline(path: Path = OSM_ZIP) -> gpd.GeoDataFrame | None:
    """Load coastline features from OSM extract (natural line layer, fclass=coastline)."""
    if not path.exists():
        logger.warning("OSM extract not found: %s", path)
        return None

    try:
        gdf = gpd.read_file(
            f"zip://{path}!gis_osm_water_a_free_1.shp",
        )
        logger.info("OSM water_a: %d features, CRS=%s", len(gdf), gdf.crs)
    except Exception:
        logger.warning("Could not load OSM water_a layer")
        return None

    gdf = gdf.to_crs(CRS_WGS84)
    return gdf


def derive_coastline_from_states(states: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Derive approximate coastline from state boundaries.

    Takes the exterior boundary of the dissolved union of all state polygons.
    This includes both coastline and international land borders (Thailand,
    Indonesia), which is an acceptable approximation for 5 km hotel buffers.
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


def load_hotels(path: Path = HOTELS_PARQUET) -> pd.DataFrame:
    """Load MOTAC rated hotels."""
    if not path.exists():
        raise FileNotFoundError(f"Hotels parquet not found: {path}")
    df = pd.read_parquet(path)
    logger.info("Hotels: %d records, columns=%s", len(df), df.columns.tolist())
    return df


def geocode_hotels(
    hotels: pd.DataFrame,
    cache_path: Path = GEOCODE_CACHE,
    delay: float = 1.1,
) -> gpd.GeoDataFrame:
    """Geocode hotels using Nominatim with caching.

    Respects Nominatim usage policy with 1-second delay between requests.
    Cached results are loaded from parquet to avoid re-geocoding on re-runs.
    """
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
    from geopy.geocoders import Nominatim

    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        cached_names = set(cached["name"].tolist())
        to_geocode = hotels[~hotels["name"].isin(cached_names)].copy()
        logger.info("Cache hit: %d/%d hotels already geocoded, %d remaining",
                     len(cached), len(hotels), len(to_geocode))
    else:
        cached = pd.DataFrame()
        to_geocode = hotels.copy()

    if len(to_geocode) == 0:
        gdf = gpd.GeoDataFrame(
            cached,
            geometry=gpd.points_from_xy(cached["longitude"], cached["latitude"]),
            crs=CRS_WGS84,
        )
        return gdf

    geocoder = Nominatim(user_agent="mytourismsci_dosm_datathon_2026", timeout=10)
    results = []
    total = len(to_geocode)

    for idx, (_, row) in enumerate(to_geocode.iterrows()):
        query = f"{row['name']}, {row['address']}"
        lat, lon = pd.NA, pd.NA
        try:
            location = geocoder.geocode(query, country_codes="MY")
            if location:
                lat, lon = location.latitude, location.longitude
            else:
                location = geocoder.geocode(row["address"], country_codes="MY")
                if location:
                    lat, lon = location.latitude, location.longitude
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.warning("Geocoder error for '%s': %s", row["name"], e)

        results.append({"name": row["name"], "latitude": lat, "longitude": lon})

        if (idx + 1) % 50 == 0 or idx == total - 1:
            logger.info("Geocoding progress: %d/%d (%.0f%%)", idx + 1, total, (idx + 1) / total * 100)

        time.sleep(delay)

    new_df = pd.DataFrame(results)
    combined = pd.concat([cached, hotels.merge(new_df, on="name", how="inner")], ignore_index=True)

    if "latitude_x" in combined.columns:
        combined = combined.rename(columns={"latitude_x": "latitude", "longitude_x": "longitude"})
        combined = combined.drop(columns=["latitude_y", "longitude_y"], errors="ignore")

    combined.to_parquet(cache_path, index=False)
    logger.info("Geocoded %d new hotels, total cached: %d", len(new_df), len(combined))

    valid = combined.dropna(subset=["latitude", "longitude"])
    gdf = gpd.GeoDataFrame(
        valid,
        geometry=gpd.points_from_xy(valid["longitude"], valid["latitude"]),
        crs=CRS_WGS84,
    )
    return gdf


def compute_buffer_indicators(
    hotels_gdf: gpd.GeoDataFrame,
    coastline: gpd.GeoDataFrame,
    wdpa: gpd.GeoDataFrame,
    states: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Compute coastal and protected-area buffer indicators per state.

    Projects all geometries to UTM 48N for metric distance calculations,
    applies 5 km buffers around coastline and WDPA polygons, then counts
    hotels falling within each buffer per state.
    """
    hotels_proj = hotels_gdf.to_crs(CRS_UTM48N)
    states_proj = states.to_crs(CRS_UTM48N)
    wdpa_proj = wdpa.to_crs(CRS_UTM48N)
    coast_proj = coastline.to_crs(CRS_UTM48N)

    coast_buffer = coast_proj.geometry.buffer(BUFFER_METERS)
    coast_buffer_union = unary_union(coast_buffer)
    logger.info("Coastal buffer (5 km) computed")

    wdpa_valid = wdpa_proj.copy()
    wdpa_valid["geometry"] = wdpa_valid["geometry"].apply(make_valid)
    pa_buffer = wdpa_valid.geometry.buffer(BUFFER_METERS)
    pa_buffer_union = unary_union(pa_buffer)
    logger.info("Protected area buffer (5 km) computed")

    hotels_proj["in_coastal_buffer"] = hotels_proj.geometry.within(coast_buffer_union)
    hotels_proj["in_pa_buffer"] = hotels_proj.geometry.within(pa_buffer_union)

    state_col = _find_state_column(states_proj)
    states_for_join = states_proj[[state_col, "geometry"]].rename(columns={state_col: "_st_code"})
    hotel_states = gpd.sjoin(hotels_proj, states_for_join, how="left", predicate="within")

    rows = []
    for sc in STATE_CODES:
        state_hotels = hotel_states[hotel_states["_st_code"] == sc]
        total = len(state_hotels)
        coastal_count = int(state_hotels["in_coastal_buffer"].sum()) if total > 0 else 0
        pa_count = int(state_hotels["in_pa_buffer"].sum()) if total > 0 else 0

        rows.append({
            "state_code": sc,
            "coastal_hotel_count": coastal_count,
            "coastal_hotel_share": round(coastal_count / total, 4) if total > 0 else pd.NA,
            "pa_hotel_count": pa_count,
            "pa_hotel_share": round(pa_count / total, 4) if total > 0 else pd.NA,
            "total_geocoded_hotels": total,
        })

    result = pd.DataFrame(rows)
    logger.info("Indicator summary:\n%s", result.to_string(index=False))
    return result


def _find_state_column(gdf: gpd.GeoDataFrame) -> str:
    """Identify the column containing state codes in the GeoDataFrame."""
    for col in ["state_code", "state", "STATE", "code", "CODE", "NAME", "name"]:
        if col in gdf.columns:
            return col
    raise KeyError(f"Cannot find state column in {gdf.columns.tolist()}")


def validate_checkpoint(
    states: gpd.GeoDataFrame,
    wdpa: gpd.GeoDataFrame,
    osm_water: gpd.GeoDataFrame | None,
    hotels: pd.DataFrame,
) -> None:
    """Print checkpoint summary for Task 2 validation."""
    print("\n" + "=" * 60)
    print("CHECKPOINT: Source Validation (Task 2)")
    print("=" * 60)

    print(f"\n1. States boundary:")
    print(f"   Features: {len(states)}")
    print(f"   CRS: {states.crs}")
    print(f"   Extent: {states.total_bounds}")
    print(f"   Columns: {states.columns.tolist()}")

    print(f"\n2. WDPA protected areas:")
    print(f"   Features: {len(wdpa)}")
    print(f"   CRS: {wdpa.crs}")
    print(f"   Extent: {wdpa.total_bounds}")

    if osm_water is not None:
        print(f"\n3. OSM water polygons:")
        print(f"   Features: {len(osm_water)}")
        print(f"   CRS: {osm_water.crs}")
        if "fclass" in osm_water.columns:
            print(f"   Feature classes: {osm_water['fclass'].value_counts().to_dict()}")
    else:
        print(f"\n3. OSM water: NOT LOADED (will derive coastline from state boundaries)")

    print(f"\n4. MOTAC hotels:")
    print(f"   Records: {len(hotels)}")
    print(f"   Columns: {hotels.columns.tolist()}")
    unique_states = [s for s in hotels['state_code'].dropna().unique().tolist() if isinstance(s, str)]
    print(f"   States: {sorted(unique_states)}")
    print("=" * 60 + "\n")


def geocode_checkpoint(hotels_gdf: gpd.GeoDataFrame, total_hotels: int) -> bool:
    """Print geocoding checkpoint. Returns True if success rate >= 70%."""
    geocoded = len(hotels_gdf)
    rate = geocoded / total_hotels if total_hotels > 0 else 0

    print("\n" + "=" * 60)
    print("CHECKPOINT: Geocoding Results (Task 4)")
    print("=" * 60)
    print(f"   Total hotels: {total_hotels}")
    print(f"   Successfully geocoded: {geocoded}")
    print(f"   Success rate: {rate:.1%}")

    if geocoded > 0:
        print(f"   State distribution:")
        by_state = hotels_gdf.groupby("state_code").size()
        for sc, count in by_state.items():
            print(f"     {sc}: {count}")

    print("=" * 60 + "\n")

    if rate < 0.70:
        logger.warning("Geocoding success rate %.1f%% is below 70%% threshold", rate * 100)
        return False
    return True


def run(skip_geocoding: bool = False) -> pd.DataFrame:
    """Run the full geospatial ingestion pipeline.

    Set skip_geocoding=True to use cached geocoding results only.
    """
    _ensure_dirs()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    logger.info("=== Task 1: CRS setup ===")
    logger.info("Storage CRS: %s (WGS84)", CRS_WGS84)
    logger.info("Projected CRS: %s (UTM 48N) for distance calculations", CRS_UTM48N)

    logger.info("=== Task 2: Load and validate sources ===")
    states = load_states()
    wdpa = load_wdpa()
    osm_water = load_osm_coastline()
    hotels_df = load_hotels()

    validate_checkpoint(states, wdpa, osm_water, hotels_df)

    logger.info("=== Task 3: Prepare coastline ===")
    coastline = derive_coastline_from_states(states)

    logger.info("=== Task 4: Geocode hotels ===")
    if skip_geocoding and GEOCODE_CACHE.exists():
        logger.info("Using cached geocoding results")
        cached = pd.read_parquet(GEOCODE_CACHE)
        valid = cached.dropna(subset=["latitude", "longitude"])
        hotels_gdf = gpd.GeoDataFrame(
            valid,
            geometry=gpd.points_from_xy(valid["longitude"], valid["latitude"]),
            crs=CRS_WGS84,
        )
    else:
        hotels_gdf = geocode_hotels(hotels_df)

    ok = geocode_checkpoint(hotels_gdf, len(hotels_df))
    if not ok:
        logger.error("Geocoding below 70%% threshold. Stopping for manual review.")
        raise RuntimeError(
            "Geocoding success rate below 70%. Consider fallback: "
            "MapBox geocoding or MOTAC state-only aggregation."
        )

    logger.info("=== Task 5: Compute indicators ===")

    state_col = _find_state_column(states)
    if state_col != "state_code":
        states = states.rename(columns={state_col: "state_code"})

    indicators = compute_buffer_indicators(hotels_gdf, coastline, wdpa, states)

    logger.info("=== Task 6-7: Save outputs ===")
    indicators.to_parquet(INDICATORS_OUT, index=False)
    logger.info("Saved indicators to %s", INDICATORS_OUT)

    hotels_out = hotels_gdf.drop(columns=["geometry"])
    hotels_out.to_parquet(GEOCODE_CACHE, index=False)
    logger.info("Saved geocoded hotels to %s", GEOCODE_CACHE)

    return indicators


if __name__ == "__main__":
    run()
