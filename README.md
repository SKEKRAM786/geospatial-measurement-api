# Geospatial File Measurement API

FastAPI service that accepts KML files and zipped Shapefiles, extracts geospatial features, and calculates metric area and length. Uploaded files are stored under UUID filenames; processing results are kept in memory for this version.

## Features

- Upload `.kml` or `.zip` (Shapefile) files
- Extract features and geometry types
- Calculate polygon / multipolygon **area** in square metres
- Calculate linestring / multilinestring **length** in metres
- Handle points without inventing a measurement
- Skip unsupported geometries without failing the whole request
- Transform geographic coordinates to a projected CRS before measuring
- Reject invalid extensions, empty uploads, corrupted files, unsafe ZIP paths, and missing CRS
- Swagger UI at `/docs`

## Tech stack

- Python 3
- FastAPI
- Uvicorn
- GeoPandas
- Shapely
- PyProj
- pytest

## Installation / setup

From the project root:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

On macOS/Linux, activate with `source venv/bin/activate`.

## How to run the server

```bash
uvicorn app.main:app --reload
```

The API listens on `http://127.0.0.1:8000`.

## Swagger URL

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

OpenAPI schema: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

## API endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Health check |
| `POST` | `/api/files/` | Upload a `.kml` or `.zip` file and process it |
| `GET` | `/api/files/{id}/` | File metadata (`feature_count`, `crs`, `status`) |
| `GET` | `/api/files/{id}/measurements/` | Calculated measurements |

Paths without a trailing slash are also accepted so existing clients keep working.

### `POST /api/files/`

Multipart form field: `file`.

Successful response includes `id`, original `filename`, `status`, `feature_count`, `crs`, `features`, and `measurements`. Stored files use `{uuid}{extension}` under `uploads/` and never use the original name as a filesystem path.

### `GET /api/files/{id}/`

Returns file information without the full feature/measurement payloads.

### `GET /api/files/{id}/measurements/`

Returns `{ "file_id", "filename", "measurements" }`.

## Supported file formats

- **KML** (`.kml`)
- **Zipped Shapefile** (`.zip`) that contains at least one `.shp` file, plus the usual sidecar files

Other extensions return HTTP 400.

## Processing flow

1. Validate that a file is present, non-empty, and has a `.kml` or `.zip` extension.
2. Save bytes to `uploads/{uuid}{extension}`.
3. Read geometries:
   - KML via GeoPandas (`driver="KML"`)
   - ZIP: confirm a `.shp` member exists, extract into a temporary directory with Zip Slip checks, then read the Shapefile
4. If the GeoDataFrame is empty, return `feature_count = 0` and `measurements = []`.
5. Require a CRS for non-empty data.
6. Extract GeoJSON features and calculate measurements.
7. Store metadata in the in-memory `files_db`.

Temporary ZIP extraction directories are created with `tempfile.TemporaryDirectory` and deleted automatically.

## Measurement logic

| Geometry | Result |
| --- | --- |
| Polygon, MultiPolygon | `measurement.type = "area"`, unit `m²` |
| LineString, MultiLineString | `measurement.type = "length"`, unit `m` |
| Point | `measurement = null` and a message that no measurement is required |
| Anything else | `measurement = null` and a message naming the unsupported type |

Unsupported or empty geometries do not abort processing of other features.

## CRS handling

Area and length **cannot** be calculated directly from EPSG:4326 (or any geographic CRS) in latitude/longitude **degrees**.

A degree of longitude is not a fixed distance: it shrinks toward the poles. A degree of latitude is also not exactly one metre. Using `geometry.area` or `geometry.length` on lon/lat data therefore produces values in “square degrees” or “degrees”, which are not real-world metres.

This API:

- Refuses files that have features but no CRS
- If the CRS is geographic (`is_geographic`), transforms the data with GeoPandas `estimate_utm_crs()` to a local UTM projected CRS (units: metres)
- Then calculates area/length
- Returns HTTP 400 if a suitable projected CRS cannot be determined

Already-projected data is measured in its existing CRS.

## Error handling

Clients receive JSON `{"detail": "..."}` without Python tracebacks.

| Situation | Status |
| --- | --- |
| Unsupported extension | 400 |
| Missing or empty upload | 400 |
| Corrupted KML or ZIP | 400 |
| ZIP with no `.shp` | 400 |
| ZIP path traversal | 400 |
| Missing CRS | 400 |
| Cannot estimate projected CRS | 400 |
| Unknown file id | 404 |

## Project architecture

```
GEOSPATIAL-MEASUREMENT-API/
├── app/
│   ├── main.py                 # FastAPI app and error handlers
│   ├── routes.py               # HTTP endpoints and in-memory files_db
│   ├── exceptions.py           # GeospatialFileError
│   └── services/
│       ├── file_processor.py   # Read KML / safe ZIP Shapefile extraction
│       └── measurement.py      # CRS transform and measurements
├── tests/
├── uploads/
├── requirements.txt
└── README.md
```

## Testing instructions

```bash
pytest
```

Tests use FastAPI `TestClient` only. They do not need a database or external services. Sample KML and Shapefile ZIP payloads are built in-memory.

## Design decisions

- **UUID storage names** so original filenames cannot be used for path traversal
- **Safe ZIP extraction** instead of a raw `extractall()`
- **Temporary directories** for Shapefile unzip so extracted files are not left on disk
- **In-memory `files_db`** until persistence is added
- **Per-feature measurement failures** (unsupported geometry) do not fail the upload
- **UTM estimation** as a practical projected CRS for local area/length without extra dependencies

## Limitations

- Results are lost on process restart (no database)
- Only the first `.shp` in a ZIP is read
- Very large uploads are not size-limited yet
- KML support depends on the local GDAL/GeoPandas KML driver
- Measurements assume the source CRS is correct

## Future improvements

- Persist file metadata in a database
- Background processing for large files
- GeoJSON and GeoPackage upload support
- Explicit user-supplied CRS override
- Configurable maximum upload size
- Authentication and per-user file isolation
