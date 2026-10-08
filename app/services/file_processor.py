"""Read KML and zipped Shapefile uploads into features and measurements."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd

from app.exceptions import GeospatialFileError
from app.services.measurement import calculate_measurements

ALLOWED_EXTENSIONS = {".kml", ".zip"}


def process_geospatial_file(file_path: Path) -> dict:
    """Load a geospatial file and return features plus measurements."""
    extension = file_path.suffix.lower()

    if extension == ".kml":
        gdf = _read_kml(file_path)
    elif extension == ".zip":
        gdf = _read_shapefile_zip(file_path)
    else:
        raise GeospatialFileError("Unsupported file type. Only .kml and .zip files are allowed.")

    if gdf.empty:
        crs = _crs_to_string(gdf)
        return {
            "feature_count": 0,
            "crs": crs,
            "features": [],
            "measurements": [],
        }

    crs = _crs_to_string(gdf)
    features = _extract_features(gdf, crs)
    measurements = calculate_measurements(gdf)

    return {
        "feature_count": len(features),
        "crs": crs,
        "features": features,
        "measurements": measurements,
    }


def _read_kml(file_path: Path) -> gpd.GeoDataFrame:
    try:
        return gpd.read_file(file_path, driver="KML")
    except GeospatialFileError:
        raise
    except Exception as exc:
        raise GeospatialFileError(
            "The uploaded KML file is invalid or corrupted."
        ) from exc


def _read_shapefile_zip(file_path: Path) -> gpd.GeoDataFrame:
    try:
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            _assert_zip_contains_shapefile(zip_ref)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                _extract_zip_safely(zip_ref, temp_path)

                shapefiles = list(temp_path.rglob("*.shp"))
                if not shapefiles:
                    raise GeospatialFileError("ZIP file does not contain a Shapefile.")

                try:
                    return gpd.read_file(shapefiles[0])
                except GeospatialFileError:
                    raise
                except Exception as exc:
                    raise GeospatialFileError(
                        "The uploaded Shapefile is invalid or corrupted."
                    ) from exc
    except zipfile.BadZipFile as exc:
        raise GeospatialFileError(
            "The uploaded ZIP file is corrupted or invalid."
        ) from exc
    except GeospatialFileError:
        raise
    except Exception as exc:
        raise GeospatialFileError(
            "The uploaded ZIP file could not be processed."
        ) from exc


def _assert_zip_contains_shapefile(zip_ref: zipfile.ZipFile) -> None:
    has_shp = any(
        Path(info.filename).suffix.lower() == ".shp"
        and not info.filename.endswith("/")
        for info in zip_ref.infolist()
    )
    if not has_shp:
        raise GeospatialFileError("ZIP file does not contain a Shapefile.")


def _extract_zip_safely(zip_ref: zipfile.ZipFile, destination: Path) -> None:
    """Extract ZIP members only if they stay inside ``destination``.

    This avoids Zip Slip / path traversal from crafted member names such as
    ``../../etc/passwd``.
    """
    destination = destination.resolve()

    for member in zip_ref.infolist():
        if not _is_safe_zip_member(destination, member.filename):
            raise GeospatialFileError("ZIP file contains an unsafe path.")
        zip_ref.extract(member, destination)


def _is_safe_zip_member(destination: Path, member_name: str) -> bool:
    if not member_name or member_name.startswith("/") or member_name.startswith("\\"):
        return False

    normalized = member_name.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ":" in path.parts[0]:
        return False

    target = (destination / path).resolve()
    try:
        target.relative_to(destination)
    except ValueError:
        return False
    return True


def _extract_features(gdf: gpd.GeoDataFrame, crs: str | None) -> list[dict]:
    geojson = json.loads(gdf.to_json())
    features: list[dict] = []

    for index, feature in enumerate(geojson.get("features", [])):
        geometry = feature.get("geometry")
        features.append(
            {
                "feature_id": index,
                "geometry_type": geometry["type"] if geometry else None,
                "geometry": geometry,
                "crs": crs,
                "properties": feature.get("properties") or {},
            }
        )

    return features


def _crs_to_string(gdf: gpd.GeoDataFrame) -> str | None:
    if gdf.crs is None:
        return None
    return gdf.crs.to_string()
