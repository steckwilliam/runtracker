"""Verify that public_runtracker.db is safe to commit."""

import sqlite3
import sys
from pathlib import Path

from config import BASE_DIR

DEFAULT_DB_PATH = BASE_DIR / "public_runtracker.db"

SUSPICIOUS_TABLE_KEYWORDS = ("token", "oauth", "auth", "credential", "secret")
SUSPICIOUS_COLUMN_KEYWORDS = (
    "token",
    "secret",
    "refresh",
    "access",
    "oauth",
    "auth",
    "credential",
    "latitude",
    "longitude",
)
COORDINATE_COLUMNS = ("start_latitude", "start_longitude")


def _resolve_db_path(path_value=None):
    path = Path(path_value) if path_value else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def _get_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def _get_columns(conn, table_name):
    rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return [row[1] for row in rows]


def _table_name_is_suspicious(table_name):
    lowered = table_name.lower()
    return any(keyword in lowered for keyword in SUSPICIOUS_TABLE_KEYWORDS)


def _column_name_is_suspicious(column_name):
    lowered = column_name.lower()
    return any(keyword in lowered for keyword in SUSPICIOUS_COLUMN_KEYWORDS)


def verify_public_db(db_path=None):
    db_path = _resolve_db_path(db_path)
    issues = []

    print("RunTracker Public Database Verification")
    print("=" * 40)
    print(f"Database: {db_path}")

    if not db_path.exists():
        print("\nERROR: Database file not found.")
        print("\nPUBLIC DB CHECK FAILED")
        return False

    conn = sqlite3.connect(db_path)
    try:
        tables = _get_tables(conn)
        print("\nTables:")
        if tables:
            for table_name in tables:
                print(f"  - {table_name}")
        else:
            print("  (none)")

        suspicious_tables = [name for name in tables if _table_name_is_suspicious(name)]
        print("\nToken/auth table check:")
        if suspicious_tables:
            print("  FAIL: Suspicious tables found:")
            for table_name in suspicious_tables:
                print(f"    - {table_name}")
            issues.append("token/auth tables present")
        else:
            print("  PASS: No token/auth tables found.")

        run_count = 0
        latest_run_date = None
        if "runs" in tables:
            run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            latest_run_date = conn.execute("SELECT MAX(date) FROM runs").fetchone()[0]
        else:
            issues.append("runs table missing")

        print("\nRuns summary:")
        print(f"  Total runs: {run_count}")
        print(f"  Latest run date: {latest_run_date or 'none'}")

        print("\nCoordinate check:")
        if "runs" not in tables:
            print("  SKIP: runs table not found.")
        else:
            run_columns = _get_columns(conn, "runs")
            present_coord_columns = [
                column for column in COORDINATE_COLUMNS if column in run_columns
            ]
            if not present_coord_columns:
                print("  PASS: runs table has no coordinate columns.")
            else:
                print(f"  Coordinate columns present: {', '.join(present_coord_columns)}")
                for column in present_coord_columns:
                    count = conn.execute(
                        f'SELECT COUNT(*) FROM runs WHERE "{column}" IS NOT NULL'
                    ).fetchone()[0]
                    print(f"    - {column}: {count} non-null row(s)")
                total_with_coords = conn.execute(
                    """
                    SELECT COUNT(*) FROM runs
                    WHERE start_latitude IS NOT NULL OR start_longitude IS NOT NULL
                    """
                ).fetchone()[0]
                if total_with_coords == 0:
                    print("  PASS: 0 rows with coordinate values.")
                else:
                    print(f"  FAIL: {total_with_coords} row(s) still have coordinates.")
                    issues.append("coordinates remain in runs")

        print("\nSuspicious column check:")
        suspicious_columns = []
        for table_name in tables:
            for column_name in _get_columns(conn, table_name):
                if _column_name_is_suspicious(column_name):
                    suspicious_columns.append((table_name, column_name))

        if suspicious_columns:
            print("  Columns with sensitive names:")
            for table_name, column_name in suspicious_columns:
                print(f"    - {table_name}.{column_name}")
        else:
            print("  No suspicious column names found.")

        if "runs" in tables:
            run_columns = _get_columns(conn, "runs")
            has_lat_col = "start_latitude" in run_columns
            has_lng_col = "start_longitude" in run_columns
            if has_lat_col or has_lng_col:
                print(
                    "  Note: latitude/longitude columns may exist in schema; "
                    "verify that row values are empty."
                )

    finally:
        conn.close()

    print("\n" + "=" * 40)
    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nPUBLIC DB CHECK FAILED")
        return False

    print("\nPUBLIC DB CHECK PASSED")
    return True


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    passed = verify_public_db(db_path)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
