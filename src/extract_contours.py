"""Extract airport DNL contours from the BTS national noise mosaic.

The BTS "CONUS Aviation Noise" mosaic (an Esri File Geodatabase of 30m
rasters, one per state) stores modeled DNL values per cell. This tool crops
the relevant state raster to a square around an airport, thresholds it at
the DNL cutoff, polygonizes the result, and writes a GeoJSON into
data/raw/contours/<iata>/ — which src/prepare.py then picks up.

Usage (single airport):
    export BTS_NOISE_GDB=/path/to/CONUS_aviation_noise.gdb
    python src/extract_contours.py ATL
    python src/extract_contours.py ATL --radius-km 60 --threshold 65

Usage (batch — every airport in processed/airports.parquet, state rasters
opened once each, summary CSV written to data/raw/contours/):
    python src/extract_contours.py

NOTE: BTS noise values are MODELED (national 2022 model), not a published
airport Noise Exposure Map. Everything derived from them must be labeled
as modeled. An airport with no cells >= threshold within the box gets no
GeoJSON — in batch mode that is recorded as a result, not an error.
"""

import argparse
import os
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.features import shapes
from rasterio.windows import from_bounds
from shapely.geometry import shape
from shapely.ops import unary_union

PROC_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
CONTOURS_DIR = RAW_DIR / "contours"


def extract_from(ds: rasterio.DatasetReader, airport, radius_km: float,
                 threshold: float):
    """Contour GeoDataFrame for one airport from an OPEN state raster, or
    None if nothing in the window reaches the threshold."""
    # airport geometry is EPSG:5070; the raster is ESRI:102039 -- two
    # look-alike Albers projections. Reproject before building the window;
    # mixing them silently mis-centers the crop.
    center = gpd.GeoSeries([airport.geometry], crs="EPSG:5070").to_crs(ds.crs).iloc[0]
    box = center.buffer(radius_km * 1000).bounds
    win = from_bounds(*box, transform=ds.transform).round_offsets().round_lengths()
    arr = ds.read(1, window=win, masked=True)
    win_transform = ds.window_transform(win)

    # Explicit include raster: 1 = valid cell above threshold. No mask
    # kwarg -- rasterio shapes() mask semantics are easy to invert;
    # filtering returned value == 1 is unambiguous.
    include = (arr.data >= threshold).astype("uint8")
    include[arr.mask] = 0
    polys = [shape(g) for g, v in shapes(include, transform=win_transform)
             if v == 1]
    polys = [p for p in polys if p.area > 0]
    if not polys:
        return None
    contour = unary_union(polys)
    return gpd.GeoDataFrame(
        {"airport": airport["iata_code"], "dnl_min": threshold,
         "source": "BTS CONUS aviation noise 2022 (modeled)"},
        geometry=[contour], crs=ds.crs, index=[0])


def write_geojson(gdf: gpd.GeoDataFrame) -> Path:
    iata = gdf["airport"].iloc[0]
    dest = CONTOURS_DIR / iata.lower() / f"{iata.lower()}_dnl{int(gdf['dnl_min'].iloc[0])}.geojson"
    dest.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(dest, driver="GeoJSON")
    return dest


def extract_one(iata: str, gdb: Path, radius_km: float, threshold: float) -> None:
    airports = gpd.read_parquet(PROC_DIR / "airports.parquet")
    match = airports[airports["iata_code"] == iata]
    if match.empty:
        sys.exit(f"{iata} not in processed/airports.parquet — check the IATA code")
    airport = match.iloc[0]
    state = airport["iso_region"].split("-")[1]
    print(f"{iata}: {airport['name']} ({state}) -- centering {radius_km} km box")
    uri = f'OpenFileGDB:"{gdb.as_posix()}":{state}_aviation_noise'
    with rasterio.open(uri) as ds:
        gdf = extract_from(ds, airport, radius_km, threshold)
    if gdf is None:
        sys.exit(f"no cells >= {threshold} dB within {radius_km} km -- "
                 f"widen --radius-km or lower --threshold")
    dest = write_geojson(gdf)
    print(f"wrote {dest.relative_to(RAW_DIR.parent)} "
          f"({gdf.geometry.iloc[0].area / 1e6:.1f} km^2 >= {threshold} dB)")


def extract_all(gdb: Path, radius_km: float, threshold: float) -> None:
    airports = gpd.read_parquet(PROC_DIR / "airports.parquet")
    results = []
    states = airports["iso_region"].str.split("-").str[1]
    for state, group in airports.groupby(states):
        uri = f'OpenFileGDB:"{gdb.as_posix()}":{state}_aviation_noise'
        with rasterio.open(uri) as ds:
            for _, airport in group.iterrows():
                iata = airport["iata_code"]
                gdf = extract_from(ds, airport, radius_km, threshold)
                if gdf is None:
                    print(f"{iata}: no zone >={threshold} dB")
                    results.append({"iata": iata, "type": airport["type"],
                                    "has_zone": False, "zone_area_km2": None})
                    continue
                area = gdf.geometry.iloc[0].area / 1e6
                write_geojson(gdf)
                print(f"{iata}: zone {area:.1f} km^2")
                results.append({"iata": iata, "type": airport["type"],
                                "has_zone": True, "zone_area_km2": round(area, 1)})
    summary = pd.DataFrame(results)
    CONTOURS_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(CONTOURS_DIR / "_batch_summary.csv", index=False)
    n = int(summary["has_zone"].sum())
    print(f"\n{n}/{len(summary)} airports have a >={threshold} dB zone "
          f"(see contours/_batch_summary.csv)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iata", nargs="?", help="one airport, e.g. ATL; omit for batch")
    parser.add_argument("--gdb", type=Path,
                        default=Path(os.environ["BTS_NOISE_GDB"])
                        if "BTS_NOISE_GDB" in os.environ else None,
                        help="path to CONUS_aviation_noise.gdb (or set BTS_NOISE_GDB)")
    parser.add_argument("--radius-km", type=float, default=40.0)
    parser.add_argument("--threshold", type=float, default=65.0)
    args = parser.parse_args()

    if args.gdb is None:
        sys.exit("pass --gdb /path/to/CONUS_aviation_noise.gdb or set BTS_NOISE_GDB")
    if not args.gdb.exists():
        sys.exit(f"gdb not found: {args.gdb}")
    if args.iata:
        extract_one(args.iata.upper(), args.gdb, args.radius_km, args.threshold)
    else:
        extract_all(args.gdb, args.radius_km, args.threshold)


if __name__ == "__main__":
    main()
