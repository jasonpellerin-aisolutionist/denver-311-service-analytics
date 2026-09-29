# Tableau Public dashboard: build and publish guide

Everything Tableau needs is in `tableau/exports/` (aggregates only, about 1 MB). Rebuild the
exports with `make export`. The dashboard is built in **Tableau Public (Apple silicon)** and
saved to a free Tableau Public profile.

Working title: **Denver 311: Where the Work Comes From and How Fast It Closes (2019-2025)**

## Fast path: generated workbook

`make tableau` writes `tableau/denver311_dashboard.twbx`: the eight worksheets, the dashboard
below, calculated fields, and the project palettes, packaged with one `.hyper` extract per data
source (built from `tableau/exports/` with Tableau's Hyper API). It also installs the palettes
into `~/Documents/My Tableau Repository/Preferences.tps`. The `.twbx` is generated, not committed.

1. Open `tableau/denver311_dashboard.twbx` in Tableau Public (Desktop).
2. Check each sheet, then follow **Publish** below.

Tableau Public only opens workbooks whose data are extracts, which is why the sources ship as
`.hyper` files rather than live CSV links. The neighborhood map is drawn from
`neighborhood_polygons.csv` (one row per outline vertex, Polygon mark, Path = point order)
because spatial files are not extracted. Outlines are exterior rings only, so the seven interior
holes (enclaves) are filled.

The rest of this guide documents the same build by hand.

## Palette

Use these colors only (no red or orange anywhere, including default Tableau palettes).

| Role | Hex |
|---|---|
| Primary (navy) | `#1e3a5f` |
| Secondary (teal) | `#0f766e` |
| Accent (blue) | `#2563eb` |
| Muted (slate) | `#64748b` |
| Light fill | `#cbd5e1` |
| Title text | `#0f172a` |
| Body text | `#334155` |

For sequential color, use a custom two-color ramp from `#f1f5f9` to `#1e3a5f`. For the wait
index map, use a custom diverging ramp `#0f766e` / `#f8fafc` / `#1e3a5f` centered at 0.50,
range 0.45 to 0.55.

## Data sources

Connect each file as its own data source (Connect > To a File > Text file, or Spatial file).

| Data source | File | Grain |
|---|---|---|
| KPIs | `kpi_summary.csv` | one row per headline metric |
| Type Year | `type_year.csv` | request type x year, top 25 types present all 7 years |
| Published LOS | `published_los.csv` | request type x year for the 5 types with a DOTI Level of Service goal |
| Monthly | `monthly_category.csv` | month x request category |
| Channel Year | `channel_year.csv` | year x intake channel |
| Channel Speed | `channel_speed.csv` | request type, phone vs app median hours |
| Neighborhoods | `neighborhood_polygons.csv` | one row per outline vertex of the 78 neighborhoods, with metrics (`neighborhoods_metrics.geojson` holds the same shapes for other tools) |
| Hotspots (optional) | `hotspots.csv` | 0.005 degree grid cell x category, cells with 25+ requests |

In **Type Year**, set `year` to a discrete dimension (Date part not needed) and `record_gap`
to a boolean dimension.

## Calculated fields

Type Year:

```
// P50 days
[p50_hours] / 24

// P90 days
[p90_hours] / 24

// 2019 benchmark (P90 days)  -- derived, not a city target
[p90_hours_2019] / 24

// Benchmark label
IF [record_gap] THEN "gap" ELSE STR(ROUND([share_within_2019_p90] * 100)) + "%" END
```

Monthly:

```
// Month
DATE([month])

// Rolling 12-month field requests (table calc, compute using Month)
WINDOW_SUM(SUM([field_requests]), -11, 0)
```

Channel Year:

```
// Channel group
IF [channel] = "Phone" OR [channel] = "App (PocketGov)" THEN [channel] ELSE "Other channels" END
```

Channel Speed:

```
// App slower by (hours)
[app_minus_phone_hours]
```

## Worksheets

1. **KPI tiles** (KPIs). Filter `metric` to: Field requests 2019-2025; Field share of
   contacts; Like-for-like field requests, 2019 to 2025; App share of field requests, 2025;
   Type-years with a record gap. Text mark showing `value` formatted per `unit`, `metric` as
   the label. One tile per metric, navy numbers, slate labels.
2. **Type speed** (Type Year). Rows: `request_type` sorted by P90 days. Columns: dual axis of
   P50 days (teal circle) and P90 days (navy circle), synchronized log axis. Add a
   `year` single-value dropdown filter defaulting to 2025.
3. **Benchmark heatmap** (Type Year). Rows: `request_type`. Columns: `year`. Color:
   `share_within_2019_p90` sequential ramp 0 to 1. Label: `Benchmark label`. Tooltip explains
   that 2019 equals 90% by construction and that "gap" means the closure record is incomplete.
4. **Against DOTI goals** (Published LOS). Columns: `year`. Rows: `share_within_los`. Color:
   `request_type`. Line with markers, y axis 50% to 100%. Title the view with the goal source:
   "DOTI Level of Service goals, business days (denvergov.org)".
5. **Monthly trend** (Monthly). Columns: `Month` (continuous month). Rows:
   `SUM(field_requests)`. Color: `request_category`, filtered to the top 6 categories by
   volume, using navy, teal, blue, slate, `#5b8db8`, `#5eada5`. Add the rolling 12-month line
   as a second view or a reference toggle.
6. **Neighborhood wait map** (Neighborhoods). Set `latitude` and `longitude` to their
   geographic roles and put AVG of each on Rows and Columns. Mark type Polygon, `neighborhood`
   and `part_id` on Detail, `point_order` (dimension) on Path. Color: `wait_index`
   diverging ramp centered at 0.50. Filter `ranked_requests >= 500` (show the rest in light
   grey via a second layer or leave unfiltered with a note). Tooltip: neighborhood, wait index,
   P50 days, field requests per 1k residents per year, per-capita income, poverty rate.
7. **Channel share** (Channel Year). Columns: `year`. Rows: `share_of_field`. Color:
   `Channel group` (Phone navy, App teal, Other slate). Line chart with markers.
8. **Phone vs app** (Channel Speed). Dumbbell: rows `request_type` sorted by phone median,
   columns dual axis `phone_p50_hours` (navy) and `app_p50_hours` (teal), log axis.

## Dashboard layout

- Size: fixed 1200 x 1400 (Tableau Public renders fixed sizes cleanly in an embed).
- Top band: title, one-sentence subtitle, KPI tiles.
- Row 2: Benchmark heatmap (left, 60%) and Type speed (right, 40%). Year filter applies to Type
  speed only.
- Row 3: Against DOTI goals (left) and Monthly trend (right).
- Row 4: Neighborhood wait map (left) and Channel share over Phone vs app (right).
- Footer text: "Source: Denver Open Data Catalog, 311 Service Requests 2019-2025 (CC BY 3.0).
  Benchmark = each type's own 2019 P90, derived for this analysis. Code:
  github.com/jasonpellerin-aisolutionist/denver-311-service-analytics"

## Publish

1. File > Save to Tableau Public As... and sign in (free account).
2. Name: `Denver 311 Service Analytics 2019-2025`.
3. On the published page, open Settings and allow workbook download (lets reviewers inspect
   the build), and set the dashboard as the default view.
4. Copy the share link and the embed code (Share > Embed Code).
5. Save screenshots to `tableau/screenshots/` as `dashboard_full.png`, `benchmark_heatmap.png`,
   and `neighborhood_map.png`.
6. Add the link to the README "Live links" section and to the Wix post (Tableau embed block or
   hero link).
