import calendar
import sqlite3
from datetime import datetime, timedelta

from config import Config
from time_of_day import (
    OTHER_BUCKET_KEY,
    TIME_OF_DAY_BUCKETS,
    get_bucket_by_key,
    run_to_qualifying_time_of_day_key,
    run_to_time_of_day_key,
)

DB_PATH = Config.get_database_path()

DATE_RANGE_KEYS = ("30d", "90d", "365d", "all")
RANGE_LABELS = {
    "30d": "Last 30 days",
    "90d": "Last 90 days",
    "365d": "Last 365 days",
    "all": "All time",
}
# Legacy bookmark support for old range query params.
_LEGACY_RANGE_ALIASES = {"ytd": "365d", "this_year": "365d"}
DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
WEEKDAY_ORDER = list(DAY_NAMES)

WEATHER_TEMPERATURE_BUCKETS = (
    ("Below 50°F", -999, 49),
    ("50–59°F", 50, 59),
    ("60–69°F", 60, 69),
    ("70–79°F", 70, 79),
    ("80–89°F", 80, 89),
    ("90°F+", 90, 999),
)

BEST_CONDITIONS_MIN_RUNS = 5
BEST_CONDITIONS_MIN_DISTANCE_MILES = 2.0

CREATE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    distance_miles REAL NOT NULL,
    pace_per_mile TEXT NOT NULL,
    pace_seconds INTEGER NOT NULL,
    moving_time TEXT NOT NULL,
    elevation_gain INTEGER,
    run_type TEXT,
    temperature_f INTEGER,
    weather_condition TEXT,
    weather_icon TEXT,
    strava_activity_id TEXT UNIQUE
);
"""

CREATE_STRAVA_TOKENS_TABLE = """
CREATE TABLE IF NOT EXISTS strava_tokens (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    athlete_id TEXT,
    athlete_name TEXT,
    scope TEXT,
    access_token TEXT,
    refresh_token TEXT,
    expires_at INTEGER,
    updated_at TEXT
);
"""


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _runs_has_strava_activity_id(conn):
    columns = conn.execute("PRAGMA table_info(runs)").fetchall()
    return any(col[1] == "strava_activity_id" for col in columns)


def _runs_has_column(conn, column_name):
    columns = conn.execute("PRAGMA table_info(runs)").fetchall()
    return any(col[1] == column_name for col in columns)


def ensure_runs_schema():
    conn = get_db_connection()
    conn.execute(CREATE_RUNS_TABLE)
    if not _runs_has_strava_activity_id(conn):
        conn.execute("ALTER TABLE runs ADD COLUMN strava_activity_id TEXT")
    for column, col_type in (
        ("start_datetime_local", "TEXT"),
        ("start_time_display", "TEXT"),
        ("hour_of_day", "INTEGER"),
        ("day_of_week", "TEXT"),
        ("start_latitude", "REAL"),
        ("start_longitude", "REAL"),
        ("humidity", "INTEGER"),
        ("wind_speed_mph", "REAL"),
        ("precipitation", "REAL"),
        ("weather_code", "INTEGER"),
        ("weather_synced_at", "TEXT"),
    ):
        if not _runs_has_column(conn, column):
            conn.execute(f"ALTER TABLE runs ADD COLUMN {column} {col_type}")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_strava_activity_id
        ON runs(strava_activity_id)
        WHERE strava_activity_id IS NOT NULL
        """
    )
    conn.commit()
    conn.close()


def init_db():
    conn = get_db_connection()
    conn.execute(CREATE_RUNS_TABLE)
    if Config.ENABLE_STRAVA_ROUTES:
        conn.execute(CREATE_STRAVA_TOKENS_TABLE)
    conn.commit()
    conn.close()
    ensure_runs_schema()


def save_strava_tokens(token_data, scope):
    athlete = token_data.get("athlete") or {}
    athlete_id = athlete.get("id")
    athlete_id = str(athlete_id) if athlete_id is not None else ""
    athlete_name = (
        athlete.get("firstname")
        or athlete.get("username")
        or athlete_id
        or ""
    )
    access_token = token_data.get("access_token") or ""
    refresh_token = token_data.get("refresh_token") or ""
    expires_at = token_data.get("expires_at")
    if expires_at is not None:
        expires_at = int(expires_at)
    updated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO strava_tokens (
            id, athlete_id, athlete_name, scope, access_token, refresh_token,
            expires_at, updated_at
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            athlete_id = excluded.athlete_id,
            athlete_name = excluded.athlete_name,
            scope = excluded.scope,
            access_token = excluded.access_token,
            refresh_token = excluded.refresh_token,
            expires_at = excluded.expires_at,
            updated_at = excluded.updated_at
        """,
        (
            athlete_id,
            athlete_name,
            scope,
            access_token,
            refresh_token,
            expires_at,
            updated_at,
        ),
    )
    conn.commit()
    conn.close()
    return bool(access_token or refresh_token)


def get_strava_tokens():
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM strava_tokens WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else None


def has_strava_refresh_token():
    tokens = get_strava_tokens()
    return bool(tokens and tokens.get("refresh_token"))


def update_strava_tokens_from_refresh(token_data):
    existing = get_strava_tokens() or {}
    scope = existing.get("scope", "")
    athlete = token_data.get("athlete")
    if not athlete:
        athlete = {
            "id": existing.get("athlete_id"),
            "firstname": existing.get("athlete_name"),
        }
    merged = {**token_data, "athlete": athlete}
    return save_strava_tokens(merged, scope)


def parse_strava_start_local(start_str):
    if not start_str:
        return None
    cleaned = start_str.replace("Z", "").split("+")[0].split(".")[0]
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def format_start_time_display(dt):
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.minute:02d} {ampm}"


def extract_run_time_fields(start_str):
    dt = parse_strava_start_local(start_str)
    if not dt:
        return {
            "start_datetime_local": None,
            "start_time_display": None,
            "hour_of_day": None,
            "day_of_week": None,
        }
    return {
        "start_datetime_local": dt.isoformat(timespec="seconds"),
        "start_time_display": format_start_time_display(dt),
        "hour_of_day": dt.hour,
        "day_of_week": DAY_NAMES[dt.weekday()],
    }


def extract_strava_coordinates(activity):
    latlng = activity.get("start_latlng")
    if latlng and len(latlng) >= 2:
        return float(latlng[0]), float(latlng[1])
    return None, None


def _run_needs_time_backfill(run):
    return not run.get("start_datetime_local") or run.get("hour_of_day") is None


def _run_needs_coordinate_backfill(run):
    return run.get("start_latitude") is None or run.get("start_longitude") is None


def _run_needs_strava_backfill(run):
    return _run_needs_time_backfill(run) or _run_needs_coordinate_backfill(run)


def get_run_by_strava_activity_id(activity_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM runs WHERE strava_activity_id = ?",
        (activity_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _time_field_values(run_data):
    return (
        run_data.get("start_datetime_local"),
        run_data.get("start_time_display"),
        run_data.get("hour_of_day"),
        run_data.get("day_of_week"),
    )


def _coordinate_field_values(run_data):
    return (
        run_data.get("start_latitude"),
        run_data.get("start_longitude"),
    )


def insert_strava_run(run_data):
    """Insert a new run or backfill missing Strava fields on an existing one.

    Returns: "inserted", "backfilled", or "skipped".
    """
    activity_id = run_data["strava_activity_id"]
    existing = get_run_by_strava_activity_id(activity_id)

    if existing:
        if not _run_needs_strava_backfill(existing):
            return "skipped"
        conn = get_db_connection()
        conn.execute(
            """
            UPDATE runs SET
                start_datetime_local = COALESCE(start_datetime_local, ?),
                start_time_display = COALESCE(start_time_display, ?),
                hour_of_day = COALESCE(hour_of_day, ?),
                day_of_week = COALESCE(day_of_week, ?),
                start_latitude = COALESCE(start_latitude, ?),
                start_longitude = COALESCE(start_longitude, ?)
            WHERE strava_activity_id = ?
            """,
            (
                *(_time_field_values(run_data)),
                *(_coordinate_field_values(run_data)),
                activity_id,
            ),
        )
        conn.commit()
        conn.close()
        return "backfilled"

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO runs (
                date, name, distance_miles, pace_per_mile, pace_seconds,
                moving_time, elevation_gain, run_type,
                temperature_f, weather_condition, weather_icon,
                strava_activity_id,
                start_datetime_local, start_time_display, hour_of_day, day_of_week,
                start_latitude, start_longitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_data["date"],
                run_data["name"],
                run_data["distance_miles"],
                run_data["pace_per_mile"],
                run_data["pace_seconds"],
                run_data["moving_time"],
                run_data["elevation_gain"],
                run_data["run_type"],
                None,
                None,
                None,
                activity_id,
                run_data.get("start_datetime_local"),
                run_data.get("start_time_display"),
                run_data.get("hour_of_day"),
                run_data.get("day_of_week"),
                run_data.get("start_latitude"),
                run_data.get("start_longitude"),
            ),
        )
        conn.commit()
        return "inserted"
    except sqlite3.IntegrityError:
        return "skipped"
    finally:
        conn.close()


def get_runs_needing_weather_sync():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT * FROM runs
        WHERE start_datetime_local IS NOT NULL
          AND start_latitude IS NOT NULL
          AND start_longitude IS NOT NULL
          AND weather_synced_at IS NULL
        ORDER BY date ASC
        """
    ).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def get_runs_missing_coordinates():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT * FROM runs
        WHERE strava_activity_id IS NOT NULL
          AND (start_latitude IS NULL OR start_longitude IS NULL)
        """
    ).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def update_run_weather(run_id, weather_data):
    synced_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE runs SET
            temperature_f = ?,
            weather_condition = ?,
            weather_icon = ?,
            humidity = ?,
            wind_speed_mph = ?,
            precipitation = ?,
            weather_code = ?,
            weather_synced_at = ?
        WHERE id = ?
        """,
        (
            weather_data.get("temperature_f"),
            weather_data.get("weather_condition"),
            weather_data.get("weather_icon"),
            weather_data.get("humidity"),
            weather_data.get("wind_speed_mph"),
            weather_data.get("precipitation"),
            weather_data.get("weather_code"),
            synced_at,
            run_id,
        ),
    )
    conn.commit()
    conn.close()


def _rows_to_dicts(rows):
    return [dict(row) for row in rows]


def pace_to_seconds(pace_str):
    minutes, seconds = pace_str.split(":")
    return int(minutes) * 60 + int(seconds)


def seconds_to_pace(total_seconds):
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def format_date_label(dt):
    return f"{calendar.month_abbr[dt.month]} {dt.day}"


def format_month_label(dt):
    return calendar.month_abbr[dt.month]


def format_date_short(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{calendar.month_abbr[dt.month]} {dt.day}, {dt.year}"


def _week_start(dt):
    return dt - timedelta(days=dt.weekday())


def moving_time_to_seconds(time_str):
    parts = time_str.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = (int(p) for p in parts)
        return hours * 3600 + minutes * 60 + seconds
    if len(parts) == 2:
        minutes, seconds = (int(p) for p in parts)
        return minutes * 60 + seconds
    return 0


def _format_weather_display(run):
    if run.get("temperature_f") is None and not run.get("weather_condition"):
        return "—"
    parts = []
    if run.get("weather_icon"):
        parts.append(run["weather_icon"])
    if run.get("temperature_f") is not None:
        parts.append(f"{round(run['temperature_f'])}°F")
    if run.get("weather_condition"):
        parts.append(run["weather_condition"])
    return " ".join(parts) if parts else "—"


def _enrich_run_for_display(run):
    weather_display = _format_weather_display(run)
    temperature_f = run.get("temperature_f")
    hour_of_day = run.get("hour_of_day")
    start_time_display = run.get("start_time_display") or "—"
    return {
        **run,
        "date_display": format_date_short(run["date"]),
        "distance_display": f"{run['distance_miles']:.1f} mi",
        "pace_display": f"{run['pace_per_mile']} /mi",
        "weather_display": weather_display,
        "start_time_display": start_time_display,
        "time_seconds": moving_time_to_seconds(run["moving_time"]),
        "temperature_sort": temperature_f if temperature_f is not None else -1,
        "start_time_sort": hour_of_day if hour_of_day is not None else -1,
    }


def get_all_runs():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM runs ORDER BY date DESC").fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def _parse_run_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _reference_now():
    return datetime.now()


def normalize_date_range(range_key):
    if range_key in _LEGACY_RANGE_ALIASES:
        return _LEGACY_RANGE_ALIASES[range_key]
    if range_key in DATE_RANGE_KEYS:
        return range_key
    return None


def get_default_date_range(runs=None, reference=None):
    # Rolling 365-day window is the default dashboard view.
    return "365d"


def resolve_date_range(range_key=None, runs=None, reference=None):
    reference = reference or _reference_now()
    if runs is None:
        runs = get_all_runs()
    normalized = normalize_date_range(range_key)
    if normalized is None:
        normalized = get_default_date_range(runs, reference)
    return normalized


def get_range_start_date(range_key, reference=None):
    reference = reference or _reference_now()
    today = reference.date()
    if range_key == "30d":
        return today - timedelta(days=30)
    if range_key == "90d":
        return today - timedelta(days=90)
    if range_key == "365d":
        return today - timedelta(days=365)
    return None


def filter_runs_by_range(runs, range_key, reference=None):
    start = get_range_start_date(range_key, reference)
    if start is None:
        return list(runs)
    filtered = []
    for run in runs:
        run_date = _run_date_for_filter(run)
        if run_date is not None and run_date >= start:
            filtered.append(run)
    return filtered


def get_dashboard_runs(range_key=None, reference=None):
    """Resolve the selected range once and return filtered runs for the dashboard."""
    reference = reference or _reference_now()
    all_runs = get_all_runs()
    resolved = resolve_date_range(range_key, all_runs, reference)
    filtered = filter_runs_by_range(all_runs, resolved, reference)
    return filtered, resolved


def get_runs_for_range(range_key, reference=None):
    runs, resolved = get_dashboard_runs(range_key, reference)
    return runs, resolved


def get_recent_runs(range_key=None, reference=None, runs=None):
    if runs is None:
        runs, _ = get_dashboard_runs(range_key, reference)
    return [_enrich_run_for_display(run) for run in runs]


def _empty_dashboard_stats():
    return {
        "total_miles": "0.0 mi",
        "total_runs": 0,
        "average_pace": "0:00 /mi",
        "longest_run": "0.0 mi",
    }


def get_dashboard_stats(range_key=None, reference=None, runs=None):
    if runs is None:
        runs, _ = get_dashboard_runs(range_key, reference)
    if not runs:
        return _empty_dashboard_stats()

    total_miles = sum(r["distance_miles"] for r in runs)
    avg_pace_seconds = round(
        sum(pace_to_seconds(r["pace_per_mile"]) for r in runs) / len(runs)
    )
    longest = max(r["distance_miles"] for r in runs)

    return {
        "total_miles": f"{total_miles:.1f} mi",
        "total_runs": len(runs),
        "average_pace": f"{seconds_to_pace(avg_pace_seconds)} /mi",
        "longest_run": f"{longest:.1f} mi",
    }


def get_weekly_mileage_data(range_key=None, reference=None, runs=None):
    if runs is None:
        runs, _ = get_dashboard_runs(range_key, reference)
    week_totals = {}
    for run in runs:
        dt = datetime.strptime(run["date"], "%Y-%m-%d")
        week_key = _week_start(dt)
        week_totals[week_key] = week_totals.get(week_key, 0) + run["distance_miles"]

    sorted_weeks = sorted(week_totals.keys())
    labels = [format_date_label(wk) for wk in sorted_weeks]
    values = [round(week_totals[wk], 1) for wk in sorted_weeks]
    return {"labels": labels, "values": values}


def get_monthly_mileage_data(range_key=None, reference=None, runs=None):
    if runs is None:
        runs, _ = get_dashboard_runs(range_key, reference)
    month_totals = {}
    for run in runs:
        dt = datetime.strptime(run["date"], "%Y-%m-%d")
        month_key = dt.replace(day=1)
        month_totals[month_key] = month_totals.get(month_key, 0) + run["distance_miles"]

    sorted_months = sorted(month_totals.keys())
    labels = [format_month_label(m) for m in sorted_months]
    values = [round(month_totals[m], 1) for m in sorted_months]
    return {"labels": labels, "values": values}


def get_pace_trend_data(range_key=None, reference=None, runs=None):
    if runs is None:
        runs, _ = get_dashboard_runs(range_key, reference)
    week_paces = {}
    for run in runs:
        dt = datetime.strptime(run["date"], "%Y-%m-%d")
        week_key = _week_start(dt)
        week_paces.setdefault(week_key, []).append(pace_to_seconds(run["pace_per_mile"]))

    sorted_weeks = sorted(week_paces.keys())
    labels = [format_date_label(wk) for wk in sorted_weeks]
    values = [
        round(sum(paces) / len(paces))
        for paces in [week_paces[wk] for wk in sorted_weeks]
    ]
    return {"labels": labels, "values": values}


def get_longest_run_by_month_data(range_key=None, reference=None, runs=None):
    if runs is None:
        runs, _ = get_dashboard_runs(range_key, reference)
    month_best = {}
    for run in runs:
        dt = datetime.strptime(run["date"], "%Y-%m-%d")
        month_key = dt.replace(day=1)
        distance = run["distance_miles"]
        if month_key not in month_best or distance > month_best[month_key]:
            month_best[month_key] = distance

    sorted_months = sorted(month_best.keys())
    labels = [format_month_label(m) for m in sorted_months]
    values = [round(month_best[m], 1) for m in sorted_months]
    return {"labels": labels, "values": values}


def get_dashboard_data(range_key=None, reference=None):
    """Build all dashboard payloads from one resolved range and one filtered run list."""
    runs, resolved = get_dashboard_runs(range_key, reference)
    return {
        "range_key": resolved,
        "range_label": RANGE_LABELS.get(resolved, resolved),
        "stats": get_dashboard_stats(runs=runs),
        "recent_runs": get_recent_runs(runs=runs),
        "weekly_chart": get_weekly_mileage_data(runs=runs),
        "monthly_chart": get_monthly_mileage_data(runs=runs),
        "pace_chart": get_pace_trend_data(runs=runs),
        "longest_month_chart": get_longest_run_by_month_data(runs=runs),
    }


def _run_hour(run):
    hour = run.get("hour_of_day")
    if hour is not None:
        return hour
    start_local = run.get("start_datetime_local")
    if start_local:
        try:
            return datetime.fromisoformat(start_local).hour
        except ValueError:
            pass
    return None


def _filter_weather_pace_runs(runs):
    return [
        r
        for r in runs
        if r.get("temperature_f") is not None and r.get("pace_seconds") is not None
    ]


def _run_date_for_filter(run):
    start_local = run.get("start_datetime_local")
    if start_local:
        try:
            return datetime.fromisoformat(start_local).date()
        except ValueError:
            pass
    date_str = run.get("date")
    if date_str:
        return _parse_run_date(date_str)
    return None


def _temperature_bucket_to_range(label):
    for bucket_label, low, high in WEATHER_TEMPERATURE_BUCKETS:
        if bucket_label == label:
            min_temp = 32 if low < 0 else low
            max_temp = min(high, 120)
            return min_temp, max_temp
    return None, None


def _filter_performance_analysis_runs(runs):
    return [
        r
        for r in runs
        if r.get("distance_miles", 0) >= BEST_CONDITIONS_MIN_DISTANCE_MILES
        and r.get("pace_seconds") is not None
        and r.get("temperature_f") is not None
        and run_to_qualifying_time_of_day_key(r) is not None
        and _run_date_for_filter(r) is not None
    ]


def _best_conditions_summary_prefix(range_key):
    if range_key == "30d":
        return "Based on your last 30 days, "
    if range_key == "90d":
        return "Based on your last 90 days, "
    if range_key == "365d":
        return "Based on your last 365 days, "
    return ""


def _best_conditions_empty_message(range_key):
    if range_key == "all":
        return (
            "Not enough weather-backed runs yet. RunTracker needs at least 5 qualifying "
            "runs (at least 2 miles, start time between 7:00 AM and 10:00 PM, synced "
            "weather) in the same 90-minute time window and temperature range group."
        )
    days = {"30d": 30, "90d": 90, "365d": 365}.get(range_key, 365)
    return (
        f"Not enough recent weather-backed runs yet. RunTracker needs at least 5 "
        f"qualifying runs in the same 90-minute time window and temperature range "
        f"from the last {days} days."
    )


def get_best_conditions_methodology(range_key):
    if range_key == "all":
        period = "RunTracker analyzed your runs"
    else:
        days = {"30d": 30, "90d": 90, "365d": 365}.get(range_key, 365)
        period = f"RunTracker analyzed your runs from the last {days} days"
    return (
        f"{period} that were at least 2 miles long and had historical weather data. "
        "Runs were grouped by 90-minute time windows from 7:00 AM to 10:00 PM and by "
        "10-degree temperature ranges. Only groups with at least 5 runs were "
        "considered, which helps avoid drawing conclusions from one or two unusually "
        "fast runs."
    )


def _temperature_bucket_label(temp_f):
    if temp_f is None:
        return None
    temp = round(temp_f)
    for label, low, high in WEATHER_TEMPERATURE_BUCKETS:
        if low <= temp <= high:
            return label
    return None


def get_average_pace_by_temperature_bucket(runs=None):
    if runs is None:
        runs = get_all_runs()
    labels = [label for label, _, _ in WEATHER_TEMPERATURE_BUCKETS]
    paces_by_bucket = {label: [] for label in labels}

    for run in _filter_weather_pace_runs(runs):
        bucket = _temperature_bucket_label(run["temperature_f"])
        if bucket in paces_by_bucket:
            paces_by_bucket[bucket].append(run["pace_seconds"])

    active_labels = []
    active_values = []
    active_counts = []

    for label in labels:
        bucket_paces = paces_by_bucket[label]
        count = len(bucket_paces)
        if count > 0:
            active_labels.append(label)
            active_values.append(round(sum(bucket_paces) / count))
            active_counts.append(count)

    return {
        "labels": active_labels,
        "values": active_values,
        "has_data": bool(active_labels),
        "run_counts": active_counts,
    }


def get_average_pace_by_time_of_day(runs=None):
    if runs is None:
        runs = get_all_runs()
    paces_by_key = {bucket["key"]: [] for bucket in TIME_OF_DAY_BUCKETS}

    for run in runs:
        if run.get("pace_seconds") is None:
            continue
        bucket_key = run_to_qualifying_time_of_day_key(run)
        if bucket_key in paces_by_key:
            paces_by_key[bucket_key].append(run["pace_seconds"])

    active_labels = []
    active_values = []
    active_counts = []

    for bucket in TIME_OF_DAY_BUCKETS:
        bucket_paces = paces_by_key[bucket["key"]]
        count = len(bucket_paces)
        if count > 0:
            active_labels.append(bucket["display"])
            active_values.append(round(sum(bucket_paces) / count))
            active_counts.append(count)

    return {
        "labels": active_labels,
        "values": active_values,
        "has_data": bool(active_labels),
        "run_counts": active_counts,
    }


def get_runs_by_weather_condition(runs=None):
    if runs is None:
        runs = get_all_runs()
    counts = {}
    for run in runs:
        condition = run.get("weather_condition")
        if not condition:
            continue
        counts[condition] = counts.get(condition, 0) + 1

    sorted_conditions = sorted(counts.keys(), key=lambda c: (-counts[c], c))
    return {
        "labels": sorted_conditions,
        "values": [counts[label] for label in sorted_conditions],
        "has_data": bool(sorted_conditions),
    }


def get_best_running_conditions(runs=None, range_key="365d"):
    if runs is None:
        runs = get_all_runs()

    groups = {}
    for run in _filter_performance_analysis_runs(runs):
        time_key = run_to_qualifying_time_of_day_key(run)
        temp_bucket = _temperature_bucket_label(run["temperature_f"])
        if not time_key or not temp_bucket:
            continue
        key = (time_key, temp_bucket)
        groups.setdefault(key, []).append(run)

    best_group = None
    best_key = None

    for key, group_runs in groups.items():
        if len(group_runs) < BEST_CONDITIONS_MIN_RUNS:
            continue
        avg_pace = sum(r["pace_seconds"] for r in group_runs) / len(group_runs)
        if best_group is None or avg_pace < best_group["avg_pace_seconds"]:
            best_key = key
            best_group = {
                "avg_pace_seconds": avg_pace,
                "run_count": len(group_runs),
                "avg_distance": sum(r["distance_miles"] for r in group_runs)
                / len(group_runs),
                "avg_temperature": sum(r["temperature_f"] for r in group_runs)
                / len(group_runs),
            }

    if not best_group:
        return {
            "has_data": False,
            "empty_message": _best_conditions_empty_message(range_key),
        }

    time_key, temperature_bucket = best_key
    bucket = get_bucket_by_key(time_key)
    time_display = bucket["display"] if bucket else time_key
    min_temp, max_temp = _temperature_bucket_to_range(temperature_bucket)
    prefix = _best_conditions_summary_prefix(range_key)
    return {
        "has_data": True,
        "time_of_day": time_display,
        "time_of_day_key": time_key,
        "preferred_time": time_key,
        "temperature_bucket": temperature_bucket,
        "min_temp": min_temp,
        "max_temp": max_temp,
        "average_pace": f"{seconds_to_pace(round(best_group['avg_pace_seconds']))} /mi",
        "average_pace_seconds": round(best_group["avg_pace_seconds"]),
        "run_count": best_group["run_count"],
        "average_distance": f"{best_group['avg_distance']:.1f} mi",
        "average_temperature": f"{round(best_group['avg_temperature'])}°F",
        "summary_text": (
            f"{prefix}{'Your' if not prefix else 'your'} best aggregate pace was during "
            f"{time_display} runs in the {temperature_bucket} range."
        ),
    }


def get_best_running_conditions_for_planner(reference=None):
    """Best conditions for Weather Planner — always uses the last 90 days."""
    runs, _ = get_dashboard_runs("90d", reference)
    return get_best_running_conditions(runs, range_key="90d")


def get_weather_analysis_data(runs=None, range_key="365d"):
    if runs is None:
        runs = get_all_runs()
    weather_runs = _filter_weather_pace_runs(runs)
    best_conditions = get_best_running_conditions(runs, range_key=range_key)
    return {
        "has_data": bool(weather_runs),
        "weather_run_count": len(weather_runs),
        "best_conditions": best_conditions,
        "pace_by_temperature": get_average_pace_by_temperature_bucket(runs),
        "runs_by_weather_condition": get_runs_by_weather_condition(runs),
    }


def get_runs_by_weekday_data(runs=None):
    if runs is None:
        runs = get_all_runs()
    counts = {day: 0 for day in WEEKDAY_ORDER}
    for run in runs:
        day = run.get("day_of_week")
        if day in counts:
            counts[day] += 1
    return {
        "labels": WEEKDAY_ORDER,
        "values": [counts[day] for day in WEEKDAY_ORDER],
    }


def get_runs_by_time_of_day_data(runs=None):
    if runs is None:
        runs = get_all_runs()
    counts = {bucket["key"]: 0 for bucket in TIME_OF_DAY_BUCKETS}
    other_count = 0
    for run in runs:
        bucket_key = run_to_time_of_day_key(run)
        if bucket_key == OTHER_BUCKET_KEY:
            other_count += 1
        elif bucket_key in counts:
            counts[bucket_key] += 1
    labels = [bucket["display"] for bucket in TIME_OF_DAY_BUCKETS]
    values = [counts[bucket["key"]] for bucket in TIME_OF_DAY_BUCKETS]
    if other_count > 0:
        labels.append("Other")
        values.append(other_count)
    return {
        "labels": labels,
        "values": values,
        "has_data": any(values),
    }


def get_distance_vs_pace_data(runs=None):
    if runs is None:
        runs = get_all_runs()
    points = []
    for run in runs:
        points.append(
            {
                "x": round(run["distance_miles"], 2),
                "y": pace_to_seconds(run["pace_per_mile"]),
                "label": run.get("name") or "Run",
            }
        )
    return {"points": points}


def get_analysis_data(range_key=None, reference=None):
    """Build all analysis payloads from one resolved range and one filtered run list."""
    runs, resolved = get_dashboard_runs(range_key, reference)
    weather = get_weather_analysis_data(runs, range_key=resolved)
    return {
        "range_key": resolved,
        "range_label": RANGE_LABELS.get(resolved, resolved),
        "methodology_text": get_best_conditions_methodology(resolved),
        "runs_by_weekday": get_runs_by_weekday_data(runs),
        "pace_by_time_of_day": get_average_pace_by_time_of_day(runs),
        "runs_by_time_of_day": get_runs_by_time_of_day_data(runs),
        "distance_vs_pace": get_distance_vs_pace_data(runs),
        "weather": weather,
        "pace_by_temperature": weather["pace_by_temperature"],
    }
