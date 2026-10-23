# Data Sources

Log every dataset here the day it's downloaded: what it provides, where it came
from, access terms, and the fetch date.

| Source | What it provides | Access | Fetched |
|---|---|---|---|
| [OurAirports](https://ourairports.com/data/) | Airport + runway locations (mirrors FAA 5010) | Public CSV | — |
| [FAA 5010](https://www.faa.gov/airports/airport_safety/airportdata_5010/) | Authoritative U.S. airport / runway reference data | Public | — |
| U.S. Census ACS 5-year | Tract geometries + demographic tables | Free API key or CSV download | — |
| Airport Noise Exposure Maps (NEM) | Published DNL 65 dB contours | Varies by airport / state | — |
| [EPA EJScreen](https://www.epa.gov/ejscreen) | Environmental-justice indices (optional cross-check) | Public | — |

**Notes**

- Contour coverage is patchy — only airports that have completed noise studies
  publish them. Where missing, modeled distance bands around runways are a
  documented fallback, always labeled as modeled.
