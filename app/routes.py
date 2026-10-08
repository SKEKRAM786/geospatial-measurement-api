"""HTTP routes for geospatial file upload, metadata, and measurements."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.exceptions import GeospatialFileError
from app.services.file_processor import ALLOWED_EXTENSIONS, process_geospatial_file

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/files",
    tags=["Files"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Temporary in-memory storage. Persistence will be added later.
files_db: dict[str, dict] = {}


@router.post("/")
async def upload_file(file: UploadFile | None = File(default=None)):
    """Upload a KML or zipped Shapefile and calculate measurements."""
    original_filename, extension = _validate_upload(file)
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}{extension}"
    file_path = UPLOAD_DIR / saved_filename

    try:
        file_path.write_bytes(contents)
        result = process_geospatial_file(file_path)
    except GeospatialFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error while processing uploaded file")
        raise HTTPException(
            status_code=400,
            detail="Failed to process geospatial file.",
        )

    files_db[file_id] = {
        "id": file_id,
        "filename": original_filename,
        "feature_count": result["feature_count"],
        "crs": result["crs"],
        "status": "COMPLETED",
        "features": result["features"],
        "measurements": result["measurements"],
    }

    return {
        "id": file_id,
        "filename": original_filename,
        "status": "COMPLETED",
        "feature_count": result["feature_count"],
        "crs": result["crs"],
        "features": result["features"],
        "measurements": result["measurements"],
    }


@router.get("/{file_id}/measurements/")
@router.get("/{file_id}/measurements", include_in_schema=False)
def get_file_measurements(file_id: str):
    """Return calculated measurements for an uploaded file."""
    file_info = _get_file_or_404(file_id)
    return {
        "file_id": file_info["id"],
        "filename": file_info["filename"],
        "measurements": file_info["measurements"],
    }


@router.get("/{file_id}/")
@router.get("/{file_id}", include_in_schema=False)
def get_file_info(file_id: str):
    """Return stored metadata for an uploaded file."""
    file_info = _get_file_or_404(file_id)
    return {
        "id": file_info["id"],
        "filename": file_info["filename"],
        "feature_count": file_info["feature_count"],
        "crs": file_info["crs"],
        "status": file_info["status"],
    }


def _validate_upload(file: UploadFile | None) -> tuple[str, str]:
    if file is None:
        raise HTTPException(
            status_code=400,
            detail="A file upload is required.",
        )

    original_filename = file.filename or ""
    if not original_filename.strip():
        raise HTTPException(
            status_code=400,
            detail="A file upload is required.",
        )

    # Only the extension is used for type checks. Stored paths always use a UUID.
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .kml and .zip files are allowed.",
        )

    return original_filename, extension


def _get_file_or_404(file_id: str) -> dict:
    file_info = files_db.get(file_id)
    if file_info is None:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )
    return file_info
