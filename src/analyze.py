"""Quantify who lives inside each airport's DNL 65 dB zone.

For every airport in processed/contours.parquet, estimate how many people
live inside its noise zone and break that down by demographic group.

Method -- fractional apportionment (area weighting): a tract only partially
inside the zone contributes only part of its people, in proportion to the
share of its own area that falls inside. Assumes people are spread evenly
within a tract; the standard tract-level approximation. Tracts entirely
outside the zone contribute nothing.

Metrics per airport:
- exposed population (total + per group), fractionally apportioned
- each group's disparity ratio: share of the exposed vs. share of the
  reference population (all tracts touching the zone; ratio 2.0 = twice
  as likely to live in the noise)
- poverty rate and median age inside vs. outside the zone

Usage:
    python src/analyze.py            # every airport in contours.parquet
    python src/analyze.py ATL        # one airport

Writes exposure_summary.csv (one row per airport) and
exposure_by_group.csv (one row per airport x group) to data/processed/.
"""

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

PROC_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

GROUPS = {
    "race_white": "White",
    "race_black": "Black / African American",
    "race_aian": "American Indian / Alaska Native",
    "race_asian": "Asian",
    "race_nhpi": "Native Hawaiian / Pacific Islander",
    "race_other": "Other race",
    "race_two_plus": "Two or more races",
}


def apportion(tracts: gpd.GeoDataFrame, zone) -> gpd.GeoDataFrame:
    """Tracts touching the zone, each with its inside-area fraction."""
    hits = tracts[tracts.intersects(zone)].copy()
    frac = (hits.geometry.intersection(zone).area / hits.geometry.area).clip(0, 1)
    hits["frac_inside"] = frac
    return hits


def _rate(num: float, den: float):
    return round(num / den, 4) if den else None


def summarize(iata: str, zone, tracts: gpd.GeoDataFrame):
    hits = apportion(tracts, zone)
    if hits.empty:
        return None, []
    w = hits["frac_inside"]
    pop = hits["total_pop"].fillna(0)

    exposed_pop = float((pop * w).sum())
    ref_pop = float(pop.sum())
    if ref_pop == 0:
        # zone touches only unpopulated land (airport/water "9800" tracts)
        return None, []
    outside_pop = ref_pop - exposed_pop
    summary = {
        "airport": iata,
        "zone_area_km2": round(zone.area / 1e6, 1),
        "n_tracts_touching": len(hits),
        "exposed_pop": round(exposed_pop),
        "exposed_share_of_reference": _rate(exposed_pop, ref_pop),
    }

    # poverty + age inside vs. the rest of the touching tracts
    pov = hits["poverty_count"].fillna(0)
    exposed_pov = float((pov * w).sum())
    summary["poverty_rate_inside"] = _rate(exposed_pov, exposed_pop)
    summary["poverty_rate_outside"] = _rate(
        float(pov.sum()) - exposed_pov, outside_pop)
    age = hits["median_age"]
    if exposed_pop:
        summary["median_age_inside"] = round(
            float((age * pop * w).sum()) / exposed_pop, 1)
    else:
        summary["median_age_inside"] = None
    summary["median_age_outside"] = (round(
        float((age * pop * (1 - w)).sum()) / outside_pop, 1)
        if outside_pop else None)

    group_rows = []
    for col, label in GROUPS.items():
        g = hits[col].fillna(0)
        exposed_g = float((g * w).sum())
        share_exposed = exposed_g / exposed_pop if exposed_pop else 0.0
        share_ref = float(g.sum()) / ref_pop
        group_rows.append({
            "airport": iata,
            "group": label,
            "exposed": round(exposed_g),
            "share_of_exposed": round(share_exposed, 4),
            "share_of_reference": round(share_ref, 4),
            "disparity_ratio": round(share_exposed / share_ref, 2)
            if share_ref > 0 else None,
        })
    return summary, group_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iata", nargs="?", help="one airport, e.g. ATL")
    args = parser.parse_args()

    contours = gpd.read_parquet(PROC_DIR / "contours.parquet")
    tracts = gpd.read_parquet(PROC_DIR / "tracts.parquet")
    if args.iata:
        contours = contours[contours["airport"] == args.iata.upper()]
        if contours.empty:
            raise SystemExit(f"{args.iata.upper()} not in contours.parquet — "
                             f"run src/extract_contours.py first")

    summaries, all_groups = [], []
    for _, c in contours.iterrows():
        s, g = summarize(c["airport"], c.geometry, tracts)
        if s is None:
            print(f"{c['airport']}: no populated tracts touch the zone")
            continue
        summaries.append(s)
        all_groups.extend(g)
        print(f"\n{c['airport']}: {s['exposed_pop']:,.0f} people inside "
              f"{s['zone_area_km2']} km^2 zone "
              f"({s['n_tracts_touching']} tracts touch it)")
        print(f"  poverty rate inside {s['poverty_rate_inside']:.1%} vs "
              f"outside {s['poverty_rate_outside']:.1%} | "
              f"median age {s['median_age_inside']} vs "
              f"{s['median_age_outside']}")
        for row in g:
            print(f"  {row['group']:<30} exposed {row['exposed']:>8,.0f}  "
                  f"share of exposed {row['share_of_exposed']:>7.1%}  "
                  f"share nearby {row['share_of_reference']:>7.1%}  "
                  f"ratio {row['disparity_ratio']}")

    if summaries:
        pd.DataFrame(summaries).to_csv(PROC_DIR / "exposure_summary.csv",
                                       index=False)
        pd.DataFrame(all_groups).to_csv(PROC_DIR / "exposure_by_group.csv",
                                        index=False)
        print(f"\nwrote exposure_summary.csv, exposure_by_group.csv "
              f"({len(summaries)} airport(s))")

    if len(contours) > 1:
        # National rollup: union ALL zones first so tracts under two
        # airports' zones are counted once, then apportion once.
        nat_s, nat_g = summarize("NATIONAL", contours.union_all(), tracts)
        print(f"\n== NATIONAL (union of {len(contours)} zones; each tract "
              f"counted once) ==")
        print(f"{nat_s['exposed_pop']:,.0f} people inside the union of all "
              f"zones ({nat_s['zone_area_km2']} km^2)")
        print(f"  poverty rate inside {nat_s['poverty_rate_inside']:.1%} vs "
              f"outside {nat_s['poverty_rate_outside']:.1%} | "
              f"median age {nat_s['median_age_inside']} vs "
              f"{nat_s['median_age_outside']}")
        for row in nat_g:
            print(f"  {row['group']:<30} exposed {row['exposed']:>8,.0f}  "
                  f"ratio {row['disparity_ratio']}")
        pd.DataFrame([nat_s]).to_csv(PROC_DIR / "exposure_national.csv",
                                     index=False)
        print("wrote exposure_national.csv")


if __name__ == "__main__":
    main()
