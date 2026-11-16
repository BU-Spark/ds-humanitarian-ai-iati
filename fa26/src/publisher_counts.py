import json

with open("data/graph/coverage_geography_only.json") as f:
    before = json.load(f)

with open("data/graph/coverage_hunger_filtered.json") as f:
    after = json.load(f)

publishers = {
    "oxfamgb": "Oxfam GB",
    "oxfamus": "Oxfam America",
    "wfp": "WFP"
}

print(f"{'Publisher':<20} {'Before':>10} {'After':>10} {'Removed':>10}")

for key, name in publishers.items():
    b = before["per_publisher_funnel"].get(key, {})
    a = after["per_publisher_funnel"].get(key, {})

    # Geography-only run: activities passing the geography filter
    before_count = b.get("kept_via_geo_only", 0)

    # Normal run: activities retained by the hunger filter
    after_count = sum(
        value for metric, value in a.items()
        if metric.startswith("kept_via_") or metric == "kept_by_review"
    )

    removed = before_count - after_count

    print(f"{name:<20} {before_count:>10} {after_count:>10} {removed:>10}")
