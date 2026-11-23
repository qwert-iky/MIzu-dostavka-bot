import logging
import math
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving/"


class RouteError(Exception):
    """Raised when route calculation fails or no drivable route is found."""
    pass


@dataclass
class RouteResult:
    """Calculated car route details for a single destination."""
    distance_km: float
    duration_min: float
    coordinates: List[List[float]]  # Array of [latitude, longitude] for Leaflet
    summary: str = ""


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth in kilometers.
    """
    radius = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius * c


def order_waypoints(
    origin: Dict[str, Any],
    destinations: List[Any],
) -> List[Dict[str, Any]]:
    """
    Sort destination waypoints using Nearest Neighbor algorithm starting strictly from Point A.

    - Point B: closest to Point A
    - Point C: closest to Point B
    - Point D, E...: next closest in chain
    Labels are assigned alphabetically: B, C, D, ...
    Preserves custom_name if provided in destinations tuples or dicts.
    """
    if not destinations:
        return []

    labels = [
        "B", "C", "D", "E", "F", "G", "H", "I", "J", "K",
        "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U",
        "V", "W", "X", "Y", "Z"
    ]

    current_lat = float(origin["lat"])
    current_lon = float(origin["lon"])

    # Normalize remaining points into (lat, lon, custom_name, id)
    normalized = []
    for item in destinations:
        if isinstance(item, dict):
            normalized.append((float(item["lat"]), float(item["lon"]), item.get("custom_name"), item.get("id")))
        elif isinstance(item, (list, tuple)):
            c_name = item[2] if len(item) > 2 else None
            p_id = item[3] if len(item) > 3 else None
            normalized.append((float(item[0]), float(item[1]), c_name, p_id))

    remaining = normalized
    ordered: List[Dict[str, Any]] = []

    while remaining:
        # Pick the point closest to current position
        best_idx = min(
            range(len(remaining)),
            key=lambda i: haversine_km(current_lat, current_lon, remaining[i][0], remaining[i][1]),
        )
        best_lat, best_lon, custom_name, point_id = remaining.pop(best_idx)
        label = labels[len(ordered)] if len(ordered) < len(labels) else f"W{len(ordered) + 1}"

        point_name = custom_name.strip() if custom_name and str(custom_name).strip() else f"Точка {label}"

        ordered.append({
            "id": point_id,
            "label": label,
            "lat": round(best_lat, 6),
            "lon": round(best_lon, 6),
            "name": point_name,
            "custom_name": custom_name.strip() if custom_name and str(custom_name).strip() else None,
        })
        current_lat, current_lon = best_lat, best_lon

    return ordered


def convert_osrm_geometry_to_leaflet(osrm_geojson_coords: List[List[float]]) -> List[List[float]]:
    """
    Convert GeoJSON coordinates from OSRM format [longitude, latitude]
    to Leaflet Polyline format [latitude, longitude].
    """
    leaflet_coords: List[List[float]] = []
    for point in osrm_geojson_coords:
        if len(point) >= 2:
            lon = float(point[0])
            lat = float(point[1])
            leaflet_coords.append([lat, lon])
    return leaflet_coords


async def build_multi_route(
    origin: Dict[str, Any],
    destinations: List[Tuple[float, float]],
    timeout_sec: float = 12.0,
) -> Dict[str, Any]:
    """
    Build a multi-stop car route A -> B -> C -> ...
    Waypoints are ordered using Nearest Neighbor starting from Point A.

    Returns structured payload with points, legs, coordinates, total distance, and duration.
    """
    if not destinations:
        raise RouteError("No destination waypoints provided")

    origin_lat = float(origin["lat"])
    origin_lon = float(origin["lon"])
    origin_name = origin.get("name", "Точка А")

    ordered_destinations = order_waypoints(origin, destinations)

    # Point A definition
    point_a = {
        "label": "A",
        "name": origin_name,
        "lat": round(origin_lat, 6),
        "lon": round(origin_lon, 6),
    }

    all_points = [point_a] + ordered_destinations

    # Build coordinate string for OSRM URL: lon1,lat1;lon2,lat2;...
    coords_str = ";".join(f"{p['lon']:.6f},{p['lat']:.6f}" for p in all_points)
    url = f"{OSRM_BASE_URL}{coords_str}?overview=full&geometries=geojson&steps=true"

    data = None
    # Try httpx first with 15s timeout, fallback to aiohttp if httpx fails
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.get(url, headers={"User-Agent": "SuvBotRoutePlanner/2.0"})
            if resp.status_code == 200:
                data = resp.json()
            else:
                logger.warning("OSRM returned HTTP %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.info("httpx request failed, falling back to aiohttp: %s", exc)

    if not data:
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout_sec)) as session:
                async with session.get(url, headers={"User-Agent": "SuvBotRoutePlanner/2.0"}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                    else:
                        text = await resp.text()
                        logger.error("OSRM aiohttp error %s: %s", resp.status, text)
                        raise RouteError(f"OSRM returned HTTP {resp.status}")
        except Exception as exc:
            logger.warning("OSRM request exception: %s", exc)
            raise RouteError(f"Network error while connecting to OSRM: {exc}") from exc

    if not data or data.get("code") != "Ok":
        error_msg = data.get("message", "No driving route found") if data else "Empty response"
        logger.warning("OSRM calculation failed: %s", error_msg)
        raise RouteError(f"No route found: {error_msg}")

    routes = data.get("routes")
    if not routes or len(routes) == 0:
        raise RouteError("OSRM returned no route paths")

    best_route = routes[0]
    total_distance_km = round(float(best_route.get("distance", 0.0)) / 1000.0, 2)
    total_duration_min = round(float(best_route.get("duration", 0.0)) / 60.0, 1)

    raw_full_coords = best_route.get("geometry", {}).get("coordinates", [])
    full_leaflet_coords = convert_osrm_geometry_to_leaflet(raw_full_coords)

    # Process individual route legs (A -> B, B -> C, ...)
    legs = best_route.get("legs", [])
    processed_legs: List[Dict[str, Any]] = []

    for i, leg in enumerate(legs):
        from_pt = all_points[i]
        to_pt = all_points[i + 1]
        leg_dist = round(float(leg.get("distance", 0.0)) / 1000.0, 2)
        leg_dur = round(float(leg.get("duration", 0.0)) / 60.0, 1)

        # Reconstruct leg geometry from steps
        leg_coords_geojson: List[List[float]] = []
        for step in leg.get("steps", []):
            step_coords = step.get("geometry", {}).get("coordinates", [])
            for pt in step_coords:
                if not leg_coords_geojson or leg_coords_geojson[-1] != pt:
                    leg_coords_geojson.append(pt)

        if not leg_coords_geojson:
            leg_coords_geojson = [[from_pt["lon"], from_pt["lat"]], [to_pt["lon"], to_pt["lat"]]]

        leg_leaflet_coords = convert_osrm_geometry_to_leaflet(leg_coords_geojson)

        processed_legs.append({
            "from_label": from_pt["label"],
            "to_label": to_pt["label"],
            "from_name": from_pt.get("name", f"Точка {from_pt['label']}"),
            "to_name": to_pt.get("name", f"Точка {to_pt['label']}"),
            "from_custom_name": from_pt.get("custom_name"),
            "to_custom_name": to_pt.get("custom_name"),
            "distance_km": leg_dist,
            "duration_min": leg_dur,
            "coordinates": leg_leaflet_coords,
            "summary": leg.get("summary", ""),
        })

    return {
        "origin": point_a,
        "points": all_points,
        "legs": processed_legs,
        "total_distance_km": total_distance_km,
        "total_duration_min": total_duration_min,
        "full_coordinates": full_leaflet_coords,
    }


async def get_car_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    timeout_sec: float = 10.0,
) -> Optional[RouteResult]:
    """
    Backwards-compatible helper: single destination route calculation.
    """
    origin = {"lat": origin_lat, "lon": origin_lon, "name": "Точка А"}
    multi = await build_multi_route(origin, [(dest_lat, dest_lon)], timeout_sec=timeout_sec)
    return RouteResult(
        distance_km=multi["total_distance_km"],
        duration_min=multi["total_duration_min"],
        coordinates=multi["full_coordinates"],
        summary=multi["legs"][0]["summary"] if multi["legs"] else "",
    )
