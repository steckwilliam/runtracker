"""Shared 90-minute time-of-day buckets for analysis, best conditions, and run planner."""

from datetime import datetime

OTHER_BUCKET_KEY = "other"

# Half-open intervals [start_minutes, end_minutes) from 7:00 AM through 10:00 PM.
TIME_OF_DAY_BUCKETS = (
    {
        "key": "0700_0830",
        "display": "7:00 AM - 8:30 AM",
        "start_minutes": 7 * 60,
        "end_minutes": 8 * 60 + 30,
    },
    {
        "key": "0830_1000",
        "display": "8:30 AM - 10:00 AM",
        "start_minutes": 8 * 60 + 30,
        "end_minutes": 10 * 60,
    },
    {
        "key": "1000_1130",
        "display": "10:00 AM - 11:30 AM",
        "start_minutes": 10 * 60,
        "end_minutes": 11 * 60 + 30,
    },
    {
        "key": "1130_1300",
        "display": "11:30 AM - 1:00 PM",
        "start_minutes": 11 * 60 + 30,
        "end_minutes": 13 * 60,
    },
    {
        "key": "1300_1430",
        "display": "1:00 PM - 2:30 PM",
        "start_minutes": 13 * 60,
        "end_minutes": 14 * 60 + 30,
    },
    {
        "key": "1430_1600",
        "display": "2:30 PM - 4:00 PM",
        "start_minutes": 14 * 60 + 30,
        "end_minutes": 16 * 60,
    },
    {
        "key": "1600_1730",
        "display": "4:00 PM - 5:30 PM",
        "start_minutes": 16 * 60,
        "end_minutes": 17 * 60 + 30,
    },
    {
        "key": "1730_1900",
        "display": "5:30 PM - 7:00 PM",
        "start_minutes": 17 * 60 + 30,
        "end_minutes": 19 * 60,
    },
    {
        "key": "1900_2030",
        "display": "7:00 PM - 8:30 PM",
        "start_minutes": 19 * 60,
        "end_minutes": 20 * 60 + 30,
    },
    {
        "key": "2030_2200",
        "display": "8:30 PM - 10:00 PM",
        "start_minutes": 20 * 60 + 30,
        "end_minutes": 22 * 60,
    },
)

TIME_OF_DAY_METHODOLOGY_LABELS = "90-minute time windows from 7:00 AM to 10:00 PM"

VALID_PREFERRED_TIMES = ("anytime",) + tuple(bucket["key"] for bucket in TIME_OF_DAY_BUCKETS)

# Backward-compatible alias used by database helpers.
TIME_OF_DAY_PERIODS = TIME_OF_DAY_BUCKETS


def get_bucket_by_key(key):
    for bucket in TIME_OF_DAY_BUCKETS:
        if bucket["key"] == key:
            return bucket
    return None


get_period_by_key = get_bucket_by_key


def minutes_to_time_of_day_key(minutes):
    if minutes is None:
        return None
    for bucket in TIME_OF_DAY_BUCKETS:
        if bucket["start_minutes"] <= minutes < bucket["end_minutes"]:
            return bucket["key"]
    return OTHER_BUCKET_KEY


def run_start_minutes(run):
    start_local = run.get("start_datetime_local")
    if start_local:
        try:
            dt = datetime.fromisoformat(start_local)
            return dt.hour * 60 + dt.minute
        except ValueError:
            pass
    hour = run.get("hour_of_day")
    if hour is not None:
        return hour * 60
    return None


def run_to_time_of_day_key(run):
    return minutes_to_time_of_day_key(run_start_minutes(run))


def is_qualifying_time_of_day_key(key):
    return key is not None and key != OTHER_BUCKET_KEY


def run_to_qualifying_time_of_day_key(run):
    key = run_to_time_of_day_key(run)
    if is_qualifying_time_of_day_key(key):
        return key
    return None


def datetime_in_preferred_window(dt, preferred_time):
    if preferred_time == "anytime" or not preferred_time:
        return True
    bucket = get_bucket_by_key(preferred_time)
    if bucket is None:
        return True
    minutes = dt.hour * 60 + dt.minute
    return bucket["start_minutes"] <= minutes < bucket["end_minutes"]
