import calendar
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from config import Config

DB_PATH = Config.get_database_path()

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


def ensure_runs_schema():
    conn = get_db_connection()
    conn.execute(CREATE_RUNS_TABLE)
    if not _runs_has_strava_activity_id(conn):
        conn.execute("ALTER TABLE runs ADD COLUMN strava_activity_id TEXT")
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


def get_existing_strava_activity_ids():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT strava_activity_id FROM runs WHERE strava_activity_id IS NOT NULL"
    ).fetchall()
    conn.close()
    return {row["strava_activity_id"] for row in rows}


def insert_strava_run(run_data):
    activity_id = run_data["strava_activity_id"]
    if activity_id in get_existing_strava_activity_ids():
        return False

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO runs (
                date, name, distance_miles, pace_per_mile, pace_seconds,
                moving_time, elevation_gain, run_type,
                temperature_f, weather_condition, weather_icon,
                strava_activity_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
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
    return format_date_label(dt)


def _week_start(dt):
    return dt - timedelta(days=dt.weekday())


def _format_weather_display(run):
    parts = []
    if run.get("weather_icon"):
        parts.append(run["weather_icon"])
    if run.get("temperature_f") is not None:
        parts.append(f"{run['temperature_f']}°F")
    if run.get("weather_condition"):
        parts.append(run["weather_condition"])
    return " ".join(parts) if parts else "—"


def _enrich_run_for_display(run):
    return {
        **run,
        "date_display": format_date_short(run["date"]),
        "distance_display": f"{run['distance_miles']:.1f} mi",
        "pace_display": f"{run['pace_per_mile']} /mi",
        "weather_display": _format_weather_display(run),
    }


def get_all_runs():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM runs ORDER BY date DESC").fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def get_recent_runs():
    runs = get_all_runs()
    return [_enrich_run_for_display(run) for run in runs]


def get_dashboard_stats():
    runs = get_all_runs()
    if not runs:
        return {
            "total_miles": "0.0 mi",
            "runs_this_month": 0,
            "average_pace": "0:00 /mi",
            "longest_run": "0.0 mi",
        }

    total_miles = sum(r["distance_miles"] for r in runs)
    now = datetime(2026, 6, 9)
    runs_this_month = sum(
        1
        for r in runs
        if datetime.strptime(r["date"], "%Y-%m-%d").month == now.month
        and datetime.strptime(r["date"], "%Y-%m-%d").year == now.year
    )
    avg_pace_seconds = round(
        sum(pace_to_seconds(r["pace_per_mile"]) for r in runs) / len(runs)
    )
    longest = max(r["distance_miles"] for r in runs)
    return {
        "total_miles": f"{total_miles:.1f} mi",
        "runs_this_month": runs_this_month,
        "average_pace": f"{seconds_to_pace(avg_pace_seconds)} /mi",
        "longest_run": f"{longest:.1f} mi",
    }


def get_weekly_mileage_data():
    runs = get_all_runs()
    week_totals = {}
    for run in runs:
        dt = datetime.strptime(run["date"], "%Y-%m-%d")
        week_key = _week_start(dt)
        week_totals[week_key] = week_totals.get(week_key, 0) + run["distance_miles"]

    sorted_weeks = sorted(week_totals.keys())
    if len(sorted_weeks) > 8:
        sorted_weeks = sorted_weeks[-8:]

    labels = [format_date_label(wk) for wk in sorted_weeks]
    values = [round(week_totals[wk], 1) for wk in sorted_weeks]
    return {"labels": labels, "values": values}


def get_monthly_mileage_data():
    runs = get_all_runs()
    month_totals = {}
    for run in runs:
        dt = datetime.strptime(run["date"], "%Y-%m-%d")
        month_key = dt.replace(day=1)
        month_totals[month_key] = month_totals.get(month_key, 0) + run["distance_miles"]

    sorted_months = sorted(month_totals.keys())
    if len(sorted_months) > 6:
        sorted_months = sorted_months[-6:]

    labels = [format_month_label(m) for m in sorted_months]
    values = [round(month_totals[m], 1) for m in sorted_months]
    return {"labels": labels, "values": values}


def get_pace_trend_data():
    runs = get_all_runs()
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
