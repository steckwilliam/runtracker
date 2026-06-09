from database import get_db_connection, init_db, pace_to_seconds

SAMPLE_RUNS = [
    {
        "date": "2026-06-08",
        "name": "Evening Run",
        "distance_miles": 4.6,
        "pace_per_mile": "9:39",
        "moving_time": "44:40",
        "elevation_gain": 38,
        "run_type": "Easy",
    },
    {
        "date": "2026-06-06",
        "name": "Easy Run",
        "distance_miles": 3.2,
        "pace_per_mile": "9:22",
        "moving_time": "29:58",
        "elevation_gain": 22,
        "run_type": "Easy",
    },
    {
        "date": "2026-06-04",
        "name": "Morning Run",
        "distance_miles": 5.1,
        "pace_per_mile": "9:48",
        "moving_time": "49:58",
        "elevation_gain": 45,
        "run_type": "Easy",
    },
    {
        "date": "2026-06-02",
        "name": "Recovery Run",
        "distance_miles": 2.8,
        "pace_per_mile": "10:05",
        "moving_time": "28:14",
        "elevation_gain": 15,
        "run_type": "Recovery",
    },
    {
        "date": "2026-05-29",
        "name": "Tempo Run",
        "distance_miles": 4.0,
        "pace_per_mile": "8:45",
        "moving_time": "35:00",
        "elevation_gain": 52,
        "run_type": "Tempo",
    },
    {
        "date": "2026-05-25",
        "name": "Long Run",
        "distance_miles": 8.4,
        "pace_per_mile": "9:55",
        "moving_time": "1:23:18",
        "elevation_gain": 210,
        "run_type": "Long",
    },
    {
        "date": "2026-05-20",
        "name": "Park Loop",
        "distance_miles": 3.5,
        "pace_per_mile": "9:30",
        "moving_time": "33:15",
        "elevation_gain": 28,
        "run_type": "Easy",
    },
    {
        "date": "2026-05-15",
        "name": "Hill Repeats",
        "distance_miles": 4.2,
        "pace_per_mile": "9:10",
        "moving_time": "38:42",
        "elevation_gain": 185,
        "run_type": "Tempo",
    },
    {
        "date": "2026-05-08",
        "name": "Easy Run",
        "distance_miles": 3.8,
        "pace_per_mile": "9:45",
        "moving_time": "37:06",
        "elevation_gain": 30,
        "run_type": "Easy",
    },
    {
        "date": "2026-04-28",
        "name": "Long Run",
        "distance_miles": 7.2,
        "pace_per_mile": "10:02",
        "moving_time": "1:12:14",
        "elevation_gain": 165,
        "run_type": "Long",
    },
    {
        "date": "2026-04-18",
        "name": "Morning Run",
        "distance_miles": 4.5,
        "pace_per_mile": "9:28",
        "moving_time": "42:36",
        "elevation_gain": 40,
        "run_type": "Easy",
    },
    {
        "date": "2026-04-10",
        "name": "Recovery Run",
        "distance_miles": 2.5,
        "pace_per_mile": "10:15",
        "moving_time": "25:38",
        "elevation_gain": 12,
        "run_type": "Recovery",
    },
    {
        "date": "2026-03-22",
        "name": "Tempo Run",
        "distance_miles": 5.0,
        "pace_per_mile": "8:52",
        "moving_time": "44:20",
        "elevation_gain": 48,
        "run_type": "Tempo",
    },
    {
        "date": "2026-03-10",
        "name": "Easy Run",
        "distance_miles": 3.6,
        "pace_per_mile": "9:55",
        "moving_time": "35:42",
        "elevation_gain": 25,
        "run_type": "Easy",
    },
]

INSERT_RUN = """
INSERT INTO runs (
    date,
    name,
    distance_miles,
    pace_per_mile,
    pace_seconds,
    moving_time,
    elevation_gain,
    run_type
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


def seed_runs():
    init_db()
    conn = get_db_connection()
    conn.execute("DELETE FROM runs")

    for run in SAMPLE_RUNS:
        conn.execute(
            INSERT_RUN,
            (
                run["date"],
                run["name"],
                run["distance_miles"],
                run["pace_per_mile"],
                pace_to_seconds(run["pace_per_mile"]),
                run["moving_time"],
                run["elevation_gain"],
                run["run_type"],
            ),
        )

    conn.commit()
    conn.close()
    print(f"Seeded {len(SAMPLE_RUNS)} runs into runtracker.db")


if __name__ == "__main__":
    seed_runs()
