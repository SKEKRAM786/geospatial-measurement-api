from __future__ import annotations

from tests.helpers import (
    CORRUPT_KML,
    LINESTRING_KML,
    POINT_KML,
    POLYGON_KML,
    linestring_geodataframe,
    multipoint_geodataframe,
    point_geodataframe,
    polygon_geodataframe,
    shapefile_zip_bytes,
    zip_without_shapefile,
)


def upload(client, filename: str, content: bytes, content_type: str = "application/octet-stream"):
    return client.post(
        "/api/files/",
        files={"file": (filename, content, content_type)},
    )


def test_successful_kml_upload(client):
    response = upload(client, "sample.kml", POLYGON_KML.encode("utf-8"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["feature_count"] == 1
    assert payload["features"][0]["geometry_type"] in {"Polygon", "MultiPolygon"}
    assert payload["measurements"][0]["measurement"]["type"] == "area"
    assert payload["measurements"][0]["measurement"]["unit"] == "m²"
    assert payload["measurements"][0]["measurement"]["value"] > 0


def test_successful_zip_shapefile_upload(client):
    content = shapefile_zip_bytes(polygon_geodataframe())
    response = upload(client, "features.zip", content)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["feature_count"] == 1
    assert payload["filename"] == "features.zip"
    assert payload["measurements"][0]["measurement"]["type"] == "area"


def test_invalid_file_extension(client):
    response = upload(client, "notes.txt", b"hello")
    assert response.status_code == 400
    assert "Only .kml and .zip" in response.json()["detail"]


def test_empty_upload(client):
    response = upload(client, "empty.kml", b"")
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_corrupted_zip(client):
    response = upload(client, "broken.zip", b"this is not a zip file")
    assert response.status_code == 400
    assert "corrupted" in response.json()["detail"].lower()


def test_corrupted_kml(client):
    response = upload(client, "broken.kml", CORRUPT_KML)
    assert response.status_code == 400
    assert "kml" in response.json()["detail"].lower()


def test_zip_without_shp(client):
    response = upload(client, "noshp.zip", zip_without_shapefile())
    assert response.status_code == 400
    assert "shapefile" in response.json()["detail"].lower()


def test_missing_crs(client):
    gdf = polygon_geodataframe(crs=None)
    content = shapefile_zip_bytes(gdf, include_prj=False)
    response = upload(client, "nocrs.zip", content)
    assert response.status_code == 400
    assert "crs" in response.json()["detail"].lower()


def test_polygon_measurement(client):
    response = upload(client, "polygon.kml", POLYGON_KML.encode("utf-8"))
    measurement = response.json()["measurements"][0]["measurement"]
    assert measurement["type"] == "area"
    assert measurement["unit"] == "m²"
    assert measurement["value"] > 0


def test_linestring_measurement(client):
    response = upload(client, "line.kml", LINESTRING_KML.encode("utf-8"))
    assert response.status_code == 200
    measurement = response.json()["measurements"][0]["measurement"]
    assert measurement["type"] == "length"
    assert measurement["unit"] == "m"
    assert measurement["value"] > 0


def test_point_handling(client):
    response = upload(client, "point.kml", POINT_KML.encode("utf-8"))
    assert response.status_code == 200
    result = response.json()["measurements"][0]
    assert result["geometry_type"] == "Point"
    assert result["measurement"] is None
    assert "no measurement required" in result["message"].lower()


def test_unsupported_geometry_handling(client):
    content = shapefile_zip_bytes(multipoint_geodataframe())
    response = upload(client, "multipoint.zip", content)
    assert response.status_code == 200
    result = response.json()["measurements"][0]
    assert result["measurement"] is None
    assert "not supported" in result["message"].lower()
    assert "MultiPoint" in result["message"]


def test_file_not_found(client):
    response = client.get("/api/files/does-not-exist/")
    assert response.status_code == 404
    assert response.json()["detail"] == "File not found."


def test_file_information_endpoint(client):
    created = upload(client, "sample.kml", POLYGON_KML.encode("utf-8")).json()
    file_id = created["id"]

    response = client.get(f"/api/files/{file_id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == file_id
    assert payload["filename"] == "sample.kml"
    assert payload["status"] == "COMPLETED"
    assert payload["feature_count"] == 1
    assert "features" not in payload
    assert "measurements" not in payload

    # Existing clients that omit the trailing slash should still succeed.
    without_slash = client.get(f"/api/files/{file_id}")
    assert without_slash.status_code == 200
    assert without_slash.json()["id"] == file_id


def test_measurements_endpoint(client):
    created = upload(client, "line.zip", shapefile_zip_bytes(linestring_geodataframe())).json()
    file_id = created["id"]

    response = client.get(f"/api/files/{file_id}/measurements/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["file_id"] == file_id
    assert payload["filename"] == "line.zip"
    assert payload["measurements"][0]["measurement"]["type"] == "length"

    without_slash = client.get(f"/api/files/{file_id}/measurements")
    assert without_slash.status_code == 200
    assert without_slash.json()["file_id"] == file_id


def test_zip_path_traversal_is_rejected(client):
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("../evil.shp", b"not a real shapefile")
    response = upload(client, "traversal.zip", buffer.getvalue())
    assert response.status_code == 400
    assert "unsafe" in response.json()["detail"].lower() or "shapefile" in response.json()["detail"].lower()


def test_point_shapefile_and_linestring_shapefile(client):
    point_response = upload(client, "point.zip", shapefile_zip_bytes(point_geodataframe()))
    assert point_response.status_code == 200
    assert point_response.json()["measurements"][0]["measurement"] is None
