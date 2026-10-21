"""Reproduce George-branch findings offline against the pinned benchmark snapshot.

Original notebooks are read from the exact Git commit, never checked out or edited.
Only their setup paths are supplied by this runner; all graph-building cells are
executed unchanged. No live notebook/provider initialization is executed.
"""
import contextlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile

import networkx as nx
import pandas as pd
from langchain_core.language_models.fake_chat_models import FakeListChatModel

ROOT = Path(__file__).resolve().parents[2]
GEORGE_COMMIT = 'e86605bf92f8c5aa98cbb165a3ecf8820b735df1'


def notebook(number):
    files = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', GEORGE_COMMIT], cwd=ROOT, text=True).splitlines()
    path, = [p for p in files if p.startswith('fa26/notebooks/' + number + '_') and p.endswith('.ipynb')]
    return json.loads(subprocess.check_output(['git', 'show', GEORGE_COMMIT + ':' + path], cwd=ROOT))


def main():
    import sys
    sys.path.insert(0, str(ROOT / 'fa26' / 'benchmark'))
    from common import verify_snapshot
    result = dict(george_commit=GEORGE_COMMIT, snapshot_id=verify_snapshot()['snapshot_id'],
                  live_model_runs=0, original_notebooks={})
    with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
        for number in ('01', '02'):
            namespace = dict(pd=pd, nx=nx, Path=Path, GRAPH_DIR=ROOT/'fa26'/'benchmark'/'snapshot',
                             INTERIM=Path(temp), display=lambda *args: None)
            if number == '02':
                namespace['tables'] = {p.stem: pd.read_csv(p, dtype=str, keep_default_na=False)
                                       for p in namespace['GRAPH_DIR'].glob('*.csv')}
            for index, cell in enumerate(notebook(number)['cells']):
                if cell['cell_type'] == 'code' and index != 2:
                    exec(''.join(cell['source']), namespace)
            graph = namespace['G']
            result['original_notebooks'][number] = dict(nodes=graph.number_of_nodes(),
                relationships=graph.number_of_edges(), isolated_nodes=len(list(nx.isolates(graph))))
        participants = namespace['tables']['rel_participates']
        collapsed = len(participants) - len(participants.drop_duplicates(['org_ref', 'iati_identifier']))
        conflicting = participants.groupby(['org_ref', 'iati_identifier'])['role'].nunique()
        result['participation_relationships'] = dict(source_rows=len(participants), overwritten_rows=collapsed,
                                                     endpoint_pairs_with_multiple_roles=int((conflicting > 1).sum()))
        original = dict(re=re, json=json)
        exec(''.join(notebook('03')['cells'][12]['source']), original)
        result['original_guard_allows_custom_procedure'] = not bool(original['FORBIDDEN'].search('MATCH (n) CALL custom.proc() RETURN n'))
        original.update(SCHEMA='(:Activity)', time=__import__('time'))
        def execute(query):
            if query == 'RETURN 0 AS empty':
                return []
            raise ValueError('invalid query')
        graph = original['build_graph'](FakeListChatModel(responses=['RETURN (']), execute)
        state = graph.invoke(dict(question='test', gold_cypher='RETURN 0 AS empty', retries=0))
        result['original_execution_failure_marked_correct_when_gold_empty'] = state['match']
        graph = original['build_graph'](FakeListChatModel(responses=['MATCH (n) DELETE n']), execute)
        try:
            graph.invoke(dict(question='test', gold_cypher='RETURN 0 AS empty', retries=0))
        except Exception as exc:
            result['original_guard_terminal_failure'] = type(exc).__name__
    output = ROOT / 'fa26' / 'analysis' / 'george_review_results.json'
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
