"""Ingest and preprocess geospatial datasets for pressure indicators.

Inputs: DOSM Kawasanku boundaries, OSM Malaysia extract, WDPA protected areas
Outputs: Processed GeoJSON/GeoParquet in data/processed/
Dependencies: geopandas, shapely, pyogrio
"""
