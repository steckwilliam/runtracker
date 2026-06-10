import calendar
import sqlite3
from datetime import datetime, timedelta

from config import Config

DB_PATH = Config.get_database_path()

DATE_RANGE_KEYS = ("30d", "90d", "365d", "all")
RANGE_LABELS = {
    "30d": "Last 30 days",
    "90d": "Last 90 days",
    "365d": "Last 365 days",
    "all": "All time",
}
# Legacy query param kept for old bookmarks.
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
TIME_OF_DAY_BUCKETS = (
    ("Morning", range(5, 12)),
    ("Afternoon", range(12, 17)),
    ("Evening", range(17, 21)),
    ("Night", list(range(21, 24)) + list(range(0, 5))),
)

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
        run_date = _parse_run_date(run["date"])
        if run_date >= start:
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


def _time_of_day_bucket(hour):
    if hour is None:
        return None
    for label, hours in TIME_OF_DAY_BUCKETS:
        if hour in hours:
            return label
    return None


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


def get_pace_by_weekday_data(runs=None):
    if runs is None:
        runs = get_all_runs()
    paces_by_day = {day: [] for day in WEEKDAY_ORDER}
    for run in runs:
        day = run.get("day_of_week")
        if day in paces_by_day:
            paces_by_day[day].append(pace_to_seconds(run["pace_per_mile"]))
    values = []
    for day in WEEKDAY_ORDER:
        day_paces = paces_by_day[day]
        values.append(round(sum(day_paces) / len(day_paces)) if day_paces else 0)
    return {"labels": WEEKDAY_ORDER, "values": values}


def get_runs_by_time_of_day_data(runs=None):
    if runs is None:
        runs = get_all_runs()
    labels = [label for label, _ in TIME_OF_DAY_BUCKETS]
    counts = {label: 0 for label in labels}
    for run in runs:
        bucket = _time_of_day_bucket(run.get("hour_of_day"))
        if bucket:
            counts[bucket] += 1
    return {"labels": labels, "values": [counts[label] for label in labels]}


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


TEMPERATURE_BUCKETS = (
    ("40–49°F", 40, 49),
    ("50–59°F", 50, 59),
    ("60–69°F", 60, 69),
    ("70–79°F", 70, 79),
    ("80–89°F", 80, 89),
    ("90°F+", 90, 999),
)


def _temperature_bucket_label(temp_f):
    if temp_f is None:
        return None
    temp = round(temp_f)
    for label, low, high in TEMPERATURE_BUCKETS:
        if low <= temp <= high:
            return label
    if temp < 40:
        return "<40°F"
    return "90°F+"


def get_pace_by_temperature_bucket_data(runs=None):
    if runs is None:
        runs = get_all_runs()
    labels = [label for label, _, _ in TEMPERATURE_BUCKETS]
    paces_by_bucket = {label: [] for label in labels}

    for run in runs:
        temp = run.get("temperature_f")
        if temp is None:
            continue
        bucket = _temperature_bucket_label(temp)
        if bucket in paces_by_bucket:
            paces_by_bucket[bucket].append(pace_to_seconds(run["pace_per_mile"]))

    values = []
    active_labels = []
    active_values = []
    active_counts = []

    for label in labels:
        bucket_paces = paces_by_bucket[label]
        count = len(bucket_paces)
        values.append(round(sum(bucket_paces) / count) if count else 0)
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


def get_analysis_chart_data():
    runs = get_all_runs()
    return {
        "runs_by_weekday": get_runs_by_weekday_data(runs),
        "pace_by_weekday": get_pace_by_weekday_data(runs),
        "runs_by_time_of_day": get_runs_by_time_of_day_data(runs),
        "distance_vs_pace": get_distance_vs_pace_data(runs),
        "pace_by_temperature": get_pace_by_temperature_bucket_data(runs),
    }
