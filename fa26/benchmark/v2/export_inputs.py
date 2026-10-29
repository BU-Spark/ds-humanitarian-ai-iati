"""Export only the chosen split, schema instructions and frozen source data."""
import argparse,shutil
from pathlib import Path
from engine import ROOT,QUESTIONS
from common import verify_snapshot,save_json
from build import public,template

INSTRUCTIONS='''# Model input bundle
Answer using only the supplied snapshot. Return the submission JSON format with the
same benchmark_id, snapshot_id and split. Set a descriptive run_name.
For every question choose answer, clarify or abstain. Use facts={} for clarify or
abstain and list the applicable reason codes. For answers use reasons=[].
For new questions: use fact key count for a single count, total for a single monetary
amount, date for a single date, and currency codes for amounts requested by currency.
Each fact has value (number or string) and evidence (source reference list).
Counts refer to distinct record identifiers unless the question explicitly asks for
rows. Missing financial scope must not be invented. Zero matches can be a valid
answer; they do not prove real-world absence. Date questions refer to recorded dates.
Evidence IDs: <table>.csv:row:<1-based data row>, excluding the header. Cite all rows
contributing to each fact, including joined activity rows and matching relationship
rows. For a zero-result answer cite manifest:<table>.csv for each searched table.
For date extrema, cite all rows considered in the comparison. This benchmark measures
full contributing evidence, not a sample of citations.
Original Q01–Q20 retain their calculation contracts for regression comparability.
Allowed reason codes (global vocabulary, not mapped to questions):
'''
# Include all v1 and v2 reason codes without exposing which question requires one.
def reason_codes():
    codes=set()
    for q in QUESTIONS:
        if q.get('legacy') and q['value_type']=='unsupported':codes.update(q['contract'].split('|')[1].split(','))
        else:codes.update(q.get('reasons',[]))
    return sorted(codes)

def export(destination,split='development'):
    destination=Path(destination)
    if destination.exists():raise ValueError('Destination must not exist')
    if split not in ('all','regression','development','heldout'):raise ValueError('Unknown split')
    # Prevent accidental writes under the evaluator checkout.
    if destination.resolve().is_relative_to(ROOT.parent.resolve()):raise ValueError('Export outside benchmark directory')
    manifest=verify_snapshot();qs=[q for q in QUESTIONS if split=='all' or q['split']==split]
    destination.mkdir(parents=True);(destination/'snapshot').mkdir()
    for name in manifest['files']:shutil.copyfile(ROOT.parent/'snapshot'/name,destination/'snapshot'/name)
    save_json(destination/'manifest.json',manifest);save_json(destination/'questions.json',[public(q) for q in qs]);save_json(destination/'submission_template.json',template(qs,manifest['snapshot_id'],split))
    (destination/'README.md').write_text(INSTRUCTIONS+', '.join(reason_codes())+'\n\nRecord latency_ms per question when measured; otherwise leave null. Record cost_usd for the whole run only when measured, otherwise null. No API calls are made by this exporter.\n')
    return destination
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination',type=Path);p.add_argument('--split',default='development',choices=['all','regression','development','heldout']);a=p.parse_args();print(export(a.destination,a.split))
