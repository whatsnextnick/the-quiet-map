"""Normalize and clean geometries for analysis.

Planned responsibilities:
- Project all layers to a single CRS (Albers Equal Area, EPSG:5070)
- Repair invalid tract / contour geometries
- Derive analysis-ready layers in data/processed/ (tracts, runways,
  contours or modeled distance bands)
"""
