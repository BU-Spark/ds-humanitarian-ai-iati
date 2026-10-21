"""One-time snapshot initialization; refuses to replace an existing manifest."""
import csv
import hashlib
import json
import shutil
import subprocess
from common import ROOT, SNAPSHOT, digest, save_json


def main():
    if (ROOT/'manifest.json').exists():
        raise SystemExit('Snapshot already pinned. Create a new benchmark version to change inputs.')
    source=ROOT.parent/'data/graph'
    SNAPSHOT.mkdir(parents=True,exist_ok=True)
    files={}
    for p in sorted(source.glob('*.csv')):
        dest=SNAPSHOT/p.name
        shutil.copyfile(p,dest)
        with dest.open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        files[p.name]={'sha256':digest(dest),'rows':len(rows)}
    if not files: raise ValueError('No CSV inputs found')
    snapshot_id=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT.parent,text=True).strip()
    save_json(ROOT/'manifest.json',dict(version=1,snapshot_id=snapshot_id,source_commit=commit,source_directory='fa26/data/graph',pinned_on='2026-10-15',files=files,limitations=['Exported filtered data, not raw XML or independently validated humanitarian ground truth.','No historical snapshots or external needs data.','Positional source IDs are meaningful only with this snapshot hash.']))
    print(f'Pinned {len(files)} files: {snapshot_id}')


if __name__=='__main__': main()
