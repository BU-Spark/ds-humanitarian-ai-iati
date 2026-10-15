---
title: IATI Hunger Hotspots Knowledge Graph
emoji: 🕸️
colorFrom: purple
colorTo: green
sdk: gradio
sdk_version: 6.20.0
app_file: app.py
pinned: false
license: mit
---

# IATI Hunger Hotspots Knowledge Graph

Interactive demo comparing hunger-related IATI activities by Oxfam GB,
Oxfam America and WFP across the 13 FAO-WFP Hunger Hotspots
(June-November 2026 outlook).

Built with the [iati-hunger-graph](https://github.com/) pipeline: IATI Bulk
Data Service -> filtered graph CSVs -> this app. To refresh the data, rerun
the pipeline and replace the CSVs in `data/`.
