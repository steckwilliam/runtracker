# RunTracker

**Live site:** [https://runtracker-lirm.onrender.com/](https://runtracker-lirm.onrender.com/)

Note: The live site is hosted on a free service. If it has been inactive, the first load may take up to a minute while the server wakes up.

RunTracker is a personal running analytics app I built to better understand my own training data. I started running in August 2025 and have been recording my runs with an Apple Watch, with Strava storing detailed activity metrics like distance, pace, time, elevation, and run history. This app pulls that running data together with historical weather data for each run, then uses dashboards, charts, and analysis tools to help identify patterns in my performance and make better decisions about future runs.

The current version includes a filterable running dashboard, a full run history table, weather-based performance analysis, and a Run Planner that uses recent running history and forecast data to recommend a weekly run plan.

## Features

- **Dashboard** — stat cards, charts, date-range filters (Last 30 days, Last 90 days, Last 365 days, All time), and **Shoe Mileage** tracker
- **Run Log** — sortable, paginated runs table with weather display
- **Analysis** — performance charts by distance, timing, and temperature, plus **Best Running Conditions** insights
- **Run Planner** — recommends a weekly run plan using forecast data and recent running history, including suggested days, time windows, distances, run types, and paces
- **Suggested Conditions — Last 90 Days** — uses Best Running Conditions to pre-fill preferred temperature and time settings on the Run Planner

## Tech Stack

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- Chart.js
- Strava API
- Open-Meteo API
- Gunicorn
- Render
- Git / GitHub

## Data Sources

RunTracker combines two data streams:

**1. Strava activity data** — Synced locally from the Strava API and stored in SQLite. Includes distance, pace, run date and start time, activity name, elevation when available, and other synced run fields.

**2. Open-Meteo data** — Historical weather matched to past runs by date, time, and coordinates for analysis and the Run Log, plus 7-day New Orleans forecast data used by the Run Planner.

## How the Data Is Processed

1. **Strava sync** — Runs are imported locally through the Strava API (`sync_strava.py`).
2. **SQLite storage** — Run records, pace values, start times, and synced metadata are stored in `runtracker.db`.
3. **Historical weather sync** — Past runs with coordinates and start times receive matched weather (`sync_weather.py`).
4. **Public database export** — A sanitized copy is generated for deployment (`create_public_db.py`), stripping tokens and sensitive fields.
5. **Dashboard and Analysis** — Flask routes query SQLite, filter by selected date range, and aggregate data through Python helper functions for charts and stat cards.
6. **Run Planner** — Uses live forecast data from Open-Meteo, recent running history, and Best Running Conditions to build a weekly run plan with suggested days, windows, distances, run types, and paces.

## Chart Methodology

All pace calculations use numeric `pace_seconds` (seconds per mile). Displayed pace is formatted as minutes per mile. **Lower pace means faster.**

Dashboard and Analysis pages support date filters: `?range=30d`, `?range=90d`, `?range=365d` (default), and `?range=all`.

### Dashboard

| Chart | Calculation | Chart type |
|-------|-------------|------------|
| **Weekly Mileage** | Sum of `distance_miles` per week; week starts Monday | Bar |
| **Monthly Mileage** | Sum of `distance_miles` per calendar month | Bar |
| **Longest Run by Month** | Maximum single-run `distance_miles` per calendar month | Bar |
| **Pace Trend** | Mean `pace_seconds` per week (Monday week start) | Line |

Stat cards on the Dashboard use the same filtered run list: total miles, run count, longest run, and overall average pace.

### Analysis

| Chart | Calculation | Chart type |
|-------|-------------|------------|
| **Distance vs Pace** | One point per run: distance vs `pace_seconds` | Scatter |
| **Average Pace by Distance Bucket** | Runs grouped into mutually exclusive distance buckets (0–2, 2–3, 3–4, 4–5, 5–6, 6+ mi); mean `pace_seconds` per bucket | Bar |
| **Distance Distribution** | Count of runs per distance bucket | Bar |
| **Runs by Day of Week** | Count of runs per weekday | Bar |
| **Runs by Time of Day** | Count of runs per 90-minute start-time window (7:00 AM – 10:00 PM) | Bar |
| **Average Pace by Time of Day** | Mean `pace_seconds` per same time-of-day bucket | Bar |
| **Pace vs Temperature** | One point per weather-backed run: temperature vs `pace_seconds` | Scatter |
| **Average Pace by Temperature** | Weather-backed runs grouped into 10°F temperature buckets; mean `pace_seconds` per bucket | Bar |

## Best Running Conditions

An aggregate insight panel derived from recent weather-backed runs:

1. Filter to runs at least **2 miles** long with valid pace, temperature, and qualifying start time (7:00 AM – 10:00 PM buckets).
2. Group runs by **time-of-day bucket** and **temperature bucket**.
3. Keep only groups with at least **5 runs**.
4. Select the group with the **fastest average pace** (`pace_seconds`).
5. Display summary stats: best time window, temperature range, average pace, run count, average distance, and average temperature.

This identifies the strongest aggregate pattern in the selected date range. It is an exploratory insight, not a guarantee of future performance.

## Run Planner

Plan My Week on the Run Planner page builds a weekly run schedule from the next 7 days of forecast data and your recent running history. **Suggested Conditions — Last 90 Days** pre-fills defaults when enough weather-backed runs exist. Routes: `/weather` (primary) and `/run-planner` (alias).

### Inputs

| Setting | Options | Default |
|---------|---------|---------|
| **Runs per week** | 1–7, or auto | Auto — your 90-day average runs per week, **rounded up** (clamped to 1–7) |
| **Weekly mileage** | Auto or fixed targets (8–30 mi) | Auto — your average weekly total from the last 90 days |
| **Minimum / maximum temperature** | °F | From **Suggested Conditions** when available, otherwise 55–85°F |
| **Preferred time of day** | 90-minute buckets (7:00 AM – 10:00 PM) or Anytime | From **Suggested Conditions** when available |
| **Average pace** | Auto or fixed offsets from your default | Auto — average pace for your best time/temperature group (see below) |

**Use Suggested Conditions** applies those defaults to Plan My Week and generates your plan in **Your Plan**. You can change any setting and click **Plan My Week** again at any time.

### Defaults from your last 90 days

These values power the auto dropdown labels and the Suggested Conditions card:

**Runs per week**

- Count runs in every calendar week that overlaps the 90-day window (weeks with zero runs count as 0).
- Average: `total runs ÷ number of calendar weeks in the window`
- Default: **round up** to the next whole number, clamped between 1 and 7.

Example: 29 runs across 14 weeks → average 2.1 → default **3** runs per week.

**Weekly mileage**

- Sum `distance_miles` per Monday-start week for weeks where you ran.
- Default: **mean of those weekly totals**.

**Average pace**

- If **Best Running Conditions** finds a qualifying group (see below), use the mean `pace_seconds` for runs in that best time + temperature group.
- Otherwise, use the **median** `pace_seconds` across all runs in the last 90 days.

**Suggested Conditions — Last 90 Days**

Uses the same Best Running Conditions logic as Analysis, but scoped to 90 days:

1. Filter to runs ≥ **2 miles** with valid pace, temperature, and start time (7:00 AM – 10:00 PM buckets).
2. Group by **90-minute time-of-day bucket** and **10°F temperature bucket**.
3. Keep only groups with at least **5 runs**.
4. Select the group with the **fastest average pace**.
5. Display that group’s time window, temperature range, average pace, plus your 90-day runs-per-week and weekly mileage defaults.

### How your plan is built

RunTracker scores each daylight hour in the next 7 days using your temperature range, rain probability, and preferred time of day, then picks the highest-scoring days for your runs-per-week setting. Each run gets a time window from the best consecutive hours that day. When you plan two or more runs, easy runs share your weekly mileage evenly and one long run on the best forecast day is 1 mile longer than each easy run. Easy runs use your selected average pace; the long run adds 20 seconds per mile. A **~** mark on a day means that window did not fully match your ideal temperature range.

#### 1. Score forecast hours

Only **daylight hours** (between sunrise and sunset) are considered.

Each hour receives a score:

| Factor | Calculation | Reason |
|--------|-------------|--------|
| **Temperature** | 100 if inside your min–max range; otherwise lose **6 points per °F** outside the range (minimum 0) | Prefer your chosen comfort band, but still rank colder/hotter hours instead of excluding them |
| **Rain** | Subtract **0.5 × precipitation probability**, capped at **50** | Lower rain chance ranks higher |
| **Preferred time** | **+15** if the hour falls in your preferred time-of-day bucket | Nudge runs toward when you said you prefer to run |

**Hour score** = temperature score − rain penalty + time bonus

#### 2. Pick a day and time window

For each forecast day:

1. Score every daylight hour.
2. Find the best **consecutive block of hours** (prefer blocks of 2+ hours with the highest average hour score; a single hour is used if nothing better exists).
3. That block’s average score becomes the **day score**.
4. The displayed time window is the start and end of that block.

Days are ranked by day score. RunTracker selects the **top N days**, where N is your runs-per-week setting, then sorts them chronologically for display.

#### 3. Assign distances

**One run:** assign the full weekly mileage target to that run.

**Two or more runs:**

1. **Easy run distance** = `(weekly target − 1 mile) ÷ number of runs`, rounded to the nearest **0.5 mi** (minimum **1.0 mi**).
2. **Long run distance** = easy distance **+ 1.0 mi**.
3. The **long run** goes on the day with the **highest forecast score**; all other runs are easy runs at the easy distance.

Example with a **9.6 mi** target and **3 runs**:

- Easy distance = `(9.6 − 1) ÷ 3 = 2.87` → **3.0 mi**
- Long run = **4.0 mi**
- Plan: 3.0 + 3.0 + 4.0 = **10.0 mi planned** (target 9.6 mi; small differences come from half-mile rounding)

This keeps the rule simple: every easy run is the same length, and the long run is always exactly 1 mile longer.

#### 4. Assign pace

| Run type | Pace |
|----------|------|
| **Easy** | Your selected average pace |
| **Long run** | Selected average pace **+ 20 seconds per mile** |

The default average pace comes from your best time/temperature group when Suggested Conditions has enough data; otherwise from your 90-day median pace. Long runs are intentionally slower — a straightforward easy-vs-long distinction without a full training model.

#### 5. Ideal vs closest-available windows

A run is marked **ideal** when every hour in its window falls inside your min–max temperature range. If not, the row shows a **~** badge: RunTracker still picked the best available window for that day, but temperatures were partially outside your preferred band.

#### Summary line in Your Plan

After you click **Plan My Week**, the header shows:

`N runs · X.X mi planned (target Y.Y mi · M:SS /mi easy pace)`

- **Planned miles** = sum of assigned run distances (may differ slightly from target due to rounding).
- **Target** = your weekly mileage setting (auto or fixed).
- **Easy pace** = the resolved average pace used for easy runs (long run is +20 sec/mi).


## Screenshots

### Dashboard

The Dashboard summarizes running volume, pace, long runs, weekly mileage, monthly mileage, and recent runs with filtering, sorting, and pagination.

![Dashboard screenshot](docs/screenshots/dashboard.png)

### Analysis

The Analysis page explores performance patterns by distance, weekday, time of day, and temperature, plus Best Running Conditions when enough weather-backed data exists.

![Analysis screenshot](docs/screenshots/analysis.png)

### Run Planner

The Run Planner uses forecast data and recent running patterns to recommend a weekly run plan with suggested days, time windows, distances, run types, and paces.

![Run Planner screenshot](docs/screenshots/weather-planner.png)

## Local Development Setup

1. **Create a virtual environment**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # macOS/Linux
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Copy `.env.example` to `.env` and set at least `FLASK_SECRET_KEY`.

   For local Strava sync development, also set:

   - `STRAVA_CLIENT_ID`
   - `STRAVA_CLIENT_SECRET`
   - `STRAVA_REDIRECT_URI`
   - `ENABLE_STRAVA_ROUTES=true`

   OAuth tokens are stored in the local SQLite database after you connect. Do not paste tokens into `.env`.

4. **Run the app**

   ```bash
   python app.py
   ```

   Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

5. **Connect Strava and sync runs** (local development only)

   With `ENABLE_STRAVA_ROUTES=true`, visit [http://127.0.0.1:5000/strava/connect](http://127.0.0.1:5000/strava/connect), authorize the app, then run the sync scripts described in [Updating Run Data](#updating-run-data).

## Updating Run Data

Because the live version uses `public_runtracker.db`, run data updates require regenerating the sanitized public database locally and pushing it to GitHub.

1. **Sync new Strava activities**

   ```powershell
   python sync_strava.py
   ```

2. **Sync historical weather for newly imported runs**

   ```powershell
   python sync_weather.py
   ```

3. **Rebuild the sanitized public database**

   ```powershell
   python create_public_db.py
   ```

4. **Verify the public database is safe**

   ```powershell
   python verify_public_db.py
   ```

5. **Test locally with the public database**

   ```powershell
   $env:DATABASE_PATH="public_runtracker.db"
   $env:ENABLE_STRAVA_ROUTES="false"
   python app.py
   ```

6. **Commit and push the updated public database**

   ```powershell
   git status
   git add public_runtracker.db README.md
   git commit -m "Update public running data"
   git push
   ```

To update the data cutoff date shown in documentation, use the latest run date printed by `create_public_db.py`.

## Deployment Notes

- The app is deployed on [Render](https://render.com/).
- Start command: `gunicorn app:app`
- The live service should use:
  - `DATABASE_PATH=public_runtracker.db`
  - `ENABLE_STRAVA_ROUTES=false`
- Strava OAuth routes are disabled in the live version.
- The live version does not need Strava secrets because it uses the sanitized public database.

A `Procfile` is included for Render and similar platforms.

## Security Notes

- Do **not** commit `.env`
- Do **not** commit `runtracker.db`
- Do **not** commit private database backups
- Only `public_runtracker.db` should be committed as a database file
- Run `python verify_public_db.py` before committing an updated public database
- `public_runtracker.db` should not contain Strava tokens, OAuth tables, access tokens, refresh tokens, client secrets, or exact coordinates

## Future Improvements / To Do

- Add automatic daily Strava sync
- Add automatic weather sync after new runs are imported
- Add user accounts
- Allow users to connect their own Strava accounts
- Allow configurable weather location instead of hardcoded New Orleans
- Add admin-only sync controls
- Move to a production database if the app becomes multi-user
- Add tests for analysis and database helper functions
- Add more screenshots or demo GIFs if useful

## Optional Sample Data

For a quick demo without Strava, you can run `python seed_data.py` to populate sample runs. For real use, connect Strava and sync instead.
