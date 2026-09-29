"""Clean the raw Denver 311 yearly files into one analysis-ready parquet table.

Every transformation is recorded in data/processed/cleaning_log.json with the number of rows
it touched, so the notebook and the Google Sheet quality log report the same numbers.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from denver311 import PROCESSED_DIR, RAW_DIR

YEARS = range(2019, 2026)

# Denver city limits plus a small buffer (DIA sits far to the northeast).
LAT_RANGE = (39.60, 39.92)
LON_RANGE = (-105.12, -104.59)

TS_FORMAT = "%m/%d/%Y %I:%M:%S %p"

AGENCY_RENAMES = {
    "Environmental Health": "Public Health & Environment",
    "AFR Accounting": "Finance",
    "Accounting": "Finance",
    "ROWE": "Public Works",
}

STATUS_RENAMES = {
    "Closed - Transfered to External Agency": "Closed - Transferred to External Agency",
    "Closed - Duplicate Case": "Closed - Duplicate",
    "Spam": "Closed - Spam",
    "Approved": "Closed - Approved",
}

STATUS_GROUPS = {
    "Closed - Answer Provided": "answered",
    "Closed - Transferred to External Agency": "transferred",
    "Closed - Out of Jurisdiction": "out_of_jurisdiction",
    "Closed - In Compliance": "resolved",
    "Closed - No Violation Found": "resolved",
    "Closed - Service Completed": "resolved",
    "Closed - Scheduled": "resolved",
    "Closed - Approved": "resolved",
    "Closed - Not Approved": "resolved",
    "Closed - Resolved by Customer": "resolved",
    "Closed - Photos": "resolved",
    "Closed - Other": "resolved",
    "Closed - Spam": "invalid",
    "Closed - Created in Error": "invalid",
    "Closed - Duplicate": "invalid",
    "Closed - Canceled": "invalid",
    "Closed - Not Enough Info": "invalid",
    "Closed - No Response from Customer": "invalid",
}

# First match wins, so the more specific patterns sit above the general ones.
CATEGORY_RULES: list[tuple[str, str]] = [
    ("Encampments", r"encampment"),
    ("Parking & Vehicles", r"abandoned vehicle|parking|\browe\b|72 hour|vehicle|\btow"),
    (
        "Solid Waste",
        r"^swm\b|trash pickup|recycl|compost|dumped|large item|extra service|cart|service schedule"
        r"|service delay|dumpster",
    ),
    (
        "Streets & Traffic",
        r"pothole|signal|\bsigns?\b|street|ice blading|plow|sweep|traffic|alley|curb|pavement"
        r"|light out|streetlight|gutter|storm drain|right of way",
    ),
    (
        "Neighborhood Inspection",
        r"weed|vegetation|snow removal|trash in yard|\bnis\b|zoning|junk|graffiti|inspection"
        r"|nuisance|housing",
    ),
    ("Animals", r"dog|animal|\bpet\b|wildlife|cat\b|bird|cruelty|neglect|possible owner|stray"),
    (
        "Public Health & Noise",
        r"noise|face covering|health|food|restaurant|mosquito|rodent|bed bug",
    ),
    ("Parks & Trees", r"\bpark|tree|forestry|recreation|irrigation"),
    (
        "Public Safety (non-emergency)",
        r"\bdpd\b|police|911|sheriff|non.?emergen|dispatch|suspect|weapon|trespass|disturbance"
        r"|welfare|theft|accident|fireworks|unwanted",
    ),
    ("Clerk, DMV & Elections", r"dmv|registration|title|ballot|voter|marriage|record|court"),
    ("Licensing & Permits", r"licen|permit|\bexl\b|application"),
    ("Taxes & Property", r"\btax|assessor|property|lien"),
    ("General Information", r"information|inquiry|^other$|^311$|city & county|state"),
]


# Used only when no request-type rule matched.
AGENCY_FALLBACK = {
    "Safety": "Public Safety (non-emergency)",
    "Public Works": "Streets & Traffic",
    "Community Planning & Development": "Neighborhood Inspection",
    "Parks & Recreation": "Parks & Trees",
    "Excise & License": "Licensing & Permits",
    "Finance": "Taxes & Property",
    "Clerk & Recorder": "Clerk, DMV & Elections",
    "Public Health & Environment": "Public Health & Noise",
    "311": "General Information",
    "External Agency": "General Information",
    "Mayor's Office": "General Information",
    "City Council": "General Information",
    "Tech Services": "General Information",
    "Denver Human Services": "General Information",
}


@dataclass
class LogEntry:
    step: str
    rows: int
    decision: str


def normalize_header(name: str) -> str:
    return re.sub(r"\W+", "_", name.replace("\ufeff", "").strip().lower()).strip("_")


def read_year(year: int) -> pd.DataFrame:
    path = RAW_DIR / f"311_service_requests_{year}.csv"
    # 2019-2023 are UTF-8 with a BOM; 2024-2025 are Windows-1252.
    encoding = "cp1252" if year >= 2024 else "utf-8-sig"
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=encoding)
    df.columns = [normalize_header(c) for c in df.columns]
    df = df.drop(columns=["objectid"], errors="ignore")
    df.insert(0, "request_id", [f"{year}-{i:06d}" for i in range(1, len(df) + 1)])
    df.insert(1, "file_year", year)
    return df


def clean_text(s: pd.Series) -> pd.Series:
    s = s.str.replace("\xa0", " ", regex=False).str.replace(r"\s+", " ", regex=True).str.strip()
    return s.mask(s == "")


def parse_ts(s: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(s, format=TS_FORMAT, errors="coerce")
    missed = parsed.isna() & s.notna() & (s != "")
    if missed.any():
        parsed[missed] = pd.to_datetime(s[missed], format="mixed", errors="coerce")
    return parsed


def to_zip(s: pd.Series) -> pd.Series:
    z = s.str.extract(r"^(\d{5})", expand=False)
    return z.mask(z == "00000")


def to_district(s: pd.Series, upper: int) -> pd.Series:
    n = pd.to_numeric(s, errors="coerce")
    return n.where(n.between(1, upper)).astype("Int8")


def categorize(types: pd.Series, agencies: pd.Series) -> pd.Series:
    unique = pd.Series(types.dropna().unique())
    lowered = unique.str.lower()
    mapping = pd.Series("Other", index=unique.index)
    assigned = pd.Series(False, index=unique.index)
    for label, pattern in CATEGORY_RULES:
        hit = lowered.str.contains(pattern, regex=True) & ~assigned
        mapping[hit] = label
        assigned |= hit
    lookup = dict(zip(unique, mapping, strict=True))
    out = types.map(lookup).fillna("Other")
    fallback = agencies.map(AGENCY_FALLBACK)
    return out.mask((out == "Other") & fallback.notna(), fallback)


def channel(source: pd.Series) -> pd.Series:
    s = source.fillna("")
    out = pd.Series("Other", index=s.index)
    out[s.str.startswith("Email")] = "Email"
    out[s.str.startswith("City Council")] = "Council Office"
    out[s.isin(["Chat", "Citibot", "Request Form"]) | s.str.contains("Online|Web", regex=True)] = (
        "Web & Chat"
    )
    out[s == "Phone"] = "Phone"
    out[s == "PocketGov"] = "App (PocketGov)"
    return out


def main() -> None:
    log: list[LogEntry] = []

    df = pd.concat([read_year(y) for y in YEARS], ignore_index=True)
    log.append(LogEntry("load", len(df), "Read 7 yearly files; normalized headers across formats."))

    source_cols = [c for c in df.columns if c not in ("request_id", "file_year")]
    dupes = df.duplicated(subset=source_cols, keep="first")
    df = df[~dupes].reset_index(drop=True)
    log.append(
        LogEntry(
            "drop_exact_duplicates",
            int(dupes.sum()),
            "Dropped rows identical on every source field.",
        )
    )

    raw_summary = df["case_summary"].copy()
    for col in source_cols:
        df[col] = clean_text(df[col])
    changed = int(((raw_summary != df["case_summary"]) & df["case_summary"].notna()).sum())
    log.append(
        LogEntry(
            "trim_text",
            changed,
            "Request type text fixed (non-breaking spaces, padding); all text fields trimmed, blank to null.",
        )
    )

    empty = [
        c
        for c in ("division", "major_area", "type", "topic", "neighborhood")
        if df[c].notna().mean() < 0.001
    ]
    df = df.drop(columns=empty)
    log.append(
        LogEntry(
            "drop_empty_columns",
            len(empty),
            f"Dropped columns under 0.1% filled: {', '.join(empty)}.",
        )
    )

    renamed = df["agency"].isin(AGENCY_RENAMES)
    df["agency"] = df["agency"].replace(AGENCY_RENAMES).fillna("Unassigned")
    log.append(
        LogEntry(
            "merge_agency_names",
            int(renamed.sum()),
            "Environmental Health (2019 only) merged into Public Health & Environment; stray Accounting and ROWE labels merged.",
        )
    )

    restatus = df["case_status"].isin(STATUS_RENAMES)
    df["case_status"] = df["case_status"].replace(STATUS_RENAMES)
    df["status_group"] = df["case_status"].map(STATUS_GROUPS)
    df.loc[df["status_group"].isna(), "status_group"] = "open"
    log.append(
        LogEntry(
            "merge_status_labels",
            int(restatus.sum()),
            "Merged typo and synonym status labels (Transfered, Duplicate Case, Spam, Approved).",
        )
    )

    df["created_at"] = parse_ts(df["case_created_dttm"])
    df["closed_at"] = parse_ts(df["case_closed_dttm"])
    bad_created = int(df["created_at"].isna().sum())
    df = df[df["created_at"].notna()].reset_index(drop=True)
    log.append(
        LogEntry(
            "drop_unparseable_created",
            bad_created,
            "Dropped rows with no parseable created timestamp.",
        )
    )

    hours = (df["closed_at"] - df["created_at"]).dt.total_seconds() / 3600
    df["flag_closed_before_created"] = hours < 0
    df["hours_to_close"] = hours.where(hours >= 0)
    df["days_to_close"] = df["hours_to_close"] / 24
    df["is_closed"] = df["closed_at"].notna()
    log.append(
        LogEntry(
            "flag_closed_before_created",
            int(df["flag_closed_before_created"].sum()),
            "Close earlier than create: kept the row, nulled hours_to_close.",
        )
    )
    log.append(
        LogEntry(
            "open_cases",
            int((~df["is_closed"]).sum()),
            "No close timestamp: kept as open backlog, excluded from time-to-close percentiles.",
        )
    )
    log.append(
        LogEntry(
            "zero_duration",
            int((df["hours_to_close"] == 0).sum()),
            "Closed at the same second it was created: counted as handled on contact.",
        )
    )

    lat = pd.to_numeric(df.pop("latitude"), errors="coerce")
    lon = pd.to_numeric(df.pop("longitude"), errors="coerce")
    lon_copy = (lat == lon) & lat.notna() & (lat != 0)
    in_city = lat.between(*LAT_RANGE) & lon.between(*LON_RANGE)
    df["latitude"] = lat.where(in_city & ~lon_copy)
    df["longitude"] = lon.where(in_city & ~lon_copy)
    log.append(
        LogEntry(
            "null_longitude_copy",
            int(lon_copy.sum()),
            "Longitude equal to latitude (copy error): coordinates nulled.",
        )
    )
    outside = int(((lat.fillna(0) != 0) & ~in_city & ~lon_copy).sum())
    log.append(
        LogEntry(
            "null_outside_city",
            outside,
            "Non-zero coordinates outside the Denver bounding box: nulled.",
        )
    )
    zeros = int((lat.fillna(0) == 0).sum())
    log.append(LogEntry("zero_coordinates", zeros, "0 or blank coordinates treated as missing."))

    df["incident_zip"] = to_zip(df.pop("incident_zip_code").fillna(""))
    df["customer_zip"] = to_zip(df.pop("customer_zip_code").fillna(""))
    df["council_district"] = to_district(df["council_district"], 11)
    df["police_district"] = to_district(df["police_district"], 7)
    log.append(
        LogEntry(
            "normalize_zip_and_districts",
            len(df),
            "Zips to 5 digits (00000 is null); districts outside 1-11 / 1-7 (0, blank, text) are null.",
        )
    )

    df["has_location"] = (
        df["latitude"].notna()
        | df["incident_address_1"].notna()
        | df["incident_intersection_1"].notna()
    )
    df["request_type"] = df["case_summary"].fillna("(blank)")
    df["request_category"] = categorize(df["request_type"], df["agency"])
    log.append(
        LogEntry(
            "categorize_request_types",
            int(df["request_type"].nunique()),
            "Distinct request types mapped to 14 categories: keyword rules first, owning agency as fallback.",
        )
    )
    df["channel"] = channel(df["case_source"])
    df["first_call_resolution"] = df["first_call_resolution"].map({"Y": True, "N": False})
    df["created_date"] = df["created_at"].dt.date
    df["created_year"] = df["created_at"].dt.year.astype("int16")
    df["created_month"] = df["created_at"].dt.to_period("M").dt.to_timestamp()
    df["created_hour"] = df["created_at"].dt.hour.astype("int8")
    df["created_dow"] = df["created_at"].dt.dayofweek.astype("int8")

    df["is_field_request"] = df["has_location"] & df["status_group"].isin(
        ["answered", "resolved", "open"]
    )
    log.append(
        LogEntry(
            "define_field_requests",
            int(df["is_field_request"].sum()),
            "Field request = tied to a Denver place and not invalid, transferred out, or out of jurisdiction.",
        )
    )

    df = df.drop(
        columns=["case_created_date", "case_closed_date", "case_created_dttm", "case_closed_dttm"]
    )
    ordered = [
        "request_id",
        "file_year",
        "created_at",
        "closed_at",
        "created_date",
        "created_year",
        "created_month",
        "created_hour",
        "created_dow",
        "hours_to_close",
        "days_to_close",
        "is_closed",
        "flag_closed_before_created",
        "request_type",
        "request_category",
        "agency",
        "case_status",
        "status_group",
        "case_source",
        "channel",
        "first_call_resolution",
        "has_location",
        "is_field_request",
        "incident_address_1",
        "incident_address_2",
        "incident_intersection_1",
        "incident_intersection_2",
        "incident_zip",
        "customer_zip",
        "latitude",
        "longitude",
        "council_district",
        "police_district",
    ]
    df = df[ordered + [c for c in df.columns if c not in ordered]]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "requests.parquet"
    df.to_parquet(out, index=False)
    log.append(LogEntry("write", len(df), f"Wrote {out.name}."))

    (PROCESSED_DIR / "cleaning_log.json").write_text(
        json.dumps([asdict(e) for e in log], indent=2) + "\n"
    )
    for e in log:
        print(f"{e.step:<30} {e.rows:>10,}  {e.decision}")
    print(f"\nrows by year: {df.groupby('created_year').size().to_dict()}")
    print(
        f"field requests: {df['is_field_request'].mean():.1%}; has_location: {df['has_location'].mean():.1%}"
    )
    print(df["request_category"].value_counts().to_string())
    print(
        np.round(
            df.loc[df.is_field_request, "request_category"].value_counts(normalize=True), 3
        ).to_string()
    )


if __name__ == "__main__":
    main()
