# Which Airport Cost

**Mapping who lives under America's airport noise — and how unequally that burden is shared.**

Every flight traces back to a community that hears it. The FAA publishes noise
exposure contours around airports; the Census publishes who lives where. Join the
two and a hidden story surfaces: which neighborhoods absorb aviation's sound,
measured against income, race, and age — airport by airport.

## The question

> Of the people living inside U.S. airport noise contours, who are they — and how
> evenly is that burden shared across the country?

## Why this project

Part of a series of builds in the aviation-data space. The point: public datasets
(FAA, Census, EPA) already contain an untold operations-and-community story — it
just takes GIS joins and a fairness lens to surface it. Aviation's data world,
explored from the community side of the fence.

## Project scope

**In scope**

- Continental-U.S. airports with published (or modelable) noise exposure data
- Tract-level demographics from the ACS 5-year estimates: total population,
  median household income, race/ethnicity breakdown, median age, poverty status
- An exposure overlay: DNL 65 dB contours (published) or modeled distance
  bands around runways (fallback, always labeled as modeled)
- Per-airport and national equity metrics: who lives in the noise, compared to
  who doesn't
- An interactive map explorer (Streamlit + Folium) and a one-page story brief

**Out of scope (for now)**

- Regulatory noise analysis — no NEPA, FAR Part 150, or dB modeling claims
- Real-time or historical flight-track noise modeling
- Global coverage; airports outside the U.S.
- Building-level or address-level exposure

## Approach at a glance

1. **Acquire** — airport + runway locations (OurAirports / FAA 5010), Census
   tract geometries + ACS demographics, and noise contours for a pilot set of
   airports.
2. **Overlay** — published DNL 65 dB contours onto census tracts; fall back to
   modeled distance bands around runways where contours aren't published.
3. **Quantify** — exposed population by demographic group per airport; disparity
   metrics; a national rollup.
4. **Map** — an interactive explorer covering every airport in the dataset.
5. **Tell** — one page, a handful of airports, real numbers.

## First steps

### Step 0 — Environment

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

If `geopandas` gives you GDAL trouble on Windows:
`conda install -c conda-forge geopandas` instead.

### Step 1 — What to download, in order

Everything lands in `data/raw/` and gets logged in `docs/data-sources.md`
(source, URL, license, fetch date). Raw files are never edited.

1. **Airport + runway reference — OurAirports** (mirrors FAA 5010, easiest to
   fetch): `airports.csv` and `runways.csv` from
   <https://ourairports.com/data/>. Filter to continental-U.S. large/medium
   airports during prep. → `data/raw/ourairports/`
2. **Census tract geometries — TIGER/Line**: national tract shapefile
   (latest year) from the Census Bureau's FTP site, e.g.
   <https://www2.census.gov/geo/tiger/TIGER2023/TRACT/>. → `data/raw/census/`
3. **ACS 5-year demographic tables**: via the free Census API (get a key at
   <https://api.census.gov/data/key_signup.html>) or CSV download. Tables to
   start: `B01003` (total population), `B19013` (median household income),
   `B01002` (median age), `B02001` (race), `B17021` (poverty). Match to the
   same vintage as the TIGER layer. → `data/raw/acs/`
4. **Pilot noise contours (DNL 65 dB)**: pick 3–5 airports with published
   Noise Exposure Maps — good candidates: ATL, DFW, LAX, ORD, PHX. Sources vary
   by airport: airport authority GIS portals, state DOT open-data sites, or
   FAA NEM filings. Expect a mix of shapefiles and PDFs (shapefiles only are
   usable; note PDF-only airports in the log). → `data/raw/contours/<airport>/`
5. **Optional cross-check — EPA EJScreen**: environmental-justice indices from
   <https://www.epa.gov/ejscreen>, useful for validating that exposed tracts
   score high on EJ measures. → `data/raw/ejscreen/`

### Step 2 — Log every source

Fill in the `Fetched` column and any access notes in `docs/data-sources.md` the
day each file lands. If a source needs an attribution line, record it there.

### Step 3 — Build order

Implement against the stubs already in `src/`, one milestone at a time:

1. `src/download.py` — one function per source from Step 1; make downloads
   re-runnable (skip if file exists and is newer than N days).
2. `src/prepare.py` — load raw layers, project everything to Albers Equal Area
   (EPSG:5070), repair invalid geometries, write analysis-ready layers to
   `data/processed/` (`tracts.geojson`, `airports.geojson`, `runways.geojson`,
   `contours.geojson`).
3. First milestone to aim for: **one airport, end to end** — overlay ATL's
   contour on tracts, pull the demographics of tracts inside the DNL 65 line,
   print the number. That proves the whole pipeline before scaling.

### Definition of done (Phase 1)

- All Step 1 sources downloaded and logged
- `data/processed/` contains clean, single-CRS layers
- The ATL end-to-end check runs and matches a published exposure figure
  within a sane margin

## Repo structure

```
which_airport_cost/
├── README.md
├── requirements.txt
├── data/
│   ├── raw/              # downloaded source files — never edit
│   └── processed/        # cleaned / derived datasets
├── notebooks/            # exploratory work, one question per notebook
├── src/
│   ├── download.py       # fetch each public dataset into data/raw/
│   ├── prepare.py        # normalize CRS, clean geometries
│   ├── analyze.py        # spatial joins + equity metrics
│   └── map.py            # interactive map generation
├── app/
│   └── streamlit_app.py  # "The Quiet Map" explorer (Phase 4)
├── reports/
│   └── figures/          # generated maps + charts
└── docs/
    └── data-sources.md   # source log: URL, license, date fetched
```

## Roadmap

- [ ] **Phase 1 — Data.** Download airport/runway reference data + ACS tracts.
      Log every source in `docs/data-sources.md`. Acquire contours for a pilot
      set (start with 3–5 major airports).
- [ ] **Phase 2 — Overlay.** Spatial join tracts × contours; sanity-check against
      a published exposure figure for one airport.
- [ ] **Phase 3 — Equity.** Exposed population by demographic group; disparity
      index; national summary.
- [ ] **Phase 4 — The map.** Folium/Streamlit explorer: airport → contour →
      exposed community.
- [ ] **Phase 5 — Story.** One-page brief + short public write-up.

## Honest constraints

- Published DNL contours exist only for airports that have completed noise
  studies, so coverage is patchy. Modeled distance bands are a proxy and will be
  labeled as modeled wherever they're used.
- Tract-level demographics are ACS 5-year estimates — report margins of error
  where they matter.
- Census tract boundaries change between vintages; keep TIGER and ACS on the
  same year or document the mismatch.
- This is a portfolio exploration, not a regulatory noise analysis. No
  NEPA / FAR Part 150 claims.
