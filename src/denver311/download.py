"""Download Denver 311 yearly service request files from the Denver Open Data Catalog.

2019-2023 are published as ArcGIS Feature Services and are pulled through the Hub CSV
export. 2024-2025 are published as CSV items and are pulled from the item data endpoint.
Each file is written to data/raw/ and recorded in data/raw/manifest.json with its SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from denver311 import RAW_DIR

HUB = "https://opendata-geospatialdenver.hub.arcgis.com"
ARCGIS = "https://www.arcgis.com/sharing/rest/content/items"

# ArcGIS item IDs owned by The_City_and_County_of_Denver.
ITEMS: dict[int, tuple[str, str]] = {
    2019: ("acc3b988031749038b54c2fb8eedf320", "feature_service"),
    2020: ("63678a1854b740fba4ccdb34f5857538", "feature_service"),
    2021: ("7b1e415350424ed495b813874b02e88e", "feature_service"),
    2022: ("ef0a786fce784065918854d5b7eb28a7", "feature_service"),
    2023: ("ff6c84d8881647ca97b439971ad20a72", "feature_service"),
    2024: ("79f43c95bf9a4ac19ef8217c5367e6c4", "csv_item"),
    2025: ("5bdb9b3033d74782a4c410e548887ede", "csv_item"),
}


# Neighborhood polygons with ACS 2019-2023 population, used for the spatial join and rates.
NEIGHBORHOODS_ITEM = "9bd8a0dd46714e3a96c489b0f8dc3edb"
NEIGHBORHOODS_URL = (
    "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/"
    "Common_Data_Indicators_American_Community_Survery_Neighborhoods_20192023/FeatureServer/0/"
    "query?where=1%3D1&outFields=NBHD_ID,NBHD_NAME,DIST_NUM,Nmbr_Population,Nmbr_Households,"
    "Nmbr_PerCapitaIncome,Pct_PopulationInPoverty,Pct_OccupiedUnitsWithRenters"
    "&outSR=4326&f=geojson"
)


def source_url(item_id: str, kind: str) -> str:
    if kind == "feature_service":
        return f"{HUB}/api/download/v1/items/{item_id}/csv?layers=0"
    return f"{ARCGIS}/{item_id}/data"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, dest: Path, attempts: int = 4) -> None:
    tmp = dest.with_suffix(".part")
    for attempt in range(1, attempts + 1):
        try:
            with requests.get(url, stream=True, timeout=120, allow_redirects=True) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
            tmp.replace(dest)
            return
        except requests.RequestException as exc:
            if attempt == attempts:
                raise
            wait = 5 * attempt
            print(f"  attempt {attempt} failed ({exc}); retrying in {wait}s")
            time.sleep(wait)


def count_lines(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for _ in fh)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=sorted(ITEMS))
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = RAW_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for year in args.years:
        item_id, kind = ITEMS[year]
        dest = RAW_DIR / f"311_service_requests_{year}.csv"
        url = source_url(item_id, kind)
        previous = manifest.get(str(year), {})
        if dest.exists() and not args.force:
            print(f"{year}: exists, skipping ({dest.name})")
            downloaded_at = previous.get("downloaded_at")
        else:
            print(f"{year}: downloading {kind} {item_id}")
            fetch(url, dest)
            downloaded_at = datetime.now(UTC).isoformat(timespec="seconds")
        manifest[str(year)] = {
            "item_id": item_id,
            "kind": kind,
            "source_url": url,
            "item_page": f"{HUB}/datasets/{item_id}",
            "file": dest.name,
            "bytes": dest.stat().st_size,
            "text_lines": count_lines(dest),
            "sha256": sha256(dest),
            "downloaded_at": downloaded_at,
        }
        print(
            f"  {manifest[str(year)]['bytes']:,} bytes, sha256 {manifest[str(year)]['sha256'][:12]}"
        )

    nbhd = RAW_DIR / "neighborhoods_acs_2019_2023.geojson"
    if not nbhd.exists() or args.force:
        print("neighborhoods: downloading ACS 2019-2023 neighborhood polygons")
        fetch(NEIGHBORHOODS_URL, nbhd)
    manifest["neighborhoods"] = {
        "item_id": NEIGHBORHOODS_ITEM,
        "kind": "feature_service_geojson",
        "source_url": NEIGHBORHOODS_URL,
        "item_page": f"{HUB}/datasets/{NEIGHBORHOODS_ITEM}",
        "file": nbhd.name,
        "bytes": nbhd.stat().st_size,
        "features": len(json.loads(nbhd.read_text())["features"]),
        "sha256": sha256(nbhd),
        "downloaded_at": manifest.get("neighborhoods", {}).get("downloaded_at")
        or datetime.now(UTC).isoformat(timespec="seconds"),
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
