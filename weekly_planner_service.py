"""Weekly run planner — score forecast days and assign runs with distance and pace."""

import math
from dataclasses import dataclass
from datetime import timedelta

from database import (
    get_best_running_conditions_for_planner,
    get_average_runs_per_week,
    get_default_target_pace_seconds,
    get_typical_runs_per_week,
    get_typical_weekly_mileage,
    seconds_to_pace,
)
from weather_service import (
    WeatherPreferences,
    _format_date,
    _format_rain_probability,
    _format_time,
    _format_wind,
    _hour_in_daylight,
    _hour_in_preferred_time,
    fetch_forecast,
    parse_preferences,
)

WEEKLY_MILEAGE_OPTIONS = (8, 10, 12, 15, 18, 20, 25, 30)
EASY_PACE_OFFSET_SECONDS = 20


def _default_runs_per_week():
    return get_typical_runs_per_week()


@dataclass
class WeeklyPlanPreferences:
    runs_per_week: str = "auto"
    weekly_miles: str = "auto"
    target_pace: str = "auto"
    min_temp: int = 55
    max_temp: int = 85
    preferred_time: str = "anytime"


def parse_weekly_plan_preferences(source):
    runs_per_week = _parse_runs_per_week_value(source.get("runs_per_week"))
    weekly_miles = source.get("weekly_miles", "auto")
    if weekly_miles != "auto":
        try:
            weekly_miles = str(int(float(weekly_miles)))
        except (TypeError, ValueError):
            weekly_miles = "auto"

    target_pace = source.get("target_pace", "auto")
    if target_pace != "auto":
        try:
            target_pace = str(int(float(target_pace)))
        except (TypeError, ValueError):
            target_pace = "auto"

    weather_prefs = parse_preferences(source)
    return WeeklyPlanPreferences(
        runs_per_week=runs_per_week,
        weekly_miles=weekly_miles,
        target_pace=target_pace,
        min_temp=weather_prefs.min_temp,
        max_temp=weather_prefs.max_temp,
        preferred_time=weather_prefs.preferred_time,
    )


def default_weekly_plan_preferences():
    best = get_best_running_conditions_for_planner()
    if best.get("has_data"):
        return WeeklyPlanPreferences(
            runs_per_week="auto",
            weekly_miles="auto",
            target_pace="auto",
            min_temp=best["min_temp"],
            max_temp=best["max_temp"],
            preferred_time=best.get("preferred_time") or best.get("time_of_day_key") or "anytime",
        )
    return WeeklyPlanPreferences()


def get_runs_per_week_choices():
    typical = get_typical_runs_per_week()
    average = get_average_runs_per_week()
    choices = [{"value": "auto", "label": str(typical)}]
    for runs in range(1, 8):
        choices.append({"value": str(runs), "label": str(runs)})
    return choices, typical, average


def get_weekly_mileage_choices():
    typical = get_typical_weekly_mileage()
    choices = [{"value": "auto", "label": f"{typical:.1f} mi"}]
    for miles in WEEKLY_MILEAGE_OPTIONS:
        choices.append({"value": str(miles), "label": f"{miles} mi"})
    return choices, typical


def get_target_pace_choices():
    default_seconds = get_default_target_pace_seconds()
    default_display = seconds_to_pace(default_seconds)
    choices = [
        {
            "value": "auto",
            "label": f"{default_display} /mi",
        }
    ]
    for offset in (-30, -15, 15, 30):
        pace_seconds = max(300, default_seconds + offset)
        choices.append(
            {
                "value": str(pace_seconds),
                "label": f"{seconds_to_pace(pace_seconds)} /mi",
            }
        )
    return choices, default_seconds


def _resolve_target_pace_seconds(prefs):
    if prefs.target_pace == "auto" or not prefs.target_pace:
        return get_default_target_pace_seconds()
    try:
        return int(prefs.target_pace)
    except (TypeError, ValueError):
        return get_default_target_pace_seconds()


def _parse_runs_per_week_value(value):
    if value in (None, "", "auto"):
        return "auto"
    try:
        runs = max(1, min(7, math.ceil(float(value))))
        return str(runs)
    except (TypeError, ValueError):
        return "auto"


def _resolve_runs_per_week(prefs):
    if prefs.runs_per_week == "auto" or not prefs.runs_per_week:
        return _default_runs_per_week()
    try:
        return max(1, min(7, math.ceil(float(prefs.runs_per_week))))
    except (TypeError, ValueError):
        return _default_runs_per_week()


def _resolve_weekly_miles(prefs):
    if prefs.weekly_miles == "auto":
        return round(get_typical_weekly_mileage(), 1)
    return float(prefs.weekly_miles)


def _weather_prefs(prefs):
    return WeatherPreferences(
        min_temp=prefs.min_temp,
        max_temp=prefs.max_temp,
        preferred_time=prefs.preferred_time,
    )


def _score_hour(hour, prefs, daylight):
    temp = hour["temperature_f"]
    if temp is None or not _hour_in_daylight(hour["datetime"], daylight):
        return None

    weather = _weather_prefs(prefs)
    if prefs.min_temp <= temp <= prefs.max_temp:
        temp_score = 100
    else:
        if temp < prefs.min_temp:
            gap = prefs.min_temp - temp
        else:
            gap = temp - prefs.max_temp
        temp_score = max(0, 100 - gap * 6)

    precip = hour.get("precip_probability") or 0
    rain_penalty = min(50, precip * 0.5)

    time_bonus = 15 if _hour_in_preferred_time(hour["datetime"], weather.preferred_time) else 0

    return temp_score - rain_penalty + time_bonus


def _hours_for_day(forecast_hours, day_date):
    return [h for h in forecast_hours if h["datetime"].date() == day_date]


def _best_window_for_hours(hours):
    if not hours:
        return None, None

    hours = sorted(hours, key=lambda h: h["datetime"])
    best_group = None
    best_score = None

    for start_idx in range(len(hours)):
        group = [hours[start_idx]]
        group_score = hours[start_idx].get("_score", 0)
        for end_idx in range(start_idx + 1, len(hours)):
            if hours[end_idx]["datetime"] - hours[end_idx - 1]["datetime"] != timedelta(hours=1):
                break
            group.append(hours[end_idx])
            group_score += hours[end_idx].get("_score", 0)
            if len(group) >= 2:
                avg = group_score / len(group)
                if best_score is None or avg > best_score:
                    best_score = avg
                    best_group = list(group)

        if len(group) == 1:
            avg = group_score
            if best_score is None or avg > best_score:
                best_score = avg
                best_group = list(group)

    if best_group is None:
        best_group = [hours[0]]
        best_score = hours[0].get("_score", 0)

    return best_group, best_score


def _score_days(forecast_hours, daylight, prefs):
    days = sorted({h["datetime"].date() for h in forecast_hours})
    scored = []

    for day in days:
        day_hours = _hours_for_day(forecast_hours, day)
        scored_hours = []
        for hour in day_hours:
            score = _score_hour(hour, prefs, daylight)
            if score is not None:
                enriched = dict(hour)
                enriched["_score"] = score
                scored_hours.append(enriched)

        if not scored_hours:
            continue

        window_hours, day_score = _best_window_for_hours(scored_hours)
        if not window_hours:
            continue

        temps = [h["temperature_f"] for h in window_hours if h["temperature_f"] is not None]
        precip_probs = [h["precip_probability"] for h in window_hours]
        winds = [h["wind_mph"] for h in window_hours]
        representative = window_hours[len(window_hours) // 2]
        start = window_hours[0]["datetime"]
        end = window_hours[-1]["datetime"]
        end_display = end + timedelta(hours=1)

        scored.append(
            {
                "date": day,
                "date_display": _format_date(start),
                "weekday": start.strftime("%A"),
                "sort_key": start,
                "score": day_score,
                "time_window": f"{_format_time(start)} – {_format_time(end_display)}",
                "temp_range": f"{min(temps):.0f}–{max(temps):.0f}°F" if temps else "—",
                "rain_probability": _format_rain_probability(precip_probs),
                "weather_display": (
                    f"{representative['condition_icon']} {representative['condition_label']}"
                ),
                "wind_display": _format_wind(winds),
                "ideal_match": bool(temps)
                and all(prefs.min_temp <= t <= prefs.max_temp for t in temps),
            }
        )

    scored.sort(key=lambda d: d["score"], reverse=True)
    return scored


def _select_run_days(scored_days, runs_per_week):
    if not scored_days:
        return []

    selected = []
    used_dates = set()

    for day in scored_days:
        if len(selected) >= runs_per_week:
            break
        if day["date"] in used_dates:
            continue
        selected.append(day)
        used_dates.add(day["date"])

    if len(selected) < runs_per_week:
        for day in scored_days:
            if len(selected) >= runs_per_week:
                break
            if day["date"] not in used_dates:
                selected.append(day)
                used_dates.add(day["date"])

    selected.sort(key=lambda d: d["sort_key"])
    return selected


def _round_half(value):
    return round(value * 2) / 2


def _assign_distances(selected_days, weekly_miles, runs_per_week):
    if not selected_days:
        return []

    count = len(selected_days)
    if count == 1:
        selected_days[0]["distance_miles"] = round(weekly_miles, 1)
        selected_days[0]["run_type"] = "Run"
        return selected_days

    long_index = max(range(count), key=lambda i: selected_days[i]["score"])
    easy_miles = _round_half(max(1.0, (weekly_miles - 1) / count))
    long_miles = _round_half(easy_miles + 1.0)

    for index, day in enumerate(selected_days):
        if index == long_index:
            day["distance_miles"] = long_miles
            day["run_type"] = "Long run"
        else:
            day["distance_miles"] = easy_miles
            day["run_type"] = "Easy"

    return selected_days


def _assign_paces(selected_days, target_pace_seconds):
    for day in selected_days:
        if day["run_type"] == "Long run":
            pace_seconds = target_pace_seconds + EASY_PACE_OFFSET_SECONDS
        else:
            pace_seconds = target_pace_seconds
        day["pace_display"] = f"{seconds_to_pace(pace_seconds)} /mi"
        day["pace_seconds"] = pace_seconds
    return selected_days


def build_weekly_plan(preferences):
    prefs = preferences
    runs_per_week = _resolve_runs_per_week(prefs)
    weekly_miles = _resolve_weekly_miles(prefs)
    target_pace_seconds = _resolve_target_pace_seconds(prefs)
    forecast_hours, daylight = fetch_forecast()

    scored_days = _score_days(forecast_hours, daylight, prefs)
    selected = _select_run_days(scored_days, runs_per_week)
    selected = _assign_distances(selected, weekly_miles, runs_per_week)
    selected = _assign_paces(selected, target_pace_seconds)

    planned_miles = round(sum(d["distance_miles"] for d in selected), 1)
    ideal_count = sum(1 for d in selected if d.get("ideal_match"))

    return {
        "runs": selected,
        "weekly_miles_target": weekly_miles,
        "planned_miles": planned_miles,
        "runs_per_week": runs_per_week,
        "target_pace_display": f"{seconds_to_pace(target_pace_seconds)} /mi",
        "ideal_weather_count": ideal_count,
        "has_runs": bool(selected),
        "note": _plan_note(selected, prefs, ideal_count),
    }


def _plan_note(selected, prefs, ideal_count):
    if not selected:
        return "No forecast days were available to build a plan."
    if ideal_count == len(selected):
        return "All planned runs fall within your preferred temperature and time settings."
    if ideal_count == 0:
        return (
            "No days matched your ideal conditions exactly — these are the closest available "
            "windows based on temperature, rain, and your preferred time of day."
        )
    return (
        f"{ideal_count} of {len(selected)} runs match your ideal conditions; "
        "the rest use the next-best forecast windows this week."
    )
