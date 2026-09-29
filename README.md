# Where Denver's 311 slows down

**Seven years of Denver 311 service requests (2019-2025, 3.0 million contacts), cleaned,
modeled in DuckDB and PostgreSQL, and read the way an operations manager would read them.**

Analysis by [Jason Pellerin](https://www.jasonpellerin.com). I spent five years owning
scheduling and crew dispatch for a commercial field-service division, so the question I care
about is operational: where does the work come from, how fast does it close, and what would I
change on Monday?

**Live links**

- Interactive dashboard (Tableau Public): [Denver 311 Service Analytics](https://public.tableau.com/app/profile/jason.pellerin/viz/denver311_dashboard/Denver311ServiceAnalytics)
- Analyst workbook (Google Sheets, aggregates only): [Denver 311 Service Analytics 2019-2025](https://docs.google.com/spreadsheets/d/1JRjFq1S5DuKbDTFJ2JS4PkjELUqKWEnWJ7jfL9a-YIY/edit?usp=sharing)
- Notebooks with outputs: [`notebooks/`](notebooks/)
- Full findings with every figure: [`reports/findings.md`](reports/findings.md)

![Share closed within each type's own 2019 P90](reports/figures/fig07_benchmark_heatmap.png)

## The short version

1. **Most 311 contacts are questions, not field work.** Only 27% of 3,010,330 contacts are field
   requests tied to a Denver place, and 61% of all contacts close within 15 minutes.
2. **The biggest "slowdowns" in the data are record-keeping gaps, not service.** In 2023-2024,
   77-92% of weed, sidewalk snow, and trash-in-yard cases were never closed in the published
   file, and 83% of the 2025 sidewalk snow closures were stamped on a single day (May 6, 2025).
   13 of 175 type-years fail a basic record-integrity test.
3. **Where the records are complete, the real stories are specific.** New business license
   requests went from a 1-day median (2019) to 8.4 days (2021) and back to 3.9 days (2025).
   Potholes meet the city's own 5-business-day goal 78-98% of the time, every year.
4. **App requests close later than phone requests in all 14 comparable types.** Potholes: 3 hours
   by phone, 50 hours through the app (median time to close).
5. **About 15% of phone contacts are civic questions a published answer could handle**
   (property tax, vehicle registration, trash schedule, ballots, courts, pet adoption).
6. **Place explains very little once request mix is controlled.** Every council district sits
   between 0.486 and 0.516 on a 0-to-1 wait index where 0.50 is typical, and neighborhood wait does
   not track income (r = 0.06) or poverty (r = -0.05).

## The question

Denver publishes every 311 contact as open data. The obvious dashboard (volume by year, average
days to close) answers nothing an operations lead can act on. This project asks four sharper
questions:

- **Demand:** how did volume and mix shift from 2019 to 2025, once you compare like with like?
  What is the seasonal shape of each kind of work?
- **Speed:** for the top 25 field request types, what are the median (P50) and 90th percentile
  (P90) times to close, which types carry the longest tails, and how did that trend? Is the close
  timestamp even trustworthy?
- **Channel:** does the intake channel (phone, app, email) change how fast a request closes, and
  which phone questions could be self-service?
- **Place:** after controlling for request type, do some neighborhoods or council districts wait
  longer?

## The data

- **311 Service Requests**, City and County of Denver Open Data Catalog, seven yearly files
  2019-2025, 24 columns, licensed CC BY 3.0. Downloaded 2026-09-29 through the ArcGIS Hub API.
- **Statistical neighborhoods with ACS 2019-2023 demographics** (78 polygons, population 713,734),
  same catalog.
- **DOTI Level of Service goals** (business days), published on denvergov.org, for the five top
  request types that have one.

Provenance, checksums, and row counts: [`data/README.md`](data/README.md). Raw files are not
committed; `make download` fetches them.

## Cleaning

Profiling the raw files ([`01_profile_raw`](notebooks/01_profile_raw.ipynb)) turned up more
than the usual nulls:

- **Two publishing formats.** 2019-2023 are UTF-8 Feature Service exports with a byte-order mark;
  2024-2025 are Windows-1252 CSV uploads with fully quoted fields and line breaks inside text.
  Headers differ (`Case_Summary` vs `Case Summary`). Each year is read with its own encoding and
  the headers are normalized.
- **Five documented columns are empty in every year:** Division, Major Area, Type, Topic, and
  Neighborhood. Request type comes from the free-text Case Summary (48,803 distinct strings),
  categorized with keyword rules and an agency fallback. Neighborhood comes from a point-in-polygon
  join on coordinates (99.6% of geocoded rows matched).
- **The First Call Resolution flag is "Y" on 99% of rows,** including cases closed weeks later, so
  it is not used.
- **21,417 rows store the latitude in the longitude column,** 2,015 rows are exact duplicates, and
  agency and status labels drift across years (`Environmental Health` becomes `Public Health &
  Environment`; `Transfered` is a typo for `Transferred`).

Every step writes to a cleaning log with the rows it touched, and 11 post-load checks must pass
before analysis runs ([`02_cleaning_decisions`](notebooks/02_cleaning_decisions.ipynb), and the
Quality Log tab of the workbook).

## Method

- **Field request:** a contact tied to a Denver location whose status is answered, resolved, or
  still open. Transfers, out-of-jurisdiction calls, spam, duplicates, and cancellations are
  excluded. 816,266 rows.
- **Time to close:** created to closed timestamp on the 311 case. It measures the life of the
  record, which is not always the life of the work.
- **Like-for-like volume:** solid-waste request types leave the 311 file after 2020, so year-over-year
  volume excludes them.
- **Derived benchmark:** each request type's own 2019 P90 time to close. The city does not publish
  a target for most types, so this benchmark is **derived for this analysis, not a city standard**.
  2019 equals 90% by construction. Open cases count as misses.
- **Published goals:** where DOTI publishes a Level of Service goal, requests are also tested
  against it in business days (weekends excluded). The goals are current, so earlier years are a
  retrospective comparison.
- **Record gap:** a type-year where more than 20% of field requests were never closed, or more than
  25% of closures landed on one day. Those cells are shown as gaps, not as speed.
- **Wait index:** each closed request's percentile rank within its own type and year (0 fastest,
  1 slowest), averaged by area. 0.50 is typical. This keeps a neighborhood full of slow request
  types from looking slow for that reason alone.

## Findings

### 1. Demand: flat headline, rising like-for-like

![Contact mix](reports/figures/fig01_contact_mix.png)

Field requests fell from 158,617 (2019) to 105,837 (2025), which looks like a 33% drop. Most of it
is solid-waste requests leaving the 311 file (75,873 in 2019, 10 in 2021). On a like-for-like
basis field requests **rose 5.1%**, from 100,745 to 105,837, with a 2023 peak of 131,807. This is
conservative: from 2024, most encampment reports are recorded as transferred (91% in 2024, 80% in
2025) and so fall outside the field-request definition.

![Seasonality](reports/figures/fig03_seasonality.png)

Each kind of work has its own season: encampment reports run at 2.0x a typical month in June,
parks and trees at 1.8x in June, neighborhood inspection at 1.6x in January (sidewalk snow), and
solid waste at 1.4x in July.

### 2. Speed: the record gap comes first

![Record gap](reports/figures/fig08_record_gap.png)

In 2023, 77% of weed and 55% of trash-in-yard cases never received a close timestamp; in 2024 it
was 89% and 86%, and 92% for sidewalk snow. The cases sit at `Routed to Agency`. Then 83% of the
2025 sidewalk snow closures (and 31% of trash-in-yard closures) were stamped on May 6, 2025. Barking
dog cases show the same pattern in 2019-2022 (84-88% never closed). A naive dashboard reads these
years as either very fast or very slow. The honest reading is that the 311 record did not receive
the agency's outcome, so these cells are excluded from speed claims.

![Speed by type](reports/figures/fig06_type_speed.png)

Where records are complete:

- **Business licenses slowed and recovered.** New Business License medians: 1.0 day (2019, 149
  requests), 8.4 days (2021), 3.9 days with a P90 of 8.8 days (2025). Share within the derived
  benchmark: 90%, 29%, 71%. Renewals follow the same path.
- **Potholes are the steadiest service in the file.** Median between 0.6 and 2.5 days every year,
  81-98% within the derived benchmark.
- **Illegal parking splits in two:** 32% of closed cases close within an hour and 13% after 30
  days. The slow tail concentrates in 2023 (P90 81 days) and is gone by 2024-2025 (P90 about 2
  days).

![Against DOTI goals](reports/figures/fig14_published_los.png)

Against the city's own published goals, potholes meet 5 business days in 78-98% of cases each year.
The four signal and sign types held 86-99% through 2023, fell to 61-73% in 2024, and recovered to
78-94% in 2025. The derived benchmark shows the same 2024 dip, which is a useful check on the
derived method.

### 3. Channel: the app is slower on paper

![Channel share](reports/figures/fig09_channel_share.png)

The PocketGov app's share of field requests rose from 22.9% (2019) to 48.1% (2022), then fell
back to 25.7% (2025) as the phone share returned to 69%.

![Phone vs app](reports/figures/fig10_channel_speed.png)

In all 14 request types with at least 500 closed requests on each channel, app submissions take
longer to close. Potholes: 3.0 hours by phone, 50.4 hours by app. Signal timing: 50 hours vs 159.
The data cannot separate the causes (a phone agent can route and close in one step; an app
submission may wait in a triage queue), but the gap is consistent.

![Deflection candidates](reports/figures/fig11_deflection.png)

The top 20 topics answered on the spot by phone (no location, closed within 15 minutes) make up
25.1% of all phone contacts. The two largest are police-related codes. The civic questions in the
list make up 15.0%: general city information (45,564 calls over seven years), property tax
statements (40,647), vehicle registration (39,986), DMV (31,619), trash service schedule (26,274,
of which 6,297 in 2025), mail ballots (24,595), courts (22,984), and pet adoption (21,646).

### 4. Place: narrow differences once mix is controlled

![Neighborhood wait map](reports/figures/fig12_neighborhood_wait_map.png)

Across the 75 neighborhoods with at least 500 ranked requests, the wait index runs from 0.457
(Harvey Park South) to 0.533 (Cory-Merrill). Among the slowest are affluent Washington Park and
Washington Park West. Council districts range from 0.486 to 0.516.

![Wait vs income](reports/figures/fig13_wait_vs_income.png)

Wait does not track income (r = 0.06) or poverty (r = -0.05). Demand does: requests per resident
rise with the poverty rate (r = 0.24). This data does not show lower-income areas waiting longer
for the same work.

## Recommendations

1. **Close the loop before measuring speed.** Require agency systems to write outcomes back to 311,
   and publish a monthly record-integrity check (share never closed, share closed on one day) next
   to any speed metric. Code enforcement in 2023-2024 is the case to fix first.
2. **Triage app submissions like phone calls.** Set a same-day triage target for app intake and
   track the app-minus-phone median gap by type. Potholes (47 hours) and signal timing (109 hours)
   are the clearest tests.
3. **Publish the answers people call for.** An address-based trash-day lookup, plus seasonal
   phone-tree messages timed to property tax statements and elections, target the largest civic
   question topics (about 15% of phone contacts).
4. **Staff to the season.** Move inspection capacity toward January-February (sidewalk snow) and
   summer (weeds, encampments, parks), using the seasonal index to size the shift.
5. **Set goals where none are published, from the data.** For the 20 top types without a published
   goal, the 2019 P90 is a defensible starting target. Potholes show what a goal backed by
   complete records looks like: 5 business days, met in 78-98% of cases every year.
6. **Watch the wait index, not raw medians,** and plan capacity on requests per resident.

## Limits

- Time to close is the life of the 311 record. It is not proof that work was done or not done.
- The derived benchmark describes 2019 performance, not a service promise. DOTI goals are current
  and applied retrospectively.
- Categories come from free-text case summaries; about 80 rows remain uncategorized.
- Correlations with ACS demographics are neighborhood-level and descriptive, not causal.

## Tools

Built 100% native on Apple Silicon.

| Layer | Tool |
|---|---|
| Environment | uv, Python 3.12, Makefile |
| Cleaning | pandas 3, pyarrow (parquet) |
| Analytical SQL | DuckDB 1.5 with the spatial extension (point-in-polygon, GeoJSON export) |
| Relational model | PostgreSQL 17: typed schema, partial indexes, materialized views, parity checks against DuckDB |
| GUI | DBeaver (connections to both databases) |
| Analysis | JupyterLab, matplotlib |
| Sharing | Google Sheets (analyst workbook), Tableau Public ([published dashboard](https://public.tableau.com/app/profile/jason.pellerin/viz/denver311_dashboard/Denver311ServiceAnalytics), build in [`tableau/`](tableau/README.md)) |
| Editor, version control | Cursor, Git, GitHub |

## Reproduce

Requires macOS with Homebrew, `uv`, and PostgreSQL 17 running locally.

```bash
brew install uv postgresql@17 && brew services start postgresql@17
make setup        # uv sync + createdb denver311
make download     # 7 yearly files + neighborhoods, about 600 MB, with checksums
make clean        # pandas -> data/processed/requests.parquet + cleaning_log.json
make load-duckdb  # schema, neighborhood join, 11 quality checks
make load-postgres
make analyze      # sql/duckdb/10-40
make export       # aggregate CSVs + GeoJSON for Tableau and Sheets
make workbook     # reports/denver311_workbook.xlsx
make notebooks    # execute all four notebooks, regenerate reports/figures
```

## Repository layout

```
src/denver311/     download, clean, load_duckdb, load_postgres, analyze, export, workbook, style
sql/duckdb/        01 schema, 02 quality checks, 10 demand, 20 speed, 25 published goals, 30 channel, 40 place
sql/postgres/      schema, indexes, views and materialized views
notebooks/         01 profile raw, 02 cleaning decisions, 03 EDA, 04 findings
reports/           findings.md, figures/, denver311_workbook.xlsx
tableau/           exports/ (aggregates), dashboard build guide, screenshots/
data/              README (provenance), data_dictionary.csv; raw/ and processed/ are not committed
```

## Attribution

Data: City and County of Denver, Denver Open Data Catalog, licensed under
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). This project is independent and not
affiliated with the City and County of Denver. Code: MIT License.
