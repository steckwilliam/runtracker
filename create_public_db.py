"""Build a sanitized SQLite database for the public read-only RunTracker site."""

import argparse
import sqlite3
import sys
from pathlib import Path

from config import BASE_DIR, Config

DEFAULT_SOURCE = BASE_DIR / "runtracker.db"
DEFAULT_OUTPUT = BASE_DIR / "public_runtracker.db"

TOKEN_TABLES = frozenset({"strava_tokens"})
COORD_COLUMNS = frozenset({"start_latitude", "start_longitude"})


def _resolve_path(path_value, default):
    path = Path(path_value) if path_value else default
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def _copy_runs_table(source_conn, dest_conn):
    table_row = source_conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'runs'"
    ).fetchone()
    if not table_row or not table_row[0]:
        raise RuntimeError("Source database does not contain a runs table.")

    dest_conn.execute("DROP TABLE IF EXISTS runs")
    dest_conn.execute(table_row[0])

    columns = [
        row[1] for row in source_conn.execute("PRAGMA table_info(runs)").fetchall()
    ]
    if not columns:
        raise RuntimeError("Source runs table has no columns.")

    select_exprs = [
        "NULL" if column in COORD_COLUMNS else f'"{column}"'
        for column in columns
    ]
    column_list = ", ".join(f'"{column}"' for column in columns)
    select_list = ", ".join(select_exprs)

    source_conn.row_factory = sqlite3.Row
    rows = source_conn.execute(f"SELECT {column_list} FROM runs").fetchall()
    if rows:
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f"INSERT INTO runs ({column_list}) VALUES ({placeholders})"
        dest_conn.executemany(
            insert_sql,
            [
                tuple(
                    None if columns[i] in COORD_COLUMNS else row[i]
                    for i in range(len(columns))
                )
                for row in rows
            ],
        )

    for index_row in source_conn.execute(
        """
        SELECT sql FROM sqlite_master
        WHERE type = 'index' AND tbl_name = 'runs' AND sql IS NOT NULL
        """
    ).fetchall():
        dest_conn.execute(index_row[0])

    return len(rows)


def _latest_run_date(conn):
    row = conn.execute("SELECT MAX(date) AS latest_date FROM runs").fetchone()
    if not row or not row[0]:
        return None
    return row[0]


def create_public_db(source_path, output_path):
    source_path = _resolve_path(source_path, DEFAULT_SOURCE)
    output_path = _resolve_path(output_path, DEFAULT_OUTPUT)

    if not source_path.exists():
        raise FileNotFoundError(f"Source database not found: {source_path}")

    if source_path.resolve() == output_path.resolve():
        raise ValueError("Source and output database paths must be different.")

    source_tables = {
        row[0]
        for row in sqlite3.connect(source_path).execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    excluded_token_tables = sorted(source_tables & TOKEN_TABLES)

    if output_path.exists():
        output_path.unlink()

    source_conn = sqlite3.connect(source_path)
    dest_conn = sqlite3.connect(output_path)

    try:
        runs_copied = _copy_runs_table(source_conn, dest_conn)
        dest_conn.commit()
        latest_date = _latest_run_date(dest_conn)
    finally:
        source_conn.close()
        dest_conn.close()

    return {
        "source": source_path,
        "output": output_path,
        "runs_copied": runs_copied,
        "excluded_token_tables": excluded_token_tables,
        "coordinates_cleared": sorted(COORD_COLUMNS),
        "latest_run_date": latest_date,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Create a sanitized public_runtracker.db from the local development database."
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Source SQLite database (default: runtracker.db)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output SQLite database (default: public_runtracker.db)",
    )
    args = parser.parse_args()

    try:
        summary = create_public_db(args.source, args.output)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Public database created successfully.")
    print(f"Source database: {summary['source']}")
    print(f"Output database: {summary['output']}")
    print(f"Runs copied: {summary['runs_copied']}")
    print(
        "Token tables excluded: "
        + (
            ", ".join(summary["excluded_token_tables"])
            if summary["excluded_token_tables"]
            else "none found in source"
        )
    )
    print(
        "Coordinates cleared: "
        + ", ".join(summary["coordinates_cleared"])
    )
    if summary["latest_run_date"]:
        print(f"Latest run date copied: {summary['latest_run_date']}")
        print(
            "Update README dataset cutoff with this date under Current Version Notes."
        )
    else:
        print("Latest run date copied: none")


if __name__ == "__main__":
    main()
