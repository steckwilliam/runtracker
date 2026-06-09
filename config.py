import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
    STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "")
    STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
    STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN", "")
    WEATHER_API_BASE_URL = os.getenv(
        "WEATHER_API_BASE_URL", "https://api.open-meteo.com"
    )
    DATABASE_PATH = os.getenv("DATABASE_PATH", "runtracker.db")

    @classmethod
    def get_database_path(cls) -> Path:
        path = Path(cls.DATABASE_PATH)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path
