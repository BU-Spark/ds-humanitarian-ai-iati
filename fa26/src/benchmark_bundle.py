"""Public-input adapter for notebooks 05/06. Never imports evaluator definitions."""
import copy
import hashlib
import json
from pathlib import Path


def load_bundle(path, snapshot_id):
    root = Path(path).expanduser().resolve()
    def read(name):
        return json.loads((root / name).read_text())
    manifest = read('manifest.json')
    template = read('submission_template.json')
    questions = read('questions.json')
    if manifest['snapshot_id'] != snapshot_id or template['snapshot_id'] != snapshot_id:
        raise ValueError('Bundle snapshot does not match the loaded benchmark')
    digest = hashlib.sha256(json.dumps(manifest['files'], sort_keys=True).encode()).hexdigest()
    if digest != snapshot_id:
        raise ValueError('Invalid manifest identity')
    for name, record in manifest['files'].items():
        if Path(name).name != name:
            raise ValueError('Invalid snapshot filename')
        if hashlib.sha256((root/'snapshot'/name).read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Bundle data hash mismatch')
    if template.get('benchmark_id') != 'iati-v2-100-2026-10-29':
        raise ValueError('Unsupported benchmark version')
    if template.get('split') not in ('regression','development','heldout','all'):
        raise ValueError('Invalid split')
    ids = [q['id'] for q in questions]
    if not ids or len(ids) != len(set(ids)) or ids != [a['id'] for a in template['answers']]:
        raise ValueError('Question/template IDs disagree')
    for q in questions:
        allowed = {'id','question','contract','value_type'} if q['id'].startswith('Q') else {'id','question'}
        if set(q) - allowed:
            raise ValueError('Unexpected evaluator metadata in public questions')
    instructions = (root/'README.md').read_text()
    # Vocabulary is public in the export, not imported from the evaluator catalog.
    marker = 'Allowed reason codes (global vocabulary, not mapped to questions):'
    if marker not in instructions:
        raise ValueError('Missing public reason vocabulary')
    reasons = [x.strip() for x in instructions.split(marker,1)[1].strip().splitlines()[0].split(',')]
    return dict(root=root,questions=questions,template=template,instructions=instructions,reasons=reasons)


def submission(bundle, run_name, snapshot_id, answers, synthetic=False):
    result = copy.deepcopy(bundle['template']) if bundle else dict(snapshot_id=snapshot_id)
    result.update(run_name=run_name,answers=answers,synthetic=synthetic)
    return result


def score_command(python, fa26, paths, output, bundle=None):
    if bundle:
        return [python,str(fa26/'benchmark/v2/score_v2.py'),*map(str,paths),'--split',bundle['template']['split'],'--output',str(output)]
    return [python,str(fa26/'benchmark/score.py'),*map(str,paths),str(fa26/'benchmark/runs/sqlite_baseline.json'),'--output',str(output)]


def read_scores(path, bundle=None):
    data=json.loads((Path(path)/('comparison.json' if bundle else 'details.json')).read_text())
    if bundle:
        for run in data['runs']:run['summary']['run_name']=run['run_name']
    return data
