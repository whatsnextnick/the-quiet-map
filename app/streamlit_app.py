"""The Quiet Map -- interactive explorer (run with Streamlit).

    python -m streamlit run app/streamlit_app.py

Two views:
- National overview: every airport with a DNL 65+ zone, sized by exposed
  population, colored by disparity ratio
- Airport explorer: one airport's zone over its neighboring tracts,
  colored by a variable you choose, with its equity numbers alongside

Map building lives in src/map.py; this file is only layout + selection.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import folium  # noqa: E402
import streamlit as st  # noqa: E402

import map as qmap  # noqa: E402

st.set_page_config(page_title="The Quiet Map", layout="wide")
st.title("The Quiet Map")
st.caption("Who lives under America's airport noise — modeled from BTS 2022 "
           "national aviation noise data + ACS demographics")


@st.cache_data(show_spinner="Loading data…")
def load():
    return qmap.load()


def show(m: folium.Map, height: int = 700) -> None:
    st.components.v1.html(m.get_root().render(), height=height)


data = load()

view = st.sidebar.radio("View", ["National overview", "Airport explorer"])
group = st.sidebar.selectbox(
    "Disparity group (national view)",
    sorted(data["by_group"]["group"].unique()),
    index=sorted(data["by_group"]["group"].unique()).index("Black / African American"))

if view == "National overview":
    st.subheader("Every U.S. airport's noise footprint")
    st.write("Circle size = people living in the airport's DNL 65+ zone. "
             "Color = how over- or under-represented the selected group is "
             "inside that zone (gray = not enough data). Click an airport "
             "for details.")
    show(qmap.national_map(data, group))
else:
    ranked = data["summary"].sort_values("exposed_pop", ascending=False)
    labels = [f"{r.airport} — {r.exposed_pop:,.0f} exposed"
              for r in ranked.itertuples()]
    default = next((i for i, l in enumerate(labels) if l.startswith("ATL — ")), 0)
    pick = st.sidebar.selectbox("Airport (by exposed population)", labels,
                                index=default)
    iata = pick.split(" — ")[0]
    variable = st.sidebar.selectbox("Color tracts by", list(qmap.VARIABLES),
                                    format_func=lambda k: qmap.VARIABLES[k][0])

    s = ranked[ranked["airport"] == iata].iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("People in the zone", f"{s['exposed_pop']:,.0f}")
    c2.metric("Zone area", f"{s['zone_area_km2']} km²")
    c3.metric("Poverty inside", f"{s['poverty_rate_inside']:.1%}",
              delta=f"{(s['poverty_rate_inside'] - s['poverty_rate_outside']):.1%} vs nearby")
    g = data["by_group"][(data["by_group"]["airport"] == iata)
                         & (data["by_group"]["group"] == group)].iloc[0]
    c4.metric(f"{group} disparity ratio", g["disparity_ratio"])

    left, right = st.columns([3, 1])
    with left:
        show(qmap.airport_map(data, iata, variable))
    with right:
        st.subheader("Who's in the zone")
        rows = data["by_group"][data["by_group"]["airport"] == iata]
        chart = rows.set_index("group")[["disparity_ratio"]].dropna()
        st.bar_chart(chart)
        st.dataframe(rows[["group", "exposed", "share_of_exposed",
                           "share_of_reference"]]
                     .set_index("group"),
                     use_container_width=True)
        st.caption("Ratio > 1 = over-represented in the noise zone. "
                   "All figures modeled (BTS 2022); zone is DNL 65+.")
