"""Offline demonstration using synthetic XML; use a new output directory each time."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from snapshot_download import capture, export_snapshot, verify

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('output', type=Path)
a = ap.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
raw, store = a.output / 'inputs', a.output / 'store'
xml = '<iati-activities version="2.03"><iati-activity><iati-identifier>DEMO-1</iati-identifier></iati-activity></iati-activities>'
pubs = ['oxfamgb', 'oxfamus', 'wfp']
for pub in pubs:
    (raw / pub).mkdir(parents=True)
    (raw / pub / 'demo.xml').write_text(xml)
first = capture(store, pubs, local_dir=raw)
unchanged = capture(store, pubs, local_dir=raw)
(raw / 'wfp' / 'demo.xml').write_text(xml.replace('DEMO-1', 'DEMO-2'))
changed = capture(store, pubs, local_dir=raw)
(raw / 'wfp' / 'demo.xml').write_text('<incomplete')
try:
    capture(store, pubs, local_dir=raw)
except Exception as exc:
    failure = type(exc).__name__
else:
    raise AssertionError('Malformed input should fail')
current = verify(store)
export_snapshot(store, a.output / 'restored-first-version', first['run_id'])
summary = {
    'data': 'Synthetic demonstration only, not publisher data',
    'successful_versions': 3,
    'unique_xml_objects': len(list((store / 'objects').rglob('*.xml'))),
    'unchanged_version_reuses_content': first['content_id'] == unchanged['content_id'],
    'changed_version_has_new_content': first['content_id'] != changed['content_id'],
    'failed_refresh_error': failure,
    'latest_preserved_after_failure': current['run_id'] == changed['run_id'],
    'restored_original': (a.output / 'restored-first-version' / 'wfp' / 'demo.xml').read_text() == xml,
}
assert summary['unique_xml_objects'] == 2
assert all(summary[k] for k in ('unchanged_version_reuses_content', 'changed_version_has_new_content',
                              'latest_preserved_after_failure', 'restored_original'))
(a.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
