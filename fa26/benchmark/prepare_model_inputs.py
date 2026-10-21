"""Export only public evaluation inputs; never include answer keys or baselines."""
import argparse
from pathlib import Path
import shutil

from common import ROOT, verify_snapshot

INSTRUCTIONS = """Answer questions.json using only snapshot/ and each question's calculation contract.
Return JSON matching submission_template.json with a unique run_name and unchanged snapshot_id.
Each fact needs its value and all contributing logical CSV source row IDs, e.g.
nodes_activities.csv:row:1 (first data record, excluding the header).
For an empty result, cite manifest:filename.csv for the complete table searched.
Return monetary values as decimal strings. Keep currencies, transaction types and periods separate.
Do not invent missing data. Use abstain or clarify when warranted, with empty facts and relevant
reason codes: NEEDS_DATA_MISSING, HISTORY_UNAVAILABLE, FUNDING_DEFINITION_REQUIRED,
CURRENCY_BASIS_REQUIRED, PERIOD_REQUIRED, RAW_XML_UNAVAILABLE.
Do not inspect evaluator files, reference answers, SQL baselines or previous results.
Preserve raw model responses separately. Any manual adaptation must be labeled and must not fix answers.
This folder contains no model responses or reference answers.
"""


def prepare(destination):
    manifest = verify_snapshot()
    destination = Path(destination).resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('Export outside benchmark/ to keep evaluator context separate')
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'snapshot').mkdir()
    for name in manifest['files']:
        shutil.copyfile(ROOT / 'snapshot' / name, destination / 'snapshot' / name)
    for name in ('manifest.json', 'questions.json', 'submission_template.json'):
        shutil.copyfile(ROOT / name, destination / name)
    (destination / 'INSTRUCTIONS.txt').write_text(INSTRUCTIONS)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    print(prepare(parser.parse_args().destination))
