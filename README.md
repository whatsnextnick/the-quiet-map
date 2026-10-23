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

**Where these commands run:** in a terminal, from the project root folder —
*not* in a Jupyter notebook. On Windows: right-click inside the project folder
in File Explorer → **Git Bash Here** (or open Git Bash and
`cd ~/OneDrive/Desktop/personal_projects/the-quiet-map`). In VS Code:
**Terminal → New Terminal**. Notebooks under `notebooks/` are for exploration
only; everything in `src/` is run from the shell as `python src/<file>.py`.

**First time here? Do Step 0 below first.** If a `src/download.py` command
fails with `ModuleNotFoundError: No module named 'requests'`, the dependencies
were never installed — create the venv and run `pip install -r requirements.txt`
as shown in Step 0, then try again. You only set this up once, but you must
`source .venv/Scripts/activate` in every new terminal before running project
commands.

Everything lands in `data/raw/` and gets logged in `docs/data-sources.md`
(source, URL, license, fetch date). Raw files are never edited.

Downloading is **scripted, not manual** — `python src/download.py all` fetches
items 1–3 (set a free `CENSUS_API_KEY` first for item 3), skips files that are
already fresh, and records every fetch in `data/raw/manifest.json`. Items 4–5
have no reliable programmatic source and stay manual. This keeps the project
reproducible: anyone can re-run the exact same acquisition, and refreshing to
a new data vintage is a flag change, not an afternoon of clicks.

1. **Airport + runway reference — OurAirports** *(scripted)*. Mirrors FAA
   5010, easiest to fetch: `airports.csv` and `runways.csv`. Filter to
   continental-U.S. large/medium airports during prep.
   → `data/raw/ourairports/`
2. **Census tract geometries — TIGER/Line** *(scripted)*. Per-state tract
   shapefiles for the lower 48 + DC, one vintage
   (`src/download.py` → `TIGER_VINTAGE`). → `data/raw/census/tracts/`
3. **ACS 5-year demographic tables** *(scripted, needs `CENSUS_API_KEY`)*.
   Tables: `B01003` (total population), `B19013` (median household income),
   `B01002` (median age), `B02001` (race), `B17021` (poverty). Matched to
   the same vintage as TIGER (`ACS_VINTAGE`). → `data/raw/acs/`

   **How to run it** (in Git Bash, from the project root):

   ```bash
   # one-time setup: put your key (from
   # https://api.census.gov/data/key_signup.html) into an environment variable
   export CENSUS_API_KEY=put-your-key-here        # no quotes needed
   echo $CENSUS_API_KEY                            # sanity check — must print the key

   # then fetch all 49 states (fast: a few dozen small API calls)
   python src/download.py acs
   ```

   Expect ~49 lines of `fetch acs\acs5_2022_tracts_XX.csv (NNNN tracts)` and
   one CSV per state in `data/raw/acs/`. The `export` lasts only for that
   terminal session — to make the key permanent, run once
   `setx CENSUS_API_KEY "put-your-key-here"` and open a new terminal
   (`setx` does not affect the terminal you run it in). Never paste the key
   into a notebook or any file that could get committed — `src/download.py`
   reads it from the environment only. PowerShell instead of Git Bash?
   Use `$env:CENSUS_API_KEY="put-your-key-here"`.
4. **Noise contours (DNL 65 dB)** *(scripted — national layer beats
   per-airport hunts)*: the BTS "CONUS Aviation Noise 2022" mosaic (Esri
   File Geodatabase, 30m modeled DNL rasters, one per state) covers every
   airport at once. `python src/extract_contours.py ATL` crops the right
   state raster to a box around the airport, thresholds at 65 dB,
   polygonizes, and writes `data/raw/contours/atl/`. Values are **modeled**,
   not a published NEM — labeled as modeled everywhere. Download the gdb
   once, set `BTS_NOISE_GDB` to its path. Airport-published NEMs, where
   they exist, serve as Phase-2 validation sources instead.
   → `data/raw/contours/<airport>/`
5. **Optional cross-check — EPA EJScreen** *(manual)*: environmental-justice
   indices from <https://www.epa.gov/ejscreen>, useful for validating that
   exposed tracts score high on EJ measures. → `data/raw/ejscreen/`

### Step 2 — Log every source

Fill in the `Fetched` column and any access notes in `docs/data-sources.md` the
day each file lands. If a source needs an attribution line, record it there.

### Step 3 — Build order

Implement against the stubs already in `src/`, one milestone at a time:

1. `src/download.py` — ✅ already implements Step 1 (sources 1–3) with
   freshness skips and a fetch manifest. To refresh a stale file: `--force`.
   To move to a new data vintage: bump `TIGER_VINTAGE` and `ACS_VINTAGE`
   together (they must match) and re-run.
2. `src/prepare.py` — ✅ built. Merges the 49 TIGER shapefiles, joins ACS
   demographics on GEOID, filters airports/runways to continental U.S.,
   projects everything to Albers Equal Area (EPSG:5070), repairs geometries,
   and writes GeoParquet to `data/processed/` (`tracts.parquet`,
   `airports.parquet`, `runways.parquet`, `contours.parquet` when contour
   files exist). Run one stage, e.g. `python src/prepare.py tracts`, or all.
3. ✅ **Done — ATL end to end.** `src/analyze.py` fractionally apportions
   tract populations into each airport's DNL 65 zone and computes equity
   metrics (exposed population per group, disparity ratios, poverty and
   age inside vs. outside). ATL's first real numbers: ~4,700 people in the
   zone; Black residents 1.33× as likely to be exposed; poverty rate 21.5%
   inside vs. 15.9% nearby. Outputs: `exposure_summary.csv`,
   `exposure_by_group.csv`. Next: scale contours to more airports, then
   validate against a published NEM figure (Phase 2 check).

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
│   ├── extract_contours.py  # airport DNL contours from the BTS national mosaic
│   ├── analyze.py        # spatial joins + equity metrics
│   └── map.py            # interactive map generation
├── app/
│   └── streamlit_app.py  # "The Quiet Map" explorer (Phase 4)
├── reports/
│   └── figures/          # generated maps + charts
└── docs/
    ├── data-sources.md   # source log: URL, license, date fetched
    └── playbook.md       # step-by-step build log w/ transferable lessons + troubleshooting
```

## Roadmap

- [ ] **Phase 1 — Data.** Download airport/runway reference data + ACS tracts.
      Log every source in `docs/data-sources.md`. Acquire contours for a pilot
      set (start with 3–5 major airports).
- [x] **Phase 2 — Overlay.** Spatial join tracts × contours; sanity-check against
      a published exposure figure for one airport. ✅ Validated vs ATL's
      2024 NEM: same order of magnitude (~0.5–0.6×), see docs/validation.md.
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
