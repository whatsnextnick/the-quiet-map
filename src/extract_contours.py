"""Extract one airport's DNL contour from the BTS national noise mosaic.

The BTS "CONUS Aviation Noise" mosaic (an Esri File Geodatabase of 30m
rasters, one per state) stores DNL values per cell. This tool crops the
relevant state raster to a square around an airport, thresholds it at the
DNL cutoff, polygonizes the result, and writes a GeoJSON into
data/raw/contours/<iata>/ — which src/prepare.py then picks up.

Usage:
    export BTS_NOISE_GDB=/path/to/CONUS_aviation_noise.gdb
    python src/extract_contours.py ATL
    python src/extract_contours.py ATL --radius-km 60 --threshold 65

NOTE: BTS noise values are MODELED (national 2022 model), not a published
airport Noise Exposure Map. Everything derived from them must be labeled
as modeled.
"""

import argparse
import os
import sys
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.features import shapes
from rasterio.windows import from_bounds
from shapely.geometry import shape
from shapely.ops import unary_union

PROC_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def extract(iata: str, gdb: Path, radius_km: float, threshold: float) -> None:
    airports = gpd.read_parquet(PROC_DIR / "airports.parquet")
    match = airports[airports["iata_code"] == iata]
    if match.empty:
        sys.exit(f"{iata} not in processed/airports.parquet — check the IATA code")
    airport = match.iloc[0]
    state = airport["iso_region"].split("-")[1]
    print(f"{iata}: {airport['name']} ({state}) -- centering {radius_km} km box")

    uri = f'OpenFileGDB:"{gdb.as_posix()}":{state}_aviation_noise'
    with rasterio.open(uri) as ds:
        src_crs = ds.crs
        center = airport.geometry  # already EPSG:5070 (meters)
        box = center.buffer(radius_km * 1000).bounds
        win = from_bounds(*box, transform=ds.transform).round_offsets().round_lengths()
        arr = ds.read(1, window=win, masked=True)
        win_transform = ds.window_transform(win)
        print(f"raster: {ds.width}x{ds.height} cells @ {ds.res}, "
              f"nodata={ds.nodata}, window={arr.shape}, "
              f"value range {arr.min():.1f}-{arr.max():.1f}")

    # Build an explicit include raster: 1 = valid cell above threshold.
    # No mask kwarg -- rasterio's shapes() mask semantics are easy to get
    # inverted; filtering the returned value == 1 is unambiguous.
    include = (arr.data >= threshold).astype("uint8")
    include[arr.mask] = 0
    polys = [shape(g) for g, v in shapes(include, transform=win_transform)
             if v == 1]
    polys = [p for p in polys if p.area > 0]
    if not polys:
        sys.exit(f"no cells >= {threshold} dB within {radius_km} km -- "
                 f"widen --radius-km or lower --threshold")
    contour = unary_union(polys)

    gdf = gpd.GeoDataFrame(
        {"airport": iata, "dnl_min": threshold,
         "source": "BTS CONUS aviation noise 2022 (modeled)"},
        geometry=[contour], crs=src_crs, index=[0])
    dest = RAW_DIR / "contours" / iata.lower() / f"{iata.lower()}_dnl{int(threshold)}.geojson"
    dest.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(dest, driver="GeoJSON")
    print(f"wrote {dest.relative_to(RAW_DIR.parent)} "
          f"({len(polys)} polygons, {contour.area / 1e6:.0f} km^2 >= {threshold} dB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iata", help="airport IATA code, e.g. ATL")
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
    extract(args.iata.upper(), args.gdb, args.radius_km, args.threshold)


if __name__ == "__main__":
    main()
