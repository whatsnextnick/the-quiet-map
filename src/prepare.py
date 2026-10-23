"""Build analysis-ready layers in data/processed/ from data/raw/.

Stages (run everything with `python src/prepare.py`, or one stage by name):

    tracts    merge the 49 TIGER tract shapefiles, join ACS 5-year
              demographics on GEOID, repair geometries
    airports  OurAirports rows filtered to continental-U.S. large/medium
              airports with scheduled service
    runways   runways of those airports, as LE->HE endpoint lines
    contours  DNL contours dropped by hand into data/raw/contours/<airport>/
              (.shp/.zip/.geojson/.gpkg all read) — skipped with a note if
              none are present yet

Everything is projected to Albers Equal Area (EPSG:5070): area-preserving,
the right basis for distance bands and exposure math alike. Outputs are
GeoParquet — far smaller and faster than GeoJSON at this row count; read
back with geopandas.read_parquet, open in QGIS, or serve to folium later.
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROC_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
CRS = "EPSG:5070"  # Albers Equal Area (CONUS)

# Census codes for suppressed estimates — treated as missing, not as numbers.
ACS_SUPPRESSED = {"-666666666", "-999999999"}

# ACS 5-year variable -> friendly column name.
ACS_COLUMNS = {
    "B01003_001E": "total_pop",
    "B19013_001E": "median_income",
    "B01002_001E": "median_age",
    "B17021_001E": "poverty_universe",
    "B17021_002E": "poverty_count",
    "B02001_002E": "race_white",
    "B02001_003E": "race_black",
    "B02001_004E": "race_aian",
    "B02001_005E": "race_asian",
    "B02001_006E": "race_nhpi",
    "B02001_007E": "race_other",
    "B02001_008E": "race_two_plus",
}

# Out-of-scope regions in OurAirports' iso_region values.
EXCLUDED_REGIONS = {"US-AK", "US-HI", "US-PR", "US-VI", "US-GU", "US-AS", "US-MP"}


def load_acs() -> pd.DataFrame:
    files = sorted((RAW_DIR / "acs").glob("acs5_*_tracts_*.csv"))
    if not files:
        sys.exit("no ACS files in data/raw/acs — run: python src/download.py acs")
    acs = pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)
    acs["GEOID"] = acs["state"] + acs["county"] + acs["tract"]
    acs = acs[["GEOID", *ACS_COLUMNS]].rename(columns=ACS_COLUMNS)
    for col in ACS_COLUMNS.values():
        acs[col] = pd.to_numeric(acs[col].replace(ACS_SUPPRESSED, None),
                                 errors="coerce")
    return acs


def load_airports_raw() -> gpd.GeoDataFrame:
    df = pd.read_csv(RAW_DIR / "ourairports" / "airports.csv")
    df = df[(df["iso_country"] == "US")
            & (df["type"].isin(["large_airport", "medium_airport"]))
            & (df["iata_code"].fillna("").str.strip() != "")
            & (~df["iso_region"].isin(EXCLUDED_REGIONS))]
    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude_deg"], df["latitude_deg"]),
        crs="EPSG:4326",
    )


def finish(gdf: gpd.GeoDataFrame, name: str) -> None:
    if not gdf.geometry.is_valid.all():
        gdf = gdf.set_geometry(gdf.geometry.make_valid())
    gdf = gdf.to_crs(CRS)
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    out = PROC_DIR / f"{name}.parquet"
    gdf.to_parquet(out)
    print(f"wrote {out.relative_to(PROC_DIR.parent)} "
          f"({len(gdf)} rows, {len(gdf.columns) - 1} attribute cols)")


def prepare_tracts() -> None:
    zips = sorted((RAW_DIR / "census" / "tracts").glob("*.zip"))
    if not zips:
        sys.exit("no TIGER zips in data/raw/census/tracts — run: python src/download.py tracts")
    first = gpd.read_file(zips[0])
    tracts = gpd.GeoDataFrame(
        pd.concat([first] + [gpd.read_file(z) for z in zips[1:]], ignore_index=True),
        crs=first.crs,
    )
    tracts = tracts[["GEOID", "NAME", "ALAND", "AWATER", "geometry"]].copy()
    tracts["GEOID"] = tracts["GEOID"].astype(str)
    tracts = tracts.merge(load_acs(), on="GEOID", how="left")
    n = tracts["total_pop"].notna().sum()
    print(f"tracts: demographics joined for {n}/{len(tracts)} "
          f"({n / len(tracts):.1%})")
    finish(tracts, "tracts")


def prepare_airports() -> None:
    gdf = load_airports_raw()
    keep = ["ident", "type", "name", "iata_code", "local_code", "iso_region",
            "municipality", "elevation_ft", "scheduled_service", "geometry"]
    finish(gdf[keep], "airports")


def prepare_runways() -> None:
    airports = load_airports_raw()
    rwy = pd.read_csv(RAW_DIR / "ourairports" / "runways.csv")
    rwy = rwy[(rwy["airport_ident"].isin(airports["ident"]))
              & (rwy["closed"] == 0)]
    have = (rwy[["le_latitude_deg", "le_longitude_deg",
                 "he_latitude_deg", "he_longitude_deg"]].notna().all(axis=1))
    skipped = len(rwy) - have.sum()
    if skipped:
        print(f"runways: dropped {skipped} without endpoint coordinates")
    rwy = rwy[have]
    geom = [LineString([(le_lon, le_lat), (he_lon, he_lat)])
            for le_lon, le_lat, he_lon, he_lat in zip(
                rwy["le_longitude_deg"], rwy["le_latitude_deg"],
                rwy["he_longitude_deg"], rwy["he_latitude_deg"])]
    keep = ["airport_ident", "length_ft", "width_ft", "surface", "lighted"]
    gdf = gpd.GeoDataFrame(rwy[keep].reset_index(drop=True),
                           geometry=geom, crs="EPSG:4326")
    finish(gdf, "runways")


def prepare_contours() -> None:
    folder = RAW_DIR / "contours"
    if not folder.exists():
        print("contours: data/raw/contours/ doesn't exist yet -- drop pilot "
              "airport contours there, then re-run")
        return
    files = [p for pattern in ("*.shp", "*.zip", "*.geojson", "*.json", "*.gpkg")
             for p in folder.rglob(pattern)]
    if not files:
        print("contours: nothing in data/raw/contours/ yet -- skipped")
        return
    frames = []
    for f in files:
        g = gpd.read_file(f)
        g["airport"] = f.parent.name.upper()
        frames.append(g)
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True),
                           crs=frames[0].crs)
    finish(gdf, "contours")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", default="all",
                        choices=["all", "tracts", "airports", "runways", "contours"])
    args = parser.parse_args()

    jobs = {"tracts": prepare_tracts, "airports": prepare_airports,
            "runways": prepare_runways, "contours": prepare_contours}
    for name, job in jobs.items():
        if args.target in ("all", name):
            print(f"== {name} ==")
            job()


if __name__ == "__main__":
    main()
