"""Calculate area and length for supported geospatial geometries."""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.exceptions import GeospatialFileError

SUPPORTED_AREA_TYPES = {"Polygon", "MultiPolygon"}
SUPPORTED_LENGTH_TYPES = {"LineString", "MultiLineString"}
POINT_TYPES = {"Point"}


def calculate_measurements(gdf: gpd.GeoDataFrame) -> list[dict]:
    """Return per-feature measurements in metric units.

    Geographic CRS values (for example EPSG:4326) are transformed to a
    projected CRS before area or length is calculated. Measurements are
    never computed in latitude/longitude degrees.
    """
    if gdf.empty:
        return []

    if gdf.crs is None:
        raise GeospatialFileError(
            "The file does not contain a CRS. A coordinate reference "
            "system is required before measurements can be calculated."
        )

    measurement_gdf = _to_projected_crs(gdf)
    results: list[dict] = []

    for index, geometry in enumerate(measurement_gdf.geometry):
        results.append(_measure_geometry(index, geometry))

    return results


def _to_projected_crs(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return a GeoDataFrame in a projected CRS suitable for measurements."""
    if not gdf.crs.is_geographic:
        return gdf

    try:
        projected_crs = gdf.estimate_utm_crs()
    except Exception as exc:
        raise GeospatialFileError(
            "Could not determine a suitable projected CRS for measurements."
        ) from exc

    if projected_crs is None:
        raise GeospatialFileError(
            "Could not determine a suitable projected CRS for measurements."
        )

    return gdf.to_crs(projected_crs)


def _measure_geometry(feature_id: int, geometry: BaseGeometry | None) -> dict:
    """Build a measurement payload for a single geometry."""
    if geometry is None or geometry.is_empty:
        return {
            "feature_id": feature_id,
            "geometry_type": None if geometry is None else geometry.geom_type,
            "measurement": None,
            "message": "Geometry is empty or missing.",
        }

    geometry_type = geometry.geom_type
    result: dict = {
        "feature_id": feature_id,
        "geometry_type": geometry_type,
        "measurement": None,
    }

    if geometry_type in SUPPORTED_AREA_TYPES:
        result["measurement"] = {
            "type": "area",
            "value": round(geometry.area, 2),
            "unit": "m²",
        }
    elif geometry_type in SUPPORTED_LENGTH_TYPES:
        result["measurement"] = {
            "type": "length",
            "value": round(geometry.length, 2),
            "unit": "m",
        }
    elif geometry_type in POINT_TYPES:
        result["message"] = "No measurement required for Point geometry."
    else:
        result["message"] = (
            f"Measurement not supported for geometry type: {geometry_type}"
        )

    return result
