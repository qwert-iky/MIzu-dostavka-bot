import os
from typing import Any, List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    BOT_TOKEN: str = ""
    ADMIN_IDS: Union[List[int], str] = []
    WEBAPP_URL: str = "http://localhost:8000"

    DEFAULT_ORIGIN_LAT: float = 41.2858
    DEFAULT_ORIGIN_LON: float = 69.2036
    DEFAULT_ORIGIN_NAME: str = "Фархадский базар (Farhod bozori)"

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DB_PATH: str = "data/bot.db"

    MAX_WAYPOINTS: int = 10
    DRAFT_TTL_MINUTES: int = 30
    GEOCODER_USER_AGENT: str = "SuvBotRoutePlanner/1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("SERVER_PORT", mode="before")
    @classmethod
    def parse_server_port(cls, v: Any) -> int:
        port_env = os.environ.get("PORT")
        if port_env:
            try:
                return int(port_env)
            except ValueError:
                pass
        return int(v) if v else 8000

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Union[str, List[int], int]) -> List[int]:
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return []

    @field_validator("WEBAPP_URL")
    @classmethod
    def clean_webapp_url(cls, v: str) -> str:
        return v.rstrip("/")


settings = Settings()
