from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import GeospatialFileError
from app.routes import router

app = FastAPI(
    title="Geospatial File Measurement API",
    description="API for processing KML and Shapefile files and calculating measurements.",
    version="1.0.0",
)

app.include_router(router)


@app.exception_handler(GeospatialFileError)
async def geospatial_file_error_handler(
    request: Request,
    exc: GeospatialFileError,
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/")
def root():
    return {
        "message": "Geospatial File Measurement API is running"
    }
