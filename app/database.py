import json
import os
from typing import Any, Dict, List, Optional, Tuple
import aiosqlite
from app.config import settings


class Database:
    """Asynchronous SQLite database manager for user preferences, bot settings, drafts, and routes."""

    def __init__(self, db_path: str = settings.DB_PATH) -> None:
        self.db_path = db_path

    async def init_db(self) -> None:
        """Initialize SQLite database tables and seed default origin settings if empty."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    lang TEXT NOT NULL DEFAULT 'ru',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS draft_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    custom_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # Safe column migration if table already exists
            try:
                await db.execute("ALTER TABLE draft_points ADD COLUMN custom_name TEXT")
                await db.commit()
            except Exception:
                pass
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS routes (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS geocache (
                    lat_round REAL NOT NULL,
                    lon_round REAL NOT NULL,
                    lang TEXT NOT NULL,
                    address TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (lat_round, lon_round, lang)
                );
                """
            )
            await db.commit()

            # Seed default origin point from config if not yet set in database
            cursor = await db.execute("SELECT key FROM settings WHERE key IN ('origin_lat', 'origin_lon', 'origin_name')")
            existing_keys = {row[0] for row in await cursor.fetchall()}

            if "origin_lat" not in existing_keys:
                await db.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    ("origin_lat", str(settings.DEFAULT_ORIGIN_LAT)),
                )
            if "origin_lon" not in existing_keys:
                await db.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    ("origin_lon", str(settings.DEFAULT_ORIGIN_LON)),
                )
            if "origin_name" not in existing_keys:
                await db.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    ("origin_name", str(settings.DEFAULT_ORIGIN_NAME)),
                )
            await db.commit()

    async def get_user_lang(self, user_id: int) -> str:
        """Get preferred language for a user ('ru' or 'uz'). Default is 'ru'."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
            return "ru"

    async def set_user_lang(self, user_id: int, lang: str) -> None:
        """Create or update user language preference."""
        if lang not in ("ru", "uz"):
            lang = "ru"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, lang)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang
                """,
                (user_id, lang),
            )
            await db.commit()

    async def get_origin(self) -> Dict[str, Any]:
        """Fetch current Origin Point A (lat, lon, name) from settings table."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT key, value FROM settings WHERE key IN ('origin_lat', 'origin_lon', 'origin_name')")
            rows = await cursor.fetchall()
            settings_map = {row[0]: row[1] for row in rows}

            lat = float(settings_map.get("origin_lat", settings.DEFAULT_ORIGIN_LAT))
            lon = float(settings_map.get("origin_lon", settings.DEFAULT_ORIGIN_LON))
            name = settings_map.get("origin_name", settings.DEFAULT_ORIGIN_NAME)

            return {
                "lat": lat,
                "lon": lon,
                "name": name,
            }

    async def set_origin(self, lat: float, lon: float, name: Optional[str] = None) -> None:
        """Update Origin Point A coordinates and optional custom name."""
        origin_name = name.strip() if name and name.strip() else f"{lat:.4f}, {lon:.4f}"
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                [
                    ("origin_lat", str(lat)),
                    ("origin_lon", str(lon)),
                    ("origin_name", origin_name),
                ],
            )
            await db.commit()

    # -----------------------------------------------------------------------
    # Draft Waypoints Management (multi-stop routing session)
    # -----------------------------------------------------------------------

    async def cleanup_expired_drafts(self, user_id: Optional[int] = None, ttl_minutes: int = settings.DRAFT_TTL_MINUTES) -> None:
        """Remove draft points older than ttl_minutes."""
        async with aiosqlite.connect(self.db_path) as db:
            if user_id is not None:
                await db.execute(
                    "DELETE FROM draft_points WHERE user_id = ? AND created_at <= datetime('now', '-' || ? || ' minutes')",
                    (user_id, ttl_minutes),
                )
            else:
                await db.execute(
                    "DELETE FROM draft_points WHERE created_at <= datetime('now', '-' || ? || ' minutes')",
                    (ttl_minutes,),
                )
            await db.commit()

    async def add_draft_point(self, user_id: int, lat: float, lon: float, custom_name: Optional[str] = None) -> int:
        """Add a single waypoint to user's active route draft with optional custom name."""
        await self.cleanup_expired_drafts(user_id)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO draft_points (user_id, lat, lon, custom_name) VALUES (?, ?, ?, ?)",
                (user_id, lat, lon, custom_name.strip() if custom_name else None),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_draft_points(self, user_id: int, ttl_minutes: int = settings.DRAFT_TTL_MINUTES) -> List[Tuple[float, float, Optional[str]]]:
        """Fetch all active draft points for user in insertion order [(lat, lon, custom_name), ...]."""
        await self.cleanup_expired_drafts(user_id, ttl_minutes)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT lat, lon, custom_name FROM draft_points WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [(float(r[0]), float(r[1]), r[2]) for r in rows]

    async def get_draft_points_records(self, user_id: int, ttl_minutes: int = settings.DRAFT_TTL_MINUTES) -> List[Dict[str, Any]]:
        """Fetch full draft point records for user: [{'id': id, 'lat': lat, 'lon': lon, 'custom_name': name}, ...]"""
        await self.cleanup_expired_drafts(user_id, ttl_minutes)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, lat, lon, custom_name FROM draft_points WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [{"id": r[0], "lat": float(r[1]), "lon": float(r[2]), "custom_name": r[3]} for r in rows]

    async def update_draft_point_name(self, point_id: int, custom_name: str) -> None:
        """Update custom name of a draft point by its database ID."""
        cleaned_name = custom_name.strip() if custom_name else None
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE draft_points SET custom_name = ? WHERE id = ?",
                (cleaned_name, point_id),
            )
            await db.commit()

    async def update_draft_point_name_by_index(self, user_id: int, index: int, custom_name: str) -> bool:
        """Update custom name for the N-th draft point (0-indexed) of user."""
        records = await self.get_draft_points_records(user_id)
        if 0 <= index < len(records):
            point_id = records[index]["id"]
            await self.update_draft_point_name(point_id, custom_name)
            return True
        return False

    async def clear_draft_points(self, user_id: int) -> int:
        """Clear all active draft points for user. Returns number of deleted rows."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM draft_points WHERE user_id = ?", (user_id,))
            await db.commit()
            return cursor.rowcount

    # -----------------------------------------------------------------------
    # Calculated Routes Storage (cached by route_id)
    # -----------------------------------------------------------------------

    async def save_route(self, route_id: str, user_id: int, payload: Dict[str, Any]) -> None:
        """Store calculated route payload as JSON by route_id."""
        payload_str = json.dumps(payload, ensure_ascii=False)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO routes (id, user_id, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (route_id, user_id, payload_str),
            )
            await db.commit()

    async def get_route(self, route_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve calculated route payload by route_id."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT payload_json FROM routes WHERE id = ?", (route_id,))
            row = await cursor.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception:
                    return None
            return None

    # -----------------------------------------------------------------------
    # Geocache Storage (Reverse Geocoding Cache)
    # -----------------------------------------------------------------------

    async def get_cached_address(self, lat: float, lon: float, lang: str = "ru") -> Optional[str]:
        """Fetch cached human-readable address for rounded coordinates (5 decimal places)."""
        lat_round = round(float(lat), 5)
        lon_round = round(float(lon), 5)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT address FROM geocache WHERE lat_round = ? AND lon_round = ? AND lang = ?",
                (lat_round, lon_round, lang),
            )
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
            return None

    async def save_cached_address(self, lat: float, lon: float, lang: str, address: str) -> None:
        """Cache human-readable address by rounded coordinates and language."""
        lat_round = round(float(lat), 5)
        lon_round = round(float(lon), 5)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO geocache (lat_round, lon_round, lang, address)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(lat_round, lon_round, lang) DO UPDATE SET address = excluded.address
                """,
                (lat_round, lon_round, lang, address),
            )
            await db.commit()


db = Database()
