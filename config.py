import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
    STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "")
    STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
    STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN", "")
    STRAVA_REDIRECT_URI = os.getenv(
        "STRAVA_REDIRECT_URI", "http://localhost:5000/strava/callback"
    )
    STRAVA_AUTH_URL = os.getenv(
        "STRAVA_AUTH_URL", "https://www.strava.com/oauth/authorize"
    )
    STRAVA_TOKEN_URL = os.getenv(
        "STRAVA_TOKEN_URL", "https://www.strava.com/oauth/token"
    )
    WEATHER_API_BASE_URL = os.getenv(
        "WEATHER_API_BASE_URL", "https://api.open-meteo.com"
    )
    WEATHER_LATITUDE = float(os.getenv("WEATHER_LATITUDE", "29.9511"))
    WEATHER_LONGITUDE = float(os.getenv("WEATHER_LONGITUDE", "-90.0715"))
    WEATHER_TIMEZONE = os.getenv("WEATHER_TIMEZONE", "America/Chicago")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "runtracker.db")

    @classmethod
    def get_database_path(cls) -> Path:
        path = Path(cls.DATABASE_PATH)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @classmethod
    def get_strava_config_status(cls):
        return {
            "STRAVA_CLIENT_ID": "present" if cls.STRAVA_CLIENT_ID else "missing",
            "STRAVA_CLIENT_SECRET": "present" if cls.STRAVA_CLIENT_SECRET else "missing",
            "STRAVA_REDIRECT_URI": "present" if cls.STRAVA_REDIRECT_URI else "missing",
            "STRAVA_REFRESH_TOKEN": "present" if cls.STRAVA_REFRESH_TOKEN else "missing",
        }

    @classmethod
    def get_missing_strava_connect_vars(cls):
        missing = []
        if not cls.STRAVA_CLIENT_ID:
            missing.append("STRAVA_CLIENT_ID")
        if not cls.STRAVA_CLIENT_SECRET:
            missing.append("STRAVA_CLIENT_SECRET")
        if not cls.STRAVA_REDIRECT_URI:
            missing.append("STRAVA_REDIRECT_URI")
        return missing
