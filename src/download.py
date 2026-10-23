"""Fetch public datasets into data/raw/.

One function per source. Raw files are never modified — all cleaning and
derivation happens in prepare.py against copies in data/processed/.

Usage:
    python src/download.py all            # every scripted source
    python src/download.py ourairports    # airport + runway reference CSVs
    python src/download.py tracts         # TIGER/Line tract shapefiles, per state
    python src/download.py acs            # ACS 5-year demographic tables (needs CENSUS_API_KEY)

Files already younger than --max-age-days (default 7) are skipped; use
--force to re-download anyway. Every download is recorded in
data/raw/manifest.json (path, URL, fetch time) for data lineage.

Still manual (no reliable programmatic source — see docs/data-sources.md):
- Airport Noise Exposure Map contours, per airport
- EPA EJScreen
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.json"
HEADERS = {"User-Agent": "the-quiet-map/0.1 (portfolio project; public-data download)"}
DEFAULT_MAX_AGE_DAYS = 7

TIGER_VINTAGE = 2023
ACS_VINTAGE = 2022  # ACS 5-year; keep in sync with TIGER_VINTAGE

# Continental U.S. (lower 48 + DC); AK/HI are out of project scope.
STATE_FIPS = [
    "01", "04", "05", "06", "08", "09", "10", "11", "12", "13",
    "16", "17", "18", "19", "20", "21", "22", "23", "24", "25",
    "26", "27", "28", "29", "30", "31", "32", "33", "34", "35",
    "36", "37", "38", "39", "40", "41", "42", "44", "45", "46",
    "47", "48", "49", "50", "51", "53", "54", "55", "56",
]

OURAIRPORTS_BASE = "https://davidmegginson.github.io/ourairports-data"

# ACS 5-year tables: total pop, median HH income, median age, poverty
# (universe + below), race breakdown (B02001 002-008).
ACS_VARIABLES = [
    "NAME", "B01003_001E", "B19013_001E", "B01002_001E",
    "B17021_001E", "B17021_002E",
    "B02001_002E", "B02001_003E", "B02001_004E", "B02001_005E",
    "B02001_006E", "B02001_007E", "B02001_008E",
]


def record(url: str, dest: Path) -> None:
    manifest = {}
    if MANIFEST_PATH.exists():
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    manifest[str(dest.relative_to(RAW_DIR))] = {
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")


def fetch(url: str, dest: Path, force: bool, max_age_days: int) -> bool:
    """Download url to dest unless dest is fresh. Returns True if downloaded."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        age_days = (time.time() - dest.stat().st_mtime) / 86400
        if age_days < max_age_days:
            print(f"skip  {dest.relative_to(RAW_DIR)} ({age_days:.1f}d old)")
            return False
    tmp = dest.with_name(dest.name + ".part")
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        tmp.replace(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    print(f"fetch {dest.relative_to(RAW_DIR)}")
    record(url, dest)
    return True


def download_ourairports(force: bool, max_age_days: int) -> None:
    for name in ("airports.csv", "runways.csv"):
        fetch(f"{OURAIRPORTS_BASE}/{name}",
              RAW_DIR / "ourairports" / name, force, max_age_days)


def download_tracts(force: bool, max_age_days: int) -> None:
    for fips in STATE_FIPS:
        url = (f"https://www2.census.gov/geo/tiger/TIGER{TIGER_VINTAGE}/TRACT/"
               f"tl_{TIGER_VINTAGE}_{fips}_tract.zip")
        fetch(url, RAW_DIR / "census" / "tracts" / f"tl_{TIGER_VINTAGE}_{fips}_tract.zip",
              force, max_age_days)
        time.sleep(0.2)


def download_acs(force: bool, max_age_days: int) -> None:
    api_key = os.environ.get("CENSUS_API_KEY")
    if not api_key:
        sys.exit(
            "Census API requires a free key.\n"
            "  1. Get one at https://api.census.gov/data/key_signup.html\n"
            "  2. Set it:  export CENSUS_API_KEY=<your-key>   (Git Bash)\n"
        )
    base = f"https://api.census.gov/data/{ACS_VINTAGE}/acs/acs5"
    failures = []
    for fips in STATE_FIPS:
        dest = RAW_DIR / "acs" / f"acs5_{ACS_VINTAGE}_tracts_{fips}.csv"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not force:
            age_days = (time.time() - dest.stat().st_mtime) / 86400
            if age_days < max_age_days:
                print(f"skip  {dest.relative_to(RAW_DIR)} ({age_days:.1f}d old)")
                continue
        params = {
            "get": ",".join(ACS_VARIABLES),
            "for": "tract:*",
            "in": f"state:{fips}",
            "key": api_key,
        }
        rows = None
        for attempt in range(3):
            try:
                r = requests.get(base, params=params, headers=HEADERS, timeout=180)
                r.raise_for_status()
                rows = r.json()
                if not isinstance(rows, list) or len(rows) < 2:
                    raise ValueError(f"unexpected response: {str(rows)[:120]}")
                break
            except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
                rows = None
                wait = 2 ** attempt
                print(f"warn  state {fips}: attempt {attempt + 1}/3 failed ({e}) — retry in {wait}s")
                time.sleep(wait)
        if rows is None:
            failures.append(fips)
            continue
        with open(dest, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        print(f"fetch {dest.relative_to(RAW_DIR)} ({len(rows) - 1} tracts)")
        record(r.url, dest)
        time.sleep(0.2)
    if failures:
        sys.exit(f"ERROR: {len(failures)} state(s) failed after 3 attempts: "
                 f"{', '.join(failures)} — just re-run; fresh states are skipped")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", choices=["all", "ourairports", "tracts", "acs"])
    parser.add_argument("--force", action="store_true", help="re-download even if fresh")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS,
                        help="skip files newer than this (default %(default)s)")
    args = parser.parse_args()

    jobs = {"ourairports": download_ourairports, "tracts": download_tracts,
            "acs": download_acs}
    for name, job in jobs.items():
        if args.target in ("all", name):
            print(f"== {name} ==")
            job(args.force, args.max_age_days)


if __name__ == "__main__":
    main()
