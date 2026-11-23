import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings
from app.database import db

logger = logging.getLogger(__name__)

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

# Rate-limiting lock to respect Nominatim usage policy (max 1 request per second)
_nominatim_lock = asyncio.Lock()
_last_request_timestamp: float = 0.0


def clean_district_name(name: str) -> str:
    """Trim excessive suffix words like 'район', 'tumani' for compact address display."""
    if not name:
        return ""
    cleaned = re.sub(r"\s+(район|тумани|tumani|district|shahar)$", "", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"ский$", "", cleaned, flags=re.IGNORECASE)  # Чиланзарский -> Чиланзар
    return cleaned.strip()


def format_short_address(data: Dict[str, Any], lang: str = "ru") -> Optional[str]:
    """
    Format Nominatim reverse geocoding JSON response into clean, concise human-readable address.
    Optimized for Tashkent and Uzbekistan urban layout (quarters, mahallas, avenues, house numbers, POI).
    """
    if not data or not isinstance(data, dict):
        return None

    address = data.get("address", {})
    poi_name = data.get("name") or address.get("amenity") or address.get("shop") or address.get("tourism")

    # 1. House number
    raw_house = address.get("house_number")
    house_str = ""
    if raw_house:
        raw_house = str(raw_house).strip()
        if lang == "uz":
            house_str = f"{raw_house}-uy" if not raw_house.endswith("-uy") else raw_house
        else:
            house_str = f"дом {raw_house}" if not raw_house.lower().startswith("дом") else raw_house

    # 2. Road / Street
    road = address.get("road") or address.get("pedestrian") or address.get("footway") or address.get("path")
    if road:
        road = road.strip()

    # 3. Quarter / Neighbourhood / Mahalla (very common in Tashkent: 26-й квартал, Чиланзар-26)
    quarter = address.get("quarter") or address.get("neighbourhood") or address.get("residential")
    if quarter:
        quarter = quarter.strip()

    # 4. Suburb / District (Чиланзар, Юнусабад, Мирзо-Улугбек)
    suburb = address.get("suburb") or address.get("city_district")
    if suburb:
        suburb = clean_district_name(suburb)

    parts: List[str] = []

    # Include prominent POI name if it's not a mere number and doesn't equal road
    if poi_name and not poi_name.isdigit() and poi_name != raw_house:
        poi_clean = poi_name.strip()
        if not road or poi_clean.lower() != road.lower():
            parts.append(poi_clean)

    # Add district / suburb if useful and not duplicated in quarter
    if suburb and (not quarter or suburb.lower() not in quarter.lower()):
        # Avoid redundant district if road already has it
        if not road or suburb.lower() not in road.lower():
            parts.append(suburb)

    # Add quarter / mahalla
    if quarter:
        parts.append(quarter)

    # Add street / road
    if road and (not quarter or road.lower() not in quarter.lower()):
        parts.append(road)

    # Add house number
    if house_str:
        parts.append(house_str)

    # Deduplicate while preserving order
    seen = set()
    deduped_parts = []
    for p in parts:
        p_low = p.lower()
        if p_low not in seen:
            seen.add(p_low)
            deduped_parts.append(p)

    if deduped_parts:
        return ", ".join(deduped_parts)

    # Fallback to city/town if no specific street or quarter
    fallback_city = address.get("city") or address.get("town") or address.get("village") or address.get("county")
    if fallback_city:
        return fallback_city

    return None


async def reverse_geocode(lat: float, lon: float, lang: str = "ru") -> str:
    """
    Reverse geocode coordinates (lat, lon) to a short human-readable address.
    Checks SQLite cache first. If not cached, queries OpenStreetMap Nominatim API
    with safe rate-limiting (~1 request/sec).
    """
    global _last_request_timestamp

    if lang not in ("ru", "uz"):
        lang = "ru"

    # 1. Check local SQLite cache first (instant)
    try:
        cached = await db.get_cached_address(lat, lon, lang)
        if cached:
            return cached
    except Exception as exc:
        logger.warning("Error checking geocache for (%s, %s): %s", lat, lon, exc)

    # 2. Acquire rate-limiting lock for Nominatim API
    accept_lang = "ru" if lang == "ru" else "uz,ru"
    url = (
        f"{NOMINATIM_REVERSE_URL}?format=jsonv2&lat={lat:.6f}&lon={lon:.6f}"
        f"&zoom=18&addressdetails=1&accept-language={accept_lang}"
    )
    headers = {
        "User-Agent": settings.GEOCODER_USER_AGENT,
    }

    data = None
    async with _nominatim_lock:
        now = time.monotonic()
        elapsed = now - _last_request_timestamp
        if elapsed < 1.05:
            await asyncio.sleep(1.05 - elapsed)

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                _last_request_timestamp = time.monotonic()
                if resp.status_code == 200:
                    data = resp.json()
                else:
                    logger.warning("Nominatim HTTP %s for (%s, %s): %s", resp.status_code, lat, lon, resp.text)
        except Exception as exc:
            _last_request_timestamp = time.monotonic()
            logger.warning("Nominatim reverse geocode exception for (%s, %s): %s", lat, lon, exc)

    # 3. Format address or fallback to clean coordinates
    address_str = format_short_address(data, lang=lang) if data else None

    if not address_str:
        # Graceful fallback to formatted coordinates
        address_str = f"{lat:.5f}, {lon:.5f}"

    # 4. Save to SQLite cache for future instant lookups
    try:
        await db.save_cached_address(lat, lon, lang, address_str)
    except Exception as exc:
        logger.warning("Could not save to geocache: %s", exc)

    return address_str


async def enrich_points_with_addresses(
    points: List[Dict[str, Any]],
    lang: str = "ru",
) -> List[Dict[str, Any]]:
    """
    Enrich a list of route points dictionaries with a short human-readable 'address' field.
    Point A preserves custom admin title if set; otherwise resolves via reverse geocoding.
    """
    for pt in points:
        label = pt.get("label", "")
        existing_name = pt.get("name", "")

        # If Point A has custom admin name (not generic 'Точка А' or coordinates), use it
        if label == "A" and existing_name and existing_name not in ("Точка А", "A Nuqtasi", "Точка отправления"):
            # Check if name is not purely coordinates
            if not re.match(r"^\d+\.\d+,\s*\d+\.\d+$", existing_name.strip()):
                pt["address"] = existing_name
                continue

        # Resolve address via reverse geocoding
        lat = float(pt["lat"])
        lon = float(pt["lon"])
        addr = await reverse_geocode(lat, lon, lang=lang)
        pt["address"] = addr

    return points
