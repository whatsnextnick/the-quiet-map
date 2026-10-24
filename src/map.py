"""Interactive map builders for The Quiet Map.

Two views:
- national_map(): every airport with a DNL 65 zone as a circle sized by
  exposed population, colored by a chosen group's disparity ratio
- airport_map(iata, variable): one airport -- zone overlay, nearby tracts
  colored by a chosen demographic variable, runways underneath

Used by app/streamlit_app.py (the explorer) and by this file's CLI, which
writes static HTML into reports/figures/:

    python src/map.py                 # national + ATL overview
    python src/map.py national
    python src/map.py ATL --variable poverty_rate

All geometry is projected (EPSG:5070) for math, converted to WGS84 (the
web-map standard) only at display time.
"""

import argparse
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
from branca.colormap import LinearColormap

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUT_DIR = Path(__file__).resolve().parent.parent / "reports" / "figures"

VARIABLES = {
    "poverty_rate": ("Poverty rate", "Poverty rate (%)", ["#fee5d9", "#fb6a4a", "#a50f15"]),
    "race_black_pct": ("Black share of population", "Black residents (%)", ["#f2f0f7", "#9e9ac8", "#54278f"]),
    "median_income": ("Median household income", "Median household income ($)", ["#eff3ff", "#6baed6", "#08306b"]),
    "median_age": ("Median age", "Median age (years)", ["#edf8e9", "#74c476", "#00441b"]),
    "total_pop": ("Population", "Population", ["#fff5eb", "#fd8d3c", "#7f2704"]),
}


def load():
    tracts = gpd.read_parquet(DATA_DIR / "tracts.parquet")
    tracts["poverty_rate"] = (tracts["poverty_count"] / tracts["total_pop"] * 100
                              ).where(tracts["total_pop"] > 0)
    tracts["race_black_pct"] = (tracts["race_black"] / tracts["total_pop"] * 100
                                ).where(tracts["total_pop"] > 0)
    return {
        "tracts": tracts,
        "contours": gpd.read_parquet(DATA_DIR / "contours.parquet"),
        "airports": gpd.read_parquet(DATA_DIR / "airports.parquet"),
        "runways": gpd.read_parquet(DATA_DIR / "runways.parquet"),
        "summary": pd.read_csv(DATA_DIR / "exposure_summary.csv"),
        "by_group": pd.read_csv(DATA_DIR / "exposure_by_group.csv"),
    }


def national_map(data, group: str = "Black / African American") -> folium.Map:
    """National view. Bubble SIZE encodes the chosen group's disparity
    ratio -- this is what visibly changes when you switch groups. Bubble
    COLOR encodes exposed population -- a constant reference frame."""
    m = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="OpenStreetMap")
    ap = data["airports"].merge(data["summary"], left_on="iata_code",
                                right_on="airport")
    ap = ap.merge(data["by_group"][data["by_group"]["group"] == group]
                  [["airport", "disparity_ratio"]], on="airport")
    pts = ap.to_crs("EPSG:4326")
    pts["lat"] = pts.geometry.y
    pts["lon"] = pts.geometry.x

    vmax = pts["exposed_pop"].quantile(0.98)
    exp_cmap = LinearColormap(["#fff5f0", "#fb6a4a", "#67000d"], vmin=0,
                              vmax=vmax, caption="People living in DNL 65+ zone")
    for _, r in pts.iterrows():
        ratio = r["disparity_ratio"]
        if pd.isna(ratio):
            radius, color = 4.5, "#999999"
        else:
            clipped = min(max(ratio, 0.25), 4.0)
            radius = 2.5 + 12 * ((clipped - 0.25) / 3.75) ** 0.5
            color = exp_cmap(min(r["exposed_pop"], vmax))
        tip = (f"{r['iata_code']} — {r['name']}<br>"
               f"{r['exposed_pop']:,.0f} people exposed<br>"
               f"{group} ratio: "
               f"{ratio if pd.isna(ratio) else round(ratio, 2)}")
        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=radius,
            color="#333333", weight=0.5,
            fill=True, fill_color=color, fill_opacity=0.75,
            tooltip=folium.Tooltip(tip),
        ).add_to(m)
    exp_cmap.add_to(m)
    m.get_root().html.add_child(folium.Element(
        '<div style="position: fixed; bottom: 32px; left: 32px; z-index: 9999; '
        'background: rgba(255,255,255,0.92); padding: 8px 10px; '
        'border: 1px solid #999; border-radius: 4px; font-size: 12px;">'
        f'<b>Bubble size</b> = {group} disparity ratio<br/>'
        '(bigger = more over-represented)<br/>'
        '<b>Bubble color</b> = people exposed</div>'))
    return m


def airport_map(data, iata: str, variable: str = "poverty_rate") -> folium.Map:
    label, tooltip_label, colors = VARIABLES[variable]
    contours = data["contours"]
    zone = contours.loc[contours["airport"] == iata, "geometry"]
    if zone.empty:
        raise SystemExit(f"{iata} has no zone in contours.parquet")
    zone = zone.iloc[0]

    focus = zone.centroid.buffer(max(zone.bounds[2] - zone.bounds[0],
                                     zone.bounds[3] - zone.bounds[1], 6000) * 0.8 + 3000)
    idx = list(data["tracts"].sindex.intersection(focus.bounds))
    near = data["tracts"].iloc[idx].copy()
    near["frac_inside"] = (near.geometry.intersection(zone).area
                           / near.geometry.area).clip(0, 1)
    near = near.to_crs("EPSG:4326")
    # Generalize for web display: ~11m tolerance is invisible at city zoom
    # but cuts the embedded GeoJSON several-fold.
    near = near.set_geometry(near.geometry.simplify(0.0001))
    near["frac_inside_pct"] = (near["frac_inside"] * 100).round(1)
    keep = list(dict.fromkeys(["NAME", "total_pop", "poverty_rate",
                               "median_income", "median_age",
                               "frac_inside_pct", variable, "geometry"]))
    near = near[[c for c in keep if c in near.columns]]
    for col in ("poverty_rate", "median_income", "median_age"):
        near[col] = near[col].round(0)

    vals = near[variable].dropna()
    lo, hi = (vals.quantile(0.02), vals.quantile(0.98)) if len(vals) else (0, 1)
    cmap = LinearColormap(colors, vmin=lo, vmax=hi, caption=tooltip_label)

    m = folium.Map(tiles="OpenStreetMap")

    def style(f):
        v = f["properties"].get(variable)
        return {"fillColor": "#cccccc" if v is None else cmap(v),
                "fillOpacity": 0.65 if v is not None else 0.1,
                "color": "#555555", "weight": 0.4}

    tip = folium.GeoJsonTooltip(
        fields=["NAME", "total_pop", "poverty_rate", "median_age", "frac_inside_pct"],
        aliases=["Tract", "Population", "Poverty %", "Median age", "% of tract in noise zone"],
        localize=True)
    folium.GeoJson(near, style_function=style, tooltip=tip, name="tracts").add_to(m)

    folium.GeoJson(
        gpd.GeoSeries([zone], crs="EPSG:5070").to_crs("EPSG:4326").__geo_interface__,
        style_function=lambda _: {"fillColor": "#d7191c", "color": "#d7191c",
                                  "weight": 2, "fillOpacity": 0.25},
        name="DNL 65+ zone", tooltip=f"{iata} DNL 65+ (modeled)",
    ).add_to(m)

    rwy = data["runways"]
    ridx = list(rwy.sindex.intersection(focus.bounds))
    for geom in rwy.iloc[ridx].to_crs("EPSG:4326").geometry:
        folium.PolyLine([(p[1], p[0]) for p in geom.coords], color="#444444",
                        weight=2.5, opacity=0.8).add_to(m)

    b = near.total_bounds
    m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
    return m


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", default="all", help="'national' or an IATA code")
    parser.add_argument("--variable", default="poverty_rate", choices=list(VARIABLES))
    args = parser.parse_args()

    data = load()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.target in ("all", "national"):
        out = OUT_DIR / "national_overview.html"
        national_map(data).save(out)
        print(f"wrote {out.relative_to(OUT_DIR.parent.parent)} ({out.stat().st_size // 1024} KB)")
    iata = None if args.target == "national" else ("ATL" if args.target == "all" else args.target)
    if iata:
        out = OUT_DIR / f"{iata.lower()}_map.html"
        airport_map(data, iata.upper(), args.variable).save(out)
        print(f"wrote {out.relative_to(OUT_DIR.parent.parent)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
