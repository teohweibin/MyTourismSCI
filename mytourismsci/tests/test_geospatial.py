"""Tests for geospatial ingestion: CRS handling, buffer computation, state-buffer aggregation."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, box

from src.ingestion.geospatial_ingest import (
    CRS_UTM48N,
    CRS_WGS84,
    STATE_CODES,
    compute_state_buffer_indicators,
)


@pytest.fixture
def sample_states():
    """Two synthetic state polygons in WGS84."""
    return gpd.GeoDataFrame(
        {
            "state_code": ["SGR", "PNG"],
            "geometry": [
                box(101.0, 2.5, 102.0, 3.5),
                box(100.0, 5.0, 100.8, 5.8),
            ],
        },
        crs=CRS_WGS84,
    )


class TestCRSHandling:
    def test_wgs84_to_utm_roundtrip(self, sample_states):
        projected = sample_states.to_crs(CRS_UTM48N)
        assert projected.crs.to_epsg() == 32648
        back = projected.to_crs(CRS_WGS84)
        assert back.crs.to_epsg() == 4326
        np.testing.assert_allclose(
            back.total_bounds, sample_states.total_bounds, atol=1e-6,
        )

    def test_utm_units_are_meters(self, sample_states):
        projected = sample_states.to_crs(CRS_UTM48N)
        bounds = projected.total_bounds
        x_range = bounds[2] - bounds[0]
        assert x_range > 100_000, "UTM range should be in meters, not degrees"


class TestBufferComputation:
    def test_known_point_within_buffer(self):
        """A point 3 km from a line segment should be inside a 5 km buffer."""
        coast_line = gpd.GeoDataFrame(
            geometry=[LineString([(500_000, 300_000), (500_000, 310_000)])],
            crs=CRS_UTM48N,
        )
        buffer_geom = coast_line.geometry.buffer(5_000).union_all()

        inside = Point(503_000, 305_000)
        outside = Point(510_000, 305_000)
        assert inside.within(buffer_geom)
        assert not outside.within(buffer_geom)

    def test_buffer_distance_accuracy(self):
        """Buffer radius should be close to 5000 m in projected coordinates."""
        pt = gpd.GeoDataFrame(geometry=[Point(500_000, 300_000)], crs=CRS_UTM48N)
        buffered = pt.geometry.buffer(5_000)
        centroid = pt.geometry.iloc[0]
        boundary = buffered.iloc[0].exterior
        distances = [centroid.distance(Point(c)) for c in boundary.coords]
        np.testing.assert_allclose(distances, 5_000, atol=1.0)


class TestStateBufferAggregation:
    def test_coastal_fraction_range(self):
        """Coastal area fractions should be between 0 and 1."""
        states = gpd.GeoDataFrame(
            {"state_code": ["SGR", "KUL"]},
            geometry=[
                box(101.0, 2.5, 102.0, 3.5),
                box(101.6, 3.1, 101.8, 3.3),
            ],
            crs=CRS_WGS84,
        )
        coastline = gpd.GeoDataFrame(
            geometry=[LineString([(101.0, 3.5), (102.0, 3.5)])],
            crs=CRS_WGS84,
        )
        wdpa = gpd.GeoDataFrame(geometry=[box(99, 0, 99.1, 0.1)], crs=CRS_WGS84)
        hotel_counts = pd.Series({"SGR": 30, "KUL": 85})

        result = compute_state_buffer_indicators(states, coastline, wdpa, hotel_counts)

        for _, row in result.iterrows():
            assert 0.0 <= row["coastal_area_fraction"] <= 1.0
            assert 0.0 <= row["pa_area_fraction"] <= 1.0

    def test_estimated_hotels_consistent(self):
        """Estimated hotel counts should equal round(fraction * total)."""
        states = gpd.GeoDataFrame(
            {"state_code": ["SGR"]},
            geometry=[box(101.0, 2.5, 102.0, 3.5)],
            crs=CRS_WGS84,
        )
        coastline = gpd.GeoDataFrame(
            geometry=[LineString([(101.0, 3.5), (102.0, 3.5)])],
            crs=CRS_WGS84,
        )
        wdpa = gpd.GeoDataFrame(geometry=[box(101.4, 2.9, 101.6, 3.1)], crs=CRS_WGS84)
        hotel_counts = pd.Series({"SGR": 100})

        result = compute_state_buffer_indicators(states, coastline, wdpa, hotel_counts)
        row = result.iloc[0]

        assert row["estimated_coastal_hotels"] == round(row["coastal_area_fraction"] * 100)
        assert row["estimated_pa_hotels"] == round(row["pa_area_fraction"] * 100)

    def test_all_state_codes_present(self):
        """Output should contain rows for all 16 state codes."""
        states = gpd.GeoDataFrame(
            {"state_code": STATE_CODES},
            geometry=[box(100 + i * 0.1, 1, 100.1 + i * 0.1, 1.1) for i in range(16)],
            crs=CRS_WGS84,
        )
        coastline = gpd.GeoDataFrame(
            geometry=[LineString([(99, 0), (102, 0)])],
            crs=CRS_WGS84,
        )
        wdpa = gpd.GeoDataFrame(geometry=[box(99, 0, 99.1, 0.1)], crs=CRS_WGS84)
        hotel_counts = pd.Series({"SGR": 10})

        result = compute_state_buffer_indicators(states, coastline, wdpa, hotel_counts)
        assert len(result) == 16
        assert set(result["state_code"]) == set(STATE_CODES)
        assert set(result.columns) >= {
            "state_code", "coastal_area_fraction", "pa_area_fraction",
            "estimated_coastal_hotels", "estimated_pa_hotels",
        }
