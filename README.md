# RunTracker

**Live site:** [https://runtracker-lirm.onrender.com/](https://runtracker-lirm.onrender.com/)  
**Download workbook:** [RunTracker.xlsx](https://runtracker-lirm.onrender.com/docs/RunTracker.xlsx)

RunTracker is a personal running analytics app I built to better understand my own training data. I started running in August 2025 and have been recording my runs with an Apple Watch, with Strava storing detailed activity metrics like distance, pace, time, elevation, and run history. This app pulls that running data together with historical weather data for each run, then uses dashboards, charts, and analysis tools to help identify patterns in my performance and make better decisions about future runs.

## Data Pipeline

RunTracker pulls running data from Strava and historical weather from Open-Meteo, cleans and organizes both, then combines them in SQLite so each run has its conditions attached. That dataset powers the dashboards and charts in the app, and can be exported to Excel for further analysis with formulas, PivotTables, and slicers.

### 1. Strava activity data

Runs are synced from the Strava API. The raw activity data needs cleaning before it's useful: distance arrives in meters, moving time in seconds, and timestamps include both UTC and local values.

Only run-type activities are kept. Distance is converted to miles, moving time is turned into a readable duration and a pace per mile, and the local start time is split into separate date and time fields. Elevation and start coordinates are stored with those metrics in SQLite, so each row is a clean, consistent run record.

### 2. Open-Meteo weather data

For each stored run, historical hourly weather is requested from Open-Meteo using the run date and start coordinates. The hour closest to the run start is matched, weather codes are mapped to readable labels, and temperature, humidity, wind speed, and precipitation are stored with that run.

A separate forecast endpoint supplies the next 7 days of data for the Run Planner. That forecast is used for planning only, not for adding weather to past runs.

### 3. Combine, store, and display

After both sources are cleaned, weather fields are written onto the same SQLite row as the Strava activity. The result is one table where each record is a run plus the conditions it was run in, which makes it straightforward to filter and compare performance by temperature, weekday, or time of day.

That combined dataset drives the Dashboard, Run Log, and Analysis pages—summary stats, charts, and a single readable weather string on each run in the table.

### 4. Export and Excel analysis

From the Run Log, **Export to Excel** downloads a flat workbook with Date, Start Time, Distance, Pace, Time, and Weather. **Download Workbook** in the nav is the cleaned and analyzed version of that export. Details are in [Excel Analysis](#excel-analysis) below.

## Screenshots

### Dashboard

The Dashboard summarizes running volume, pace, long runs, weekly mileage, monthly mileage, and recent runs with filtering, sorting, and pagination.

![Dashboard screenshot](docs/screenshots/dashboard.png)

### Analysis

The Analysis page explores performance patterns by distance, weekday, time of day, and temperature, plus Best Running Conditions when enough weather-backed data exists.

![Analysis screenshot](docs/screenshots/analysis.png)

### Run Planner

Weekly plan from forecast data and recent running history.

![Run Planner screenshot](docs/screenshots/weather-planner.png)

### Excel Raw Data

![Excel Raw Data screenshot](docs/screenshots/Excel_Data_Screenshot.png)

Raw export from the Run Log (**Export to Excel**). The finished workbook is available via **Download Workbook**.

### Excel Analysis

#### Runs

![Excel Runs screenshot](docs/screenshots/Excel_Runs_Screenshot.png)

I converted the export into an Excel Table so the filters, formulas, and formatting stay consistent. Since the weather data came in as one value, such as "91°F Drizzle," I split it into separate Temperature and Weather Condition columns. I also added a Month column so the data sorts correctly by month and year.

Above the table, I added a Run Summary that shows average pace, average time, average distance, total distance, and total runs. The summary uses SUBTOTAL, so it updates when the Month or Weather Condition slicers are used. I also added a weather analysis section with COUNTIFS, SUMIFS, AVERAGEIFS, and MAXIFS, along with a Fastest Qualifying Run section that uses MINIFS and XLOOKUP.

#### Pivot Analysis

![Excel Pivot Analysis screenshot](docs/screenshots/Excel_PivotAnalysis_Screenshot.png)

I used PivotTables to summarize the run data by month, including total runs, total distance, and average pace. The main PivotTable includes a Grand Total row for the full dataset.

I also created separate monthly PivotTables for average pace and total distance. These are used as the data sources for the matching charts on the Dashboard and keep the chart setup simple and organized.

#### Dashboard

![Excel Dashboard screenshot](docs/screenshots/Excel_Dashboard_Screenshot.png)

The Dashboard includes four charts: Average Pace by Month, Monthly Running Distance, Distance vs. Pace, and Temperature vs. Pace. The monthly charts are connected to PivotTables, while the scatter charts use the individual rows from the RunLog table.

The pace axes are reversed so faster times appear higher on the charts. The Dashboard also includes a Month Timeline and Weather Condition slicer for the monthly charts, while the slicers on the Runs sheet control the source table, Run Summary, and scatter charts.

## Features

- **Dashboard** — stat cards, charts, date-range filters (Last 30 days, Last 90 days, Last 365 days, All time), and **Shoe Mileage** tracker
- **Run Log** — sortable, paginated runs table with weather display
- **Analysis** — performance charts by distance, timing, and temperature, plus **Best Running Conditions** insights
- **Run Planner** — weekly plan from forecast data and recent running history
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

## Chart Methodology

### Dashboard

| Chart | Calculation | Chart type |
|-------|-------------|------------|
| **Weekly Mileage** | Sum of `distance_miles` per week; week starts Monday | Column |
| **Monthly Mileage** | Sum of `distance_miles` per calendar month | Column |
| **Longest Run by Month** | Maximum single-run `distance_miles` per calendar month | Column |
| **Pace Trend** | Mean `pace_seconds` per week (Monday week start) | Line |

### Analysis

| Chart | Calculation | Chart type |
|-------|-------------|------------|
| **Distance vs Pace** | One point per run: distance vs `pace_seconds` | Scatter |
| **Average Pace by Distance Bucket** | Runs grouped into mutually exclusive distance buckets (0–2, 2–3, 3–4, 4–5, 5–6, 6+ mi); mean `pace_seconds` per bucket | Column |
| **Distance Distribution** | Count of runs per distance bucket | Column |
| **Runs by Day of Week** | Count of runs per weekday | Column |
| **Runs by Time of Day** | Count of runs per 90-minute start-time window (7:00 AM – 10:00 PM) | Column |
| **Average Pace by Time of Day** | Mean `pace_seconds` per same time-of-day bucket | Column |
| **Pace vs Temperature** | One point per weather-backed run: temperature vs `pace_seconds` | Scatter |
| **Average Pace by Temperature** | Weather-backed runs grouped into 10°F temperature buckets; mean `pace_seconds` per bucket | Column |

## Run Planner

RunTracker scores each daylight hour in the next 7 days using your temperature range, rain probability, and preferred time of day, then picks the highest-scoring days for your runs-per-week setting. Each run gets a time window from the best consecutive hours that day. When you plan two or more runs, easy runs share your weekly mileage evenly and one long run on the best forecast day is 1 mile longer than each easy run. Easy runs use your selected average pace; the long run adds 20 seconds per mile. A **~** mark on a day means that window did not fully match your ideal temperature range.
