"""Standard-library utilities. No prototype imports or network access."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / 'snapshot'


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_snapshot():
    manifest = load_json(ROOT / 'manifest.json')
    actual = {p.name for p in SNAPSHOT.glob('*.csv')}
    if actual != set(manifest['files']):
        raise ValueError('Snapshot file inventory changed')
    for name, spec in manifest['files'].items():
        if digest(SNAPSHOT / name) != spec['sha256']:
            raise ValueError(f'Snapshot hash mismatch: {name}')
    content_id = hashlib.sha256(json.dumps(manifest['files'], sort_keys=True).encode()).hexdigest()
    if manifest['snapshot_id'] != content_id:
        raise ValueError('Manifest snapshot ID mismatch')
    return manifest


def read_tables():
    verify_snapshot()
    tables = {}
    for path in sorted(SNAPSHOT.glob('*.csv')):
        with path.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        for i, row in enumerate(rows, 1):
            row['_source'] = f'{path.name}:row:{i}'
        tables[path.stem] = rows
    return tables
