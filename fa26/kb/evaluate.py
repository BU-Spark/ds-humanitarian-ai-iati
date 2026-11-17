"""
kb/evaluate.py -- score search over the knowledge base against judged
questions (kb/eval_questions.json).

    python -m kb.evaluate                # country filter applied, as a router would
    python -m kb.evaluate --no-filters   # question text only
    python -m kb.evaluate --show-misses  # list relevant activities not retrieved

Per question:
  P@10    share of the top 10 hits that are relevant
  R@20    share of the relevant activities found in the top 20
  RR      1 / rank of the first relevant hit (0 if none in the top 20)
Means are reported by question kind too, so cross-language questions
(French WFP records) can be tracked separately.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from config import KB_PATH

from kb.search import search

QUESTIONS = Path(__file__).with_name("eval_questions.json")
DEPTH = 20


def score_question(q, use_filters=True, kb_path=KB_PATH):
    hits = search(q["question"], country=q.get("country") if use_filters else None,
                  limit=DEPTH, kb_path=kb_path)
    ids = [h["iati_identifier"] for h in hits]
    relevant = set(q["relevant"])
    top10 = ids[:10]
    first = next((i for i, x in enumerate(ids, 1) if x in relevant), None)
    return {
        "id": q["id"], "kind": q["kind"], "relevant": len(relevant),
        "p10": sum(x in relevant for x in top10) / 10,
        "r20": len(relevant & set(ids)) / len(relevant),
        "rr": 1 / first if first else 0.0,
        "misses": [x for x in q["relevant"] if x not in ids],
    }


def evaluate(path=QUESTIONS, use_filters=True, kb_path=KB_PATH):
    questions = json.loads(Path(path).read_text(encoding="utf-8"))["questions"]
    return [score_question(q, use_filters, kb_path) for q in questions]


def _mean(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else 0.0


def report(results, show_misses=False):
    print(f"{'id':<6}{'kind':<16}{'rel':>4}{'P@10':>7}{'R@20':>7}{'RR':>6}")
    for r in results:
        print(f"{r['id']:<6}{r['kind']:<16}{r['relevant']:>4}"
              f"{r['p10']:>7.2f}{r['r20']:>7.2f}{r['rr']:>6.2f}")
        if show_misses and r["misses"]:
            print("      missed:", ", ".join(r["misses"]))
    by_kind = defaultdict(list)
    for r in results:
        by_kind[r["kind"]].append(r)
    print()
    for kind, rows in sorted(by_kind.items()):
        print(f"mean {kind:<16}{len(rows):>4}{_mean(rows, 'p10'):>7.2f}"
              f"{_mean(rows, 'r20'):>7.2f}{_mean(rows, 'rr'):>6.2f}")
    print(f"mean {'ALL':<16}{len(results):>4}{_mean(results, 'p10'):>7.2f}"
          f"{_mean(results, 'r20'):>7.2f}{_mean(results, 'rr'):>6.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--no-filters", action="store_true",
                    help="ignore each question's country filter")
    ap.add_argument("--show-misses", action="store_true")
    ap.add_argument("--kb", type=Path, default=KB_PATH)
    args = ap.parse_args()
    report(evaluate(args.questions, not args.no_filters, args.kb), args.show_misses)
