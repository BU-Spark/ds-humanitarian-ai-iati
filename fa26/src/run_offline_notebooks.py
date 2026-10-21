"""Execute reviewed notebooks 01–03 without API calls, preserving source files.

Run from any directory. Logs and a machine-readable summary go to data/processed.
Notebook 04 deliberately remains outside the offline runner.
"""
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter


def main():
    fa26 = Path(__file__).resolve().parents[1]
    output = fa26 / 'data' / 'processed'
    output.mkdir(parents=True, exist_ok=True)
    os.environ['IATI_LIVE_EVAL'] = '0'
    os.chdir(fa26)
    records = []
    for number in ('01', '02', '03'):
        path, = sorted((fa26 / 'notebooks').glob(number + '_*.ipynb'))
        notebook = json.loads(path.read_text())
        namespace = {'__name__': '__offline_notebook__', 'display': lambda *args: print(*args, sep='\n')}
        stream = io.StringIO()
        started = perf_counter()
        with contextlib.redirect_stdout(stream):
            for index, cell in enumerate(notebook['cells']):
                if cell['cell_type'] == 'code':
                    exec(compile(''.join(cell['source']), f'{path.name}:cell:{index}', 'exec'), namespace)
        (output / (path.stem + '.log')).write_text(stream.getvalue())
        record = dict(notebook=path.name, status='passed', elapsed_s=perf_counter()-started,
                      code_cells=sum(c['cell_type'] == 'code' for c in notebook['cells']))
        if 'G' in namespace:
            graph = namespace['G']
            record.update(nodes=graph.number_of_nodes(), relationships=graph.number_of_edges())
            # Verify that the graph did not silently overwrite repeated relationships.
            expected = 0
            for row in namespace['RELS']:
                frame = namespace['tables'][row[0]]
                if len(row) == 5 and row[4]:
                    column, value = row[4]
                    frame = frame[frame[column] == value]
                expected += len(frame)
            assert graph.number_of_edges() == expected, (record, expected)
            record['source_relationship_rows'] = expected
            # Every relationship endpoint must correspond to an explicitly loaded node.
            assert all('label' in props for _, props in graph.nodes(data=True))
            for name, (_, key) in namespace['NODES'].items():
                frame = namespace['tables'][name]
                assert not frame[key].eq('').any(), (name, 'blank key')
                assert not frame[key].duplicated().any(), (name, 'duplicate key')
            actual_participations = sorted((u[1], v[1], data['role']) for u, v, data in graph.edges(data=True)
                                           if data['type'] == 'PARTICIPATES_IN')
            expected_participations = sorted((row.org_ref, row.iati_identifier, row.role)
                                             for row in namespace['tables']['rel_participates'].itertuples())
            assert actual_participations == expected_participations
            record['participation_roles_preserved'] = True
        if number == '03':
            result = namespace['results']
            assert len(result) == 10 and result['synthetic'].all()
            good = result[result.model == 'fake/echo-gold']
            bad = result[result.model == 'fake/bad-cypher']
            assert good['match'].all() and not bad['match'].any()
            record.update(synthetic_control_cases=len(result), live_model_runs=0)
        records.append(record)
        print(record)
    sources = [*sorted((fa26/'notebooks').glob('*.ipynb')), *sorted((fa26/'src').glob('*.py'))]
    result = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  generated_at=datetime.now(timezone.utc).isoformat(),
                  working_tree_changes=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
                  source_sha256={str(p.relative_to(fa26.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                  synthetic_only=True, notebooks=records)
    (output / 'offline_review_results.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
