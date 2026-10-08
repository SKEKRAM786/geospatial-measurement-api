from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import GeometryCollection, LineString, Point, Polygon

from app.exceptions import GeospatialFileError
from app.services.measurement import calculate_measurements


def test_empty_geodataframe_returns_no_measurements():
    gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    assert calculate_measurements(gdf) == []


def test_missing_crs_raises():
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0)])
    with pytest.raises(GeospatialFileError, match="CRS"):
        calculate_measurements(gdf)


def test_polygon_area_uses_projected_crs():
    gdf = gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (0.01, 0), (0.01, 0.01), (0, 0.01)])],
        crs="EPSG:4326",
    )
    results = calculate_measurements(gdf)
    assert results[0]["measurement"]["type"] == "area"
    assert results[0]["measurement"]["unit"] == "m²"
    assert results[0]["measurement"]["value"] > 0
    # A naive degree-based area would be ~0.0001, not hundreds of thousands of m².
    assert results[0]["measurement"]["value"] > 1


def test_linestring_length_uses_projected_crs():
    gdf = gpd.GeoDataFrame(
        geometry=[LineString([(0, 0), (0.01, 0)])],
        crs="EPSG:4326",
    )
    results = calculate_measurements(gdf)
    assert results[0]["measurement"]["type"] == "length"
    assert results[0]["measurement"]["unit"] == "m"
    assert results[0]["measurement"]["value"] > 0


def test_point_has_null_measurement():
    gdf = gpd.GeoDataFrame(geometry=[Point(1, 2)], crs="EPSG:4326")
    results = calculate_measurements(gdf)
    assert results[0]["measurement"] is None
    assert "No measurement required" in results[0]["message"]


def test_unsupported_geometry_does_not_raise():
    gdf = gpd.GeoDataFrame(
        geometry=[GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])],
        crs="EPSG:4326",
    )
    results = calculate_measurements(gdf)
    assert results[0]["measurement"] is None
    assert "GeometryCollection" in results[0]["message"]


def test_cannot_determine_projected_crs(monkeypatch):
    gdf = gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (0.01, 0), (0.01, 0.01), (0, 0.01)])],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(gdf, "estimate_utm_crs", lambda: None)
    with pytest.raises(GeospatialFileError, match="projected CRS"):
        calculate_measurements(gdf)
