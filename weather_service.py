from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

from config import Config
from time_of_day import VALID_PREFERRED_TIMES, datetime_in_preferred_window
from weather_codes import weather_code_display

FORECAST_DAYS = 7


@dataclass
class WeatherPreferences:
    min_temp: int = 55
    max_temp: int = 85
    preferred_time: str = "anytime"


def parse_preferences(source):
    min_temp = _parse_int(source.get("min_temp"), 55)
    max_temp = _parse_int(source.get("max_temp"), 78)
    if min_temp > max_temp:
        min_temp, max_temp = max_temp, min_temp

    preferred_time = source.get("preferred_time", "anytime")
    if preferred_time not in VALID_PREFERRED_TIMES:
        preferred_time = "anytime"

    return WeatherPreferences(
        min_temp=min_temp,
        max_temp=max_temp,
        preferred_time=preferred_time,
    )


def _parse_int(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fetch_forecast():
    base_url = Config.WEATHER_API_BASE_URL.rstrip("/")
    url = f"{base_url}/v1/forecast"
    params = {
        "latitude": Config.WEATHER_LATITUDE,
        "longitude": Config.WEATHER_LONGITUDE,
        "hourly": ",".join(
            [
                "temperature_2m",
                "precipitation_probability",
                "precipitation",
                "weather_code",
                "relative_humidity_2m",
                "wind_speed_10m",
            ]
        ),
        "daily": "sunrise,sunset",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": Config.WEATHER_TIMEZONE,
        "forecast_days": FORECAST_DAYS,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []

    hours = []
    for index, time_str in enumerate(times):
        code = _value_at(hourly, "weather_code", index, 0)
        condition = weather_code_display(int(code) if code is not None else 0)
        hours.append(
            {
                "datetime": datetime.fromisoformat(time_str),
                "temperature_f": _value_at(hourly, "temperature_2m", index),
                "precip_probability": _value_at(hourly, "precipitation_probability", index),
                "precipitation_in": _value_at(hourly, "precipitation", index, 0),
                "weather_code": int(code) if code is not None else 0,
                "humidity": _value_at(hourly, "relative_humidity_2m", index),
                "wind_mph": _value_at(hourly, "wind_speed_10m", index),
                "condition_icon": condition["icon"],
                "condition_label": condition["label"],
            }
        )

    daylight = _parse_daylight_times(payload.get("daily") or {})
    return hours, daylight


def _parse_daylight_times(daily):
    daylight = {}
    dates = daily.get("time") or []
    sunrises = daily.get("sunrise") or []
    sunsets = daily.get("sunset") or []
    for index, date_str in enumerate(dates):
        if index >= len(sunrises) or index >= len(sunsets):
            break
        daylight[date_str] = (
            datetime.fromisoformat(sunrises[index]),
            datetime.fromisoformat(sunsets[index]),
        )
    return daylight


def _daylight_hour_bounds(sunrise, sunset):
    """Return first and last allowed hourly bucket between sunrise and sunset.

    Sunrise is rounded up to the next hour (e.g. 6:42 AM -> 7:00 AM start).
    Sunset is rounded down to the hour, with the window end shown as the next
    hour (e.g. 7:35 PM sunset -> include 7 PM hour, display end as 8:00 PM).
    """
    first_hour = sunrise.replace(minute=0, second=0, microsecond=0)
    if sunrise.minute > 0 or sunrise.second > 0:
        first_hour += timedelta(hours=1)

    last_hour = sunset.replace(minute=0, second=0, microsecond=0)
    return first_hour, last_hour


def _hour_in_daylight(dt, daylight):
    date_key = dt.date().isoformat()
    bounds = daylight.get(date_key)
    if not bounds:
        return True

    sunrise, sunset = bounds
    first_hour, last_hour = _daylight_hour_bounds(sunrise, sunset)
    hour_start = dt.replace(minute=0, second=0, microsecond=0)
    return first_hour <= hour_start <= last_hour


def _value_at(data, key, index, default=None):
    values = data.get(key) or []
    if index >= len(values):
        return default
    value = values[index]
    return default if value is None else value


def _hour_in_preferred_time(dt, preferred_time):
    return datetime_in_preferred_window(dt, preferred_time)


def _format_time(dt):
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.minute:02d} {ampm}"


def _format_date(dt):
    return dt.strftime("%a, %b %d")


def _format_rain_probability(precip_probs):
    values = [p for p in precip_probs if p is not None]
    if not values:
        return "—"
    return f"{max(values):.0f}%"


def _format_wind(winds):
    values = [w for w in winds if w is not None]
    if not values:
        return "—"
    return f"{sum(values) / len(values):.0f} mph"
