# Project Playbook — The Quiet Map

A step-by-step log of how this project was built, written to be **reusable**:
each entry captures what we did here, the transferable essence (so the pattern
works for any data/GIS project), the exact commands, and the problems we hit
and how they were fixed.

**How to use this file:** read it top-to-bottom once to see the whole shape of
a project like this, then refer back per-step when building something new.
Each step's "Essence" is the part that transfers; the "How" is this project's
concrete instance.

**Convention going forward:** every new step gets appended as a new entry in
the same format — What / Essence / How / Troubleshooting.

---

## Step 0 — Scaffold the repo before writing real code

**What we did.** Created the full directory layout (`data/raw`, `data/processed`,
`src/`, `notebooks/`, `docs/`, `app/`, `reports/`), stub modules with
docstrings describing their planned job, `.gitignore`, and a README that already
contained the question, the approach, and a phased roadmap.

**Essence.** *Structure is a thinking tool.* Decide your pipeline stages
(acquire → prepare → analyze → present) and create one home per stage before
any code exists. Two rules pay off forever: **raw data is never edited**
(downloads land in `raw/`, all derived work in `processed/`), and **large data
never enters git** (`.gitignore` keeps the folders via `.gitkeep` but ignores
contents). A README written *before* the work doubles as your contract with
yourself — scope, non-goals, and "definition of done" per phase.

---

## Step 1 — Verify git state before assuming anything

**What we did.** Before the first push, checked `git status`, `git log --oneline`,
`git remote -v`. Turned out: remote configured, but **zero commits** — nothing
was ever pushed.

**Essence.** "Is my work backed up?" is a factual question you answer with
`git status` + `git log`, never an assumption. Check at the start of every
session; check before renaming, rebasing, or deleting anything.

---

## Step 2 — Rename the repo (remote + local)

**What we did.** Renamed `which_airport_cost` → `the-quiet-map` everywhere.

**How.**
- GitHub side, no `gh` CLI installed: used the REST API with the credential
  already stored in Git Credential Manager:
  ```bash
  CREDS=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill)
  # extract username/password from CREDS, then:
  curl -u "$USER:$TOKEN" -X PATCH \
    https://api.github.com/repos/<owner>/<old-name> \
    -d '{"name":"<new-name>"}'
  ```
  (token was piped between commands, never printed. Don't paste tokens into
  files or chat.)
- GitHub auto-redirects the old URL, so existing links don't break.
- Local remote updated: `git remote set-url origin https://github.com/<owner>/<new-name>.git`
- Local folder rename: blocked — Windows refused with
  `Device or resource busy` because the running terminal session's working
  directory was inside the folder. Fix: close the session, rename the folder
  (File Explorer or `mv`), reopen.

**Essence.** Rename early, before the first push — after push, renames mean
redirects and stale clones. Git does not care what the local folder is called,
so folder and repo names can diverge harmlessly. On Windows, a directory
cannot be renamed while *any* process is sitting in it — including your own
terminal; if a rename refuses, something is holding it open.

---

## Step 3 — Script your downloads (never click them)

**What we did.** Implemented `src/download.py`: one function per data source,
each fetching straight into `data/raw/`. The README's Step 1 download list
became code.

**How.**
- Verify every URL **before** scripting it:
  ```bash
  curl -sI -o /dev/null -w "%{http_code}" <url>   # want 200
  ```
  This caught two things immediately: the OurAirports CSVs live at
  `https://davidmegginson.github.io/ourairports-data/` (the CDN behind
  ourairports.com, not the .com page itself), and the hoped-for single
  national TIGER tract file is a 404 — so the script loops per-state zips
  (`tl_2023_<FIPS>_tract.zip`) instead.
- Core pattern in `fetch()`: skip files newer than N days (idempotent —
  re-running costs nothing), `--force` to refresh, download to `.part` then
  rename (no half files), record every fetch (URL + timestamp) in
  `data/raw/manifest.json`.

**Essence.** *Acquisition is code, not clicks.* Manual downloads are
non-reproducible, unlogged, and painful to refresh when a new data vintage
drops. The notebook pattern you may have seen (`!wget <url>` in a cell) is the
informal version of this — the maintainable version is a standalone script
with idempotency and a manifest. **Guessing URLs wastes time: HEAD-check them
first.** Expect "one convenient national file" to not exist; per-region loops
are the norm for boundary data.

**Troubleshooting.**
| Symptom | Cause | Fix |
|---|---|---|
| `404` on a "obvious" URL | Guessed path wrong | `curl -sI` the parent directory listing or check the site's docs for the real pattern |
| Half-written file after interrupted download | Writing directly to final name | Write to `.part`, rename when complete |

---

## Step 4 — Census API keys: free data still wants a key

**What we did.** Discovered the ACS API rejects keyless calls (HTTP 302 to a
"Missing Key" page — easy to misread as an empty response, since the 302 body
prints nothing). Got a free key, passed it via the `CENSUS_API_KEY` environment
variable; the script exits with instructions if it's missing.

**How.**
```bash
# Git Bash — one session only:
export CENSUS_API_KEY=<key>
# Permanent for your Windows user (new terminals only; setx can't touch the current one):
setx CENSUS_API_KEY "<key>"
# PowerShell equivalent:
$env:CENSUS_API_KEY="<key>"
```

**Essence.** *Public government data increasingly sits behind API keys anyway.*
Treat keys like passwords: environment variables only, never in notebooks,
never in committed files (`requirements.txt` gains no key-loading library that
would tempt anyone to commit a `.env`). Design scripts to **fail with
instructions** when the key is absent — future-you will thank present-you.

**Troubleshooting.**
| Symptom | Cause | Fix |
|---|---|---|
| Empty response from `curl` to api.census.gov | It's a 302 redirect to a "Missing Key" page | Re-test with `curl -sL` (follow redirects) to see the real answer; then get a key |
| Key "disappears" after closing terminal | `export` is per-session | `setx` for permanence, or re-export per session |

---

## Step 5 — Virtual environments: the fix for "No module named X"

**What we did.** First run of `python src/download.py acs` failed with
`ModuleNotFoundError: No module named 'requests'` — dependencies had never
been installed. The machine had several Pythons and the terminal found a bare
one. Fixed with the venv:
```bash
python -m venv .venv
source .venv/Scripts/activate   # Git Bash; prompt gains a (.venv) prefix
pip install -r requirements.txt
```
Activated the venv in every subsequent terminal session before running project
commands.

**Essence.** *Never install project packages into a system Python.* Multiple
Python installs (conda, python.org, Store) means `python` is a lottery; a venv
makes the project's environment explicit, isolated, and recreatable from
`requirements.txt` by anyone — including future-you on a new machine.
**Recurring rule:** `ModuleNotFoundError` right after a fresh clone = you
forgot to create or activate the venv. Windows path quirk: activation script
is at `.venv/Scripts/activate` (not `bin/`).

**Troubleshooting.**
| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` on first run of project code | venv never created/activated | Step 0 setup, then activate per terminal |
| `pip install geopandas` fails on Windows | GDAL/C binary wheels | `conda install -c conda-forge geopandas`, then pip for the rest |

---

## Step 6 — Batch downloads must self-heal and fail loudly

**What we did.** First ACS run completed silently with **46 of 49** states —
California, Connecticut, and Delaware had failed on transient API errors; the
script printed an `ERROR state ...` line (lost in the scroll) and moved on.
Fixed `download_acs` to: retry each state 3× with exponential backoff, validate
the response is actually data (not an error payload), and exit non-zero with a
loud summary if anything is still missing. Re-running then filled exactly the
3 gaps (the other 46 skipped as fresh) → 49/49.

Then **verified the data, not just the files**: tract counts matched known
figures (CA 9,129; CT 884; DE 262), and a sample row's race columns summed
exactly to its total population.

**Essence.** *Two separate habits here.* (1) Any batch fetch over a network
will partially fail, always — transient errors are the rule, not the
exception. Idempotency (skip what's fresh) + retries + a non-zero exit on
residual failure turns a silent gap into an obvious, self-healing one.
(2) **A download "succeeding" ≠ the data being right.** Cheap verification
beats confident analysis: row counts against known totals, internal
consistency checks (parts sum to whole), a couple of eyeball spot-checks.

**Troubleshooting.**
| Symptom | Cause | Fix |
|---|---|---|
| "It said done but files are missing" | Batch loop logged-and-continued | Make the script fail loudly; count outputs (`ls *.csv \| wc -l`) before trusting |
| Large-state query fails, small ones fine | Response size / timeout on big queries | Retry with backoff; if persistent, split the query (by county) |

---

## Step 7 — Log sources twice: human log + machine manifest

**What we did.** `docs/data-sources.md` records source, what it provides,
access terms, and fetch date (human-curated); `data/raw/manifest.json` records
file → URL → fetch timestamp automatically on every download. Vintage
consistency is tracked explicitly (TIGER 2023 ↔ ACS 2022, bumped together).

**Essence.** *Data lineage is not optional in anything you'll revisit.*
"Where did this file come from?" must be answerable in one glance, months
later. A manifest generated by the download script is effortless; the human
log adds what code can't (license quirks, access notes). Boundary and
demographic vintages must match or every downstream join is quietly wrong —
tie the vintage year to one constant in code.

---

## Running glossary of symptoms → fixes

Quick index across all steps (details live in the entries above):

- `ModuleNotFoundError` → venv not created/activated (Step 5)
- `Device or resource busy` on rename/move → a process (often your own
  terminal) has the folder open; close it (Step 2)
- Empty response from an API → probably a 302; re-test with `curl -sL` (Step 4)
- 404 on a guessed download URL → HEAD-check URLs before scripting (Step 3)
- Batch job "done" but incomplete → needs idempotency + loud failure (Step 6)
- Data looks fine but isn't → verify counts/consistency, never just existence (Step 6)
- `LF will be replaced by CRLF` warnings from git on Windows → harmless line-ending normalization (Step 2, commit)

---

## Step 8 — The prepare stage: raw downloads → analysis-ready layers

**What we did.** Built `src/prepare.py`, the second pipeline stage: merges the
49 TIGER shapefiles, joins ACS demographics on GEOID, filters OurAirports to
continental-U.S. large/medium airports with scheduled service, builds runway
lines from endpoint coordinates, projects **everything** to Albers Equal Area
(EPSG:5070), repairs geometries, and writes GeoParquet to `data/processed/`.
The contours stage scans `data/raw/contours/<airport>/` for files and
processes them when present — and skips cleanly when not, so the pipeline is
ready before the manual data exists.

Results: tracts 83,777 rows with a **100% ACS join**; airports 781; runways
1,580; total population across tracts ≈ 329M (matches the 2022 lower-48+DC
estimate — a free sanity check). Bugs hit and fixed:

- `KeyError: "['geometry'] not in index"` — `keep` selected a `geometry`
  column from the plain DataFrame while also passing `geometry=...` to the
  GeoDataFrame constructor. A GeoDataFrame's geometry passed separately is
  *not* a column of the source DataFrame. Select attributes, pass geometry.
- `�` in printed output on Windows — a non-ASCII em dash in a `print()`.
  Console encoding on Windows mangles it. **Keep printed/logged output ASCII;
  non-ASCII is fine in docstrings and Markdown.**

**Essence.** *The prepare stage is the contract between messy reality and
clean analysis.* Four rules transfer to any GIS project: (1) **one CRS,
chosen for the math you plan to do** — area-preserving Albers for
population/distance work, not the GPS default of degrees; mixing CRSs is the
classic silent GIS bug. (2) **Always report join coverage** — print the
percentage of rows that matched (ours printed 100.0%; if it prints 60%, stop
and find the key mismatch *now*, not after three more stages). (3) At tens of
thousands of polygons, **GeoParquet beats GeoJSON by an order of magnitude**
in size and load time — pick the boring binary format for processed layers.
(4) Build stages that **degrade gracefully on missing inputs** (skip with a
note) so a pipeline runs end-to-end before every dataset has arrived.

**Troubleshooting.**
| Symptom | Cause | Fix |
|---|---|---|
| Join coverage < 100% | Key type mismatch (int vs str GEOID), vintage mismatch, leading zeros eaten | Read keys as strings (`dtype=str`), rebuild GEOID from parts, check vintages match |
| Map distances/areas look 2× off | Mixed CRSs or degrees treated as meters | Project everything to one CRS explicitly; never assume a file's CRS |
| `KeyError: 'geometry'` | Selecting a geometry column that lives outside the DataFrame | Pass geometry to the constructor; select attributes only |
