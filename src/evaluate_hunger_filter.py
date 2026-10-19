import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import parse_filter as pf
csv.field_size_limit(10_000_000)
from config import PUBLISHERS, RAW_DIR, GRAPH_DIR

OUTPUT = GRAPH_DIR / "hunger_filter_sample_50.csv"
SEED = 42


def load_candidates():
    candidates = []
    seen = set()

    for publisher in PUBLISHERS:
        folder = RAW_DIR / publisher

        if not folder.exists():
            print(f"Missing raw data: {folder}")
            continue

        for xml_file in sorted(folder.glob("*.xml")):
            for _, act in ET.iterparse(xml_file, events=("end",)):
                if act.tag != "iati-activity":
                    continue

                rec = pf.parse_activity(act, publisher)
                act.clear()

                if rec is None:
                    continue

                iid = rec["activity"]["iati_identifier"]

                if iid in seen:
                    continue
                seen.add(iid)

                # Evaluate the hunger filter only after geography passes.
                if not pf.hotspot_codes(rec):
                    continue

                matched, method = pf.old_hunger_match(rec)

                candidates.append({
                    "activity_id": iid,
                    "publisher": publisher,
                    "title": rec["activity"]["title"],
                    "description": rec["activity"]["description"],
                    "sector_codes": "; ".join(
                        f'{s.get("code", "")} (vocab {s.get("vocabulary", "")})'
                        for s in rec.get("sectors", [])
                    ),
                    "sector_names": "; ".join(
                        s.get("name", "")
                        for s in rec.get("sectors", [])
                        if s.get("name")
                    ),
                    "hotspot_countries": "; ".join(
                        c.get("code", "")
                        for c in rec.get("countries", [])
                        if c.get("code")
                    ),
                    "old_filter": "yes" if matched else "no",
                    "match_basis": method,
                    "manual_label": "",
                    "improved_filter": "",
                    "record_json": json.dumps(rec),
                })

    return candidates


def get_sample(candidates):
    positives = [r for r in candidates if r["old_filter"] == "yes"]
    negatives = [r for r in candidates if r["old_filter"] == "no"]

    rng = random.Random(SEED)
    rng.shuffle(positives)
    rng.shuffle(negatives)

    # Aim for 25 old positives and 25 old negatives.
    sample = positives[:25] + negatives[:25]

    if len(sample) < 50:
        remaining = [
            r for r in candidates
            if r not in sample
        ]
        rng.shuffle(remaining)
        sample += remaining[:50 - len(sample)]

    rng.shuffle(sample)
    return sample


def calculate_metrics(rows):
    labeled = [
        r for r in rows
        if r["manual_label"].strip().lower() in
        ("yes", "no", "true", "false", "1", "0")
    ]

    if not labeled:
        print("No manual labels yet. Label the CSV first.")
        return

    for prediction_col in ("old_filter", "improved_filter"):
        evaluated = [
            r for r in labeled if r[prediction_col].strip().lower()
            in ("yes", "no", "true", "false", "1", "0")
        ]

        if not evaluated:
            print(f"\n{prediction_col}: predictions not populated yet.")
            continue

        tp = fp = tn = fn = 0

        for r in evaluated:
            actual = r["manual_label"].strip().lower() in (
                "yes", "true", "1"
            )
            predicted = r[prediction_col].strip().lower() in (
                "yes", "true", "1"
            )

            if predicted and actual:
                tp += 1
            elif predicted and not actual:
                fp += 1
            elif not predicted and not actual:
                tn += 1
            else:
                fn += 1

        total = len(evaluated)
        accuracy = (tp + tn) / total
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0

        print(f"\n{prediction_col} (n={total})")
        print(f"TP={tp}, FP={fp}, TN={tn}, FN={fn}")
        print(f"Accuracy:  {accuracy:.1%}")
        print(f"Precision: {precision:.1%}")
        print(f"Recall:    {recall:.1%}")


def main():
    # Updated the evaluator to detect an empty sample CSV and regenerate the 50 activities
    # from the original XML files instead of reusing an empty file. Existing activity rows
    # and manual labels are preserved whenever available. The function also recovers missing
    # activity records when possible, reruns the improved hunger filter, saves its predictions,
    # and calculates evaluation metrics without overwriting a valid sample with zero rows.

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    rows = []

    if OUTPUT.exists():
        with open(OUTPUT, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        if rows:
            print(f"Reusing existing sample: {len(rows)} activities")
        else:
            print("Existing CSV is empty. Regenerating the sample.")

    candidates = None

    if not rows:
        candidates = load_candidates()
        rows = get_sample(candidates)

        if not rows:
            print("No eligible activities found. Check RAW_DIR and XML files.")
            return

        print(f"Created sample: {len(rows)} activities")

    # Recover missing activity records without replacing existing manual labels.
    if any(not r.get("record_json", "").strip() for r in rows):
        if candidates is None:
            candidates = load_candidates()

        candidate_lookup = {
            r["activity_id"]: r for r in candidates
        }

        for row in rows:
            if not row.get("record_json", "").strip():
                candidate = candidate_lookup.get(row.get("activity_id", ""))

                if candidate:
                    row["record_json"] = candidate.get("record_json", "")

    # Apply the improved filter to each sampled activity.
    for row in rows:
        record_json = row.get("record_json", "").strip()

        if not record_json:
            print(f"Missing activity data: {row.get('activity_id', 'unknown')}")
            row["old_filter"] = ""
            row["improved_filter"] = ""
            continue

        try:
            rec = json.loads(record_json)

            old_match, old_method = pf.old_hunger_match(rec)
            new_match, new_method = pf.hunger_match(rec)

            row["old_filter"] = "yes" if old_match else "no"
            row["improved_filter"] = "yes" if new_match else "no"

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Could not evaluate {row.get('activity_id', 'unknown')}: {e}")
            row["old_filter"] = ""
            row["improved_filter"] = ""

    # Compare old and improved predictions.
    differences = sum(
        row.get("old_filter") != row.get("improved_filter")
        for row in rows
        if row.get("old_filter") and row.get("improved_filter")
    )

    print(f"Activities where filters disagree: {differences}/{len(rows)}")

    fields = [
        "activity_id", "publisher", "title", "description",
        "old_filter", "match_basis", "manual_label",
        "improved_filter", "record_json", "sector_codes",
        "sector_names", "hotspot_countries"
    ]

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSample saved to: {OUTPUT}")
    print("Old filter counts:", dict(Counter(r["old_filter"] for r in rows)))
    print("Improved filter counts:", dict(Counter(
        r["improved_filter"] for r in rows
    )))
    calculate_metrics(rows)


if __name__ == "__main__":
    main()
