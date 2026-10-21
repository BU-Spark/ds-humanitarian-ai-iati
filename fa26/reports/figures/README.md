# Graph screenshots — October 21, 2026

Rendered from the existing Gradio application in `fa26/spaces/app.py`, using its bundled graph data. PNGs are 2400 × 1500 pixels. These are application/data views, not model-evaluation results or visualizations of the corrected NetworkX graph.

- `01_activity_coverage.png`: all hotspot countries and publishers.
- `02_yemen_funding_usd.png`: Yemen funding view, USD.
- `03_yemen_funding_gbp.png`: Yemen funding view, GBP.
- `04_funding_timeline_usd.png`: disbursements plus expenditure by year, USD.
- `05_funding_timeline_gbp.png`: disbursements plus expenditure by year, GBP.
- `06_yemen_knowledge_graph.png`: Yemen, all publishers, minimum two participations per organisation, sectors hidden.

Funding charts preserve the existing app calculations: the flow chart includes transaction types 1/11 on the incoming side and type 3 on the outgoing side; the timeline combines types 3/4. These should not be described as balanced flows or deduplicated aid totals. Currencies are shown separately. No model API was called and no application code was changed.
