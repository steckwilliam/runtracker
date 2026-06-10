from datetime import datetime

import requests

from config import Config
from weather_codes import weather_code_display

HISTORICAL_HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
]


def _historical_api_base():
    return Config.WEATHER_HISTORICAL_API_BASE_URL.rstrip("/")


def fetch_historical_hourly(latitude, longitude, date_str):
    url = f"{_historical_api_base()}/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": ",".join(HISTORICAL_HOURLY_FIELDS),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": Config.WEATHER_TIMEZONE,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("hourly") or {}


def _value_at(data, key, index, default=None):
    values = data.get(key) or []
    if index >= len(values):
        return default
    value = values[index]
    return default if value is None else value


def match_weather_to_run_start(hourly, run_start):
    times = hourly.get("time") or []
    if not times:
        return None

    target = run_start.replace(minute=0, second=0, microsecond=0)
    best_index = None
    best_diff = None

    for index, time_str in enumerate(times):
        hour_start = datetime.fromisoformat(time_str)
        diff = abs((hour_start - target).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_index = index

    if best_index is None:
        return None

    code = int(_value_at(hourly, "weather_code", best_index, 0))
    condition = weather_code_display(code)
    temperature = _value_at(hourly, "temperature_2m", best_index)

    return {
        "temperature_f": round(temperature) if temperature is not None else None,
        "weather_condition": condition["label"],
        "weather_icon": condition["icon"],
        "humidity": _value_at(hourly, "relative_humidity_2m", best_index),
        "wind_speed_mph": _value_at(hourly, "wind_speed_10m", best_index),
        "precipitation": _value_at(hourly, "precipitation", best_index, 0),
        "weather_code": code,
    }


def get_historical_weather_for_run(latitude, longitude, start_datetime_local):
    run_start = datetime.fromisoformat(start_datetime_local)
    date_str = run_start.date().isoformat()
    hourly = fetch_historical_hourly(latitude, longitude, date_str)
    return match_weather_to_run_start(hourly, run_start)
