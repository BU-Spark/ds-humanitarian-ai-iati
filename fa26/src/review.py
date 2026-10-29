"""
review.py -- manual review layer for the hunger filter.

Borderline activities are flagged instead of being silently kept or dropped
(client meeting, 23 Oct 2026). Two files in data/review/:

  hunger_review_queue.csv      REGENERATED every parse run. Flagged
                               activities with no decision yet. Reviewers
                               fill `decision` (include / exclude),
                               `reviewer` and `notes` here.
  hunger_review_decisions.csv  Human-owned record of every decision. The
                               parser never deletes from it.

At the start of each parse run, filled-in queue rows are copied into the
decisions file (harvest), and only then is the queue rewritten, so a
decision is never lost to a regenerated queue. Decisions override the
filter: include keeps an activity the filter dropped, exclude drops one it
kept.

  python src/review.py status     # queue size, decisions so far
  python src/review.py harvest    # copy decisions out of the queue now
"""
import csv
import datetime
import sys

from config import REVIEW_DIR

QUEUE = REVIEW_DIR / "hunger_review_queue.csv"
DECISIONS = REVIEW_DIR / "hunger_review_decisions.csv"

QUEUE_FIELDS = ["iati_identifier", "publisher", "hotspot_countries", "title",
                "description", "filter_decision", "match_basis", "confidence",
                "review_reasons", "match_terms",
                "decision", "reviewer", "notes"]
DECISION_FIELDS = ["iati_identifier", "decision", "reviewer", "reviewed_on",
                   "notes", "title", "match_basis_at_review"]
QUEUE_DESCRIPTION_MAX = 1000  # enough to judge; full text is in the raw XML

# yes/no accepted too, matching the manual_label convention in the samples
DECISION_VALUES = {"include": "include", "yes": "include",
                   "exclude": "exclude", "no": "exclude"}


def _read(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel opens accented titles (French WFP records) correctly
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def harvest():
    """Copy filled-in queue rows into the decisions file. Returns the
    number of decisions added or changed."""
    decisions = {r["iati_identifier"]: r for r in _read(DECISIONS)}
    changed = 0
    for row in _read(QUEUE):
        raw = row.get("decision", "").strip().lower()
        if not raw:
            continue
        if raw not in DECISION_VALUES:
            print(f"[review] ignoring decision {raw!r} for "
                  f"{row['iati_identifier']}: use include or exclude")
            continue
        new = {
            "iati_identifier": row["iati_identifier"],
            "decision": DECISION_VALUES[raw],
            "reviewer": row.get("reviewer", "").strip(),
            "reviewed_on": datetime.date.today().isoformat(),
            "notes": row.get("notes", "").strip(),
            "title": row.get("title", ""),
            "match_basis_at_review": row.get("match_basis", ""),
        }
        old = decisions.get(new["iati_identifier"])
        if old and all(old.get(k) == new[k] for k in ("decision", "reviewer", "notes")):
            continue  # already harvested; keep the original date
        decisions[new["iati_identifier"]] = new
        changed += 1
    if changed:
        _write(DECISIONS, sorted(decisions.values(),
                                 key=lambda r: r["iati_identifier"]),
               DECISION_FIELDS)
        print(f"[review] {changed} decision(s) from the queue -> {DECISIONS.name}")
    return changed


def load_decisions():
    """{iati_identifier: "include" | "exclude"}"""
    out = {}
    for r in _read(DECISIONS):
        d = DECISION_VALUES.get(r.get("decision", "").strip().lower())
        if d:
            out[r["iati_identifier"]] = d
    return out


def write_queue(rows):
    rows = sorted(rows, key=lambda r: (r["filter_decision"], r["publisher"],
                                       r["iati_identifier"]))
    for r in rows:
        r["description"] = r["description"][:QUEUE_DESCRIPTION_MAX]
    _write(QUEUE, rows, QUEUE_FIELDS)
    print(f"[review] {len(rows)} activities awaiting review -> {QUEUE}")


def status():
    queue, decisions = _read(QUEUE), _read(DECISIONS)
    reasons = {}
    for r in queue:
        for reason in r["review_reasons"].split("|"):
            reasons[reason] = reasons.get(reason, 0) + 1
    print(f"queue: {len(queue)} awaiting review")
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {reason:<28} {n}")
    filled = sum(1 for r in queue if r.get("decision", "").strip())
    if filled:
        print(f"  ({filled} filled in, saved on next parse run or `harvest`)")
    counts = {}
    for r in decisions:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1
    print(f"decisions: {len(decisions)} "
          + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "harvest":
        harvest()
    elif cmd == "status":
        status()
    else:
        sys.exit("usage: python src/review.py [status|harvest]")
