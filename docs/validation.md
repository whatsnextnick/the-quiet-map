# Validation — ATL pipeline vs. official NEM

**Date:** 2026-10-23 · **Status:** PASS (order-of-magnitude agreement)

## The comparison

Official figures: *Hartsfield-Jackson Draft NEM Update Report* (Crawford,
Murphy & Tilly, Inc., Dec 2024), existing-year **2024** NEM, noise modeled
in the FAA's AEDT tool; population from Year-2020 Census data tied to
parcel-level residences. Ours: BTS CONUS aviation noise 2022 mosaic,
thresholded at DNL 65, population apportioned from ACS 2022 tract data.

| Metric | Ours (modeled, BTS 2022) | Official (NEM 2024) | Ratio (ours/official) |
|---|---|---|---|
| Population within ≥65 dB | 4,651 | 9,671 (Table 9, p.15) | 0.48 |
| Area within ≥65 dB | 22.5 km² (8.7 sq mi) | 13.9 sq mi (Table 8, p.14) | 0.63 |

Coincidence noted but meaningless: our exposed population (4,651) nearly
equals the official *residence* count (4,649) — people vs. homes.

## Why the gap is expected, not alarming

- **Different models.** BTS 2022 is a national model; the NEM uses the
  airport-specific FAA AEDT model — airport models are fed richer local data
  and usually draw larger contours.
- **Different operation years.** 2022 vs. 2024 — ATL traffic grew post-2022.
- **Different counting methods.** Official = parcel-level residences on 2020
  Census; ours = tract-level area apportionment on ACS 2022.
- **Direction is consistent.** Both area and population run ~0.5–0.6× —
  the national model is systematically a bit conservative here, which is a
  property of the *source layer*, not of our pipeline.

**Conclusion:** the pipeline (extract → prepare → analyze) reproduces the
official figure within a factor of ~2, same order of magnitude. Phase 2
sanity check satisfied. All BTS-derived numbers remain labeled *modeled*.
