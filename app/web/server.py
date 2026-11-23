import logging
from pathlib import Path
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import db
from app.services.routing import get_car_route, RouteError

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Suv Bot Route Service & Mini App",
    description="Backend API and Telegram Mini App for driving route calculation",
    version="2.0.0",
)

# Allow CORS for development and cross-origin iframe usage in Telegram Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/api/health", methods=["GET", "HEAD"])
async def health_check() -> Dict[str, str]:
    """Health check endpoint to verify web server status (supports GET and HEAD)."""
    return {"status": "ok", "service": "suv-bot-routing"}


@app.get("/api/origin")
async def get_origin_endpoint() -> Dict[str, Any]:
    """Fetch current Origin Point A configured by admin."""
    origin = await db.get_origin()
    return {"status": "ok", "origin": origin}


@app.get("/api/route/{route_id}")
async def get_saved_route_endpoint(route_id: str) -> Dict[str, Any]:
    """Fetch previously calculated multi-stop route payload by unique route_id."""
    payload = await db.get_route(route_id)
    if not payload:
        raise HTTPException(
            status_code=404,
            detail="Route not found or has expired",
        )
    return {
        "status": "ok",
        "route_id": route_id,
        **payload,
    }


@app.get("/api/route")
async def calculate_route_endpoint(
    dest_lat: float = Query(..., description="Destination latitude (-90 to 90)"),
    dest_lon: float = Query(..., description="Destination longitude (-180 to 180)"),
) -> Dict[str, Any]:
    """
    Backwards-compatible: calculate driving route from Origin Point A to user's Destination (Point B).
    """
    if not (-90.0 <= dest_lat <= 90.0 and -180.0 <= dest_lon <= 180.0):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid destination coordinates: lat={dest_lat}, lon={dest_lon}",
        )

    origin = await db.get_origin()
    origin_lat = origin.get("lat")
    origin_lon = origin.get("lon")
    origin_name = origin.get("name", "Точка отправления")

    if origin_lat is None or origin_lon is None:
        raise HTTPException(
            status_code=500,
            detail="Origin Point A is not configured",
        )

    try:
        route_result = await get_car_route(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
        )
    except RouteError as err:
        logger.warning("Routing error for dest (%s, %s): %s", dest_lat, dest_lon, err)
        raise HTTPException(
            status_code=400,
            detail=str(err),
        )
    except Exception as exc:
        logger.exception("Unexpected error during route calculation: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Failed to connect to route engine",
        )

    return {
        "status": "ok",
        "origin": {
            "lat": origin_lat,
            "lon": origin_lon,
            "name": origin_name,
        },
        "destination": {
            "lat": dest_lat,
            "lon": dest_lon,
        },
        "route": {
            "distance_km": route_result.distance_km,
            "duration_min": route_result.duration_min,
            "coordinates": route_result.coordinates,
            "summary": route_result.summary,
        },
    }


# Mount static directory for Mini App frontend files (index.html, styles.css, app.js)
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
