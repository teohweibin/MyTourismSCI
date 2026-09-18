"""Tests for geospatial ingestion: CRS handling, buffer computation, aggregation."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon, box

from src.ingestion.geospatial_ingest import (
    CRS_UTM48N,
    CRS_WGS84,
    STATE_CODES,
    compute_buffer_indicators,
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
        """A hotel 3 km from a coastline segment should be inside a 5 km buffer."""
        coast_line = gpd.GeoDataFrame(
            geometry=[LineString([(500_000, 300_000), (500_000, 310_000)])],
            crs=CRS_UTM48N,
        )
        hotel_inside = gpd.GeoDataFrame(
            geometry=[Point(503_000, 305_000)],
            crs=CRS_UTM48N,
        )
        hotel_outside = gpd.GeoDataFrame(
            geometry=[Point(510_000, 305_000)],
            crs=CRS_UTM48N,
        )

        buffer_geom = coast_line.geometry.buffer(5_000).unary_union

        assert hotel_inside.geometry.iloc[0].within(buffer_geom)
        assert not hotel_outside.geometry.iloc[0].within(buffer_geom)

    def test_buffer_distance_accuracy(self):
        """Buffer radius should be close to 5000 m in projected coordinates."""
        pt = gpd.GeoDataFrame(geometry=[Point(500_000, 300_000)], crs=CRS_UTM48N)
        buffered = pt.geometry.buffer(5_000)
        centroid = pt.geometry.iloc[0]
        boundary = buffered.iloc[0].exterior
        distances = [centroid.distance(Point(c)) for c in boundary.coords]
        np.testing.assert_allclose(distances, 5_000, atol=1.0)


class TestStateLevelAggregation:
    def test_aggregation_counts(self):
        """Hotels assigned to correct states with correct coastal/PA counts."""
        states = gpd.GeoDataFrame(
            {"state_code": ["SGR", "JOH"]},
            geometry=[
                box(101.0, 2.5, 102.0, 3.5),
                box(103.0, 1.0, 104.0, 2.0),
            ],
            crs=CRS_WGS84,
        )
        hotels = gpd.GeoDataFrame(
            {
                "name": ["H1", "H2", "H3"],
                "state_code": ["SGR", "SGR", "JOH"],
            },
            geometry=[
                Point(101.5, 3.0),
                Point(101.3, 2.8),
                Point(103.5, 1.5),
            ],
            crs=CRS_WGS84,
        )

        coastline = gpd.GeoDataFrame(
            geometry=[LineString([(101.0, 3.5), (102.0, 3.5)])],
            crs=CRS_WGS84,
        )

        wdpa = gpd.GeoDataFrame(
            geometry=[box(103.4, 1.4, 103.6, 1.6)],
            crs=CRS_WGS84,
        )

        result = compute_buffer_indicators(hotels, coastline, wdpa, states)

        assert set(result.columns) >= {
            "state_code", "coastal_hotel_count", "coastal_hotel_share",
            "pa_hotel_count", "pa_hotel_share",
        }

        sgr = result[result["state_code"] == "SGR"].iloc[0]
        assert sgr["total_geocoded_hotels"] == 2

        joh = result[result["state_code"] == "JOH"].iloc[0]
        assert joh["total_geocoded_hotels"] == 1
        assert joh["pa_hotel_count"] >= 1

    def test_all_state_codes_present(self):
        """Output should contain rows for all 16 state codes."""
        states = gpd.GeoDataFrame(
            {"state_code": STATE_CODES},
            geometry=[box(100 + i * 0.1, 1, 100.1 + i * 0.1, 1.1) for i in range(16)],
            crs=CRS_WGS84,
        )
        hotels = gpd.GeoDataFrame(
            {"name": ["H1"], "state_code": ["SGR"]},
            geometry=[Point(100.05, 1.05)],
            crs=CRS_WGS84,
        )
        coastline = gpd.GeoDataFrame(
            geometry=[LineString([(99, 0), (102, 0)])],
            crs=CRS_WGS84,
        )
        wdpa = gpd.GeoDataFrame(geometry=[box(99, 0, 99.1, 0.1)], crs=CRS_WGS84)

        result = compute_buffer_indicators(hotels, coastline, wdpa, states)
        assert len(result) == 16
        assert set(result["state_code"]) == set(STATE_CODES)
