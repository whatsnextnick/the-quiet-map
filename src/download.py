"""Fetch public datasets into data/raw/.

One function per source. Raw files are never modified — all cleaning and
derivation happens in prepare.py against copies in data/processed/.

Planned sources (see docs/data-sources.md for the live log):
- OurAirports / FAA 5010 — airport + runway locations
- U.S. Census ACS 5-year — tract geometries + demographic tables
- Airport Noise Exposure Maps (DNL 65 dB contours), pilot airports
"""
