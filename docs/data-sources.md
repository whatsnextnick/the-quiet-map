# Data Sources

Log every dataset here the day it's downloaded: what it provides, where it came
from, access terms, and the fetch date.

| Source | What it provides | Access | Fetched |
|---|---|---|---|
| [OurAirports](https://ourairports.com/data/) | Airport + runway locations (mirrors FAA 5010) | Public CSV | 2026-10-23 |
| [FAA 5010](https://www.faa.gov/airports/airport_safety/airportdata_5010/) | Authoritative U.S. airport / runway reference data | Public | — |
| U.S. Census TIGER/Line (2023) | Tract geometries, lower 48 + DC (per-state zips) | Public FTP | 2026-10-23 |
| U.S. Census ACS 5-year (2022) | Tract demographics: B01003, B19013, B01002, B02001, B17021 | Free API key | 2026-10-23 |
| Airport Noise Exposure Maps (NEM) | Published DNL 65 dB contours | Varies by airport / state | — |
| [BTS CONUS Aviation Noise 2022](https://data.bts.gov/) | National MODELED aviation noise raster (30m, per state) — DNL surface, extracted per airport by `src/extract_contours.py` | Public | 2026-10-23 |
| [ATL Draft NEM Update Report](https://www.atl.com/community/planningnoiseenvironmental/) | Official population (9,671) & area (13.9 sq mi) within DNL 65+, 2024 existing-year NEM — used to validate our pipeline (see docs/validation.md) | Public | 2026-10-23 |
| [EPA EJScreen](https://www.epa.gov/ejscreen) | Environmental-justice indices (optional cross-check) | Public | — |

**Notes**

- Contour coverage is patchy — only airports that have completed noise studies
  publish them. Where missing, modeled distance bands around runways are a
  documented fallback, always labeled as modeled.
