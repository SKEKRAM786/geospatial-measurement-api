from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiPoint, Point, Polygon

POLYGON_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Polygon</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>0,0,0 0.01,0,0 0.01,0.01,0 0,0.01,0 0,0,0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""

LINESTRING_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Line</name>
      <LineString>
        <coordinates>0,0,0 0.01,0.01,0</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""

POINT_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Point</name>
      <Point>
        <coordinates>0,0,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""

CORRUPT_KML = b"<kml><not-valid"


def shapefile_zip_bytes(gdf: gpd.GeoDataFrame, include_prj: bool = True) -> bytes:
    """Serialize a GeoDataFrame as an in-memory Shapefile ZIP."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        with tempfile.TemporaryDirectory() as temp_dir:
            shapefile_path = Path(temp_dir) / "features.shp"
            gdf.to_file(shapefile_path)
            for child in Path(temp_dir).iterdir():
                if not include_prj and child.suffix.lower() == ".prj":
                    continue
                zip_file.write(child, child.name)
    return buffer.getvalue()


def polygon_geodataframe(crs: str | None = "EPSG:4326") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["park"]},
        geometry=[Polygon([(0, 0), (0.01, 0), (0.01, 0.01), (0, 0.01)])],
        crs=crs,
    )


def linestring_geodataframe(crs: str | None = "EPSG:4326") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["path"]},
        geometry=[LineString([(0, 0), (0.01, 0.01)])],
        crs=crs,
    )


def point_geodataframe(crs: str | None = "EPSG:4326") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["place"]},
        geometry=[Point(0, 0)],
        crs=crs,
    )


def multipoint_geodataframe(crs: str | None = "EPSG:4326") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["cluster"]},
        geometry=[MultiPoint([(0, 0), (0.01, 0.01)])],
        crs=crs,
    )


def zip_without_shapefile() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("readme.txt", "no shapefile here")
    return buffer.getvalue()
