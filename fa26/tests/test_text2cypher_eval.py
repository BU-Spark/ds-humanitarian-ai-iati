"""Offline regression tests; no model API or database connection."""
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from text2cypher_eval import build_graph, guard_query, extract_cypher, read_executor, model_registry
from langchain_core.language_models.fake_chat_models import FakeListChatModel


class EvaluationTests(unittest.TestCase):
    def test_registry_never_defaults_another_providers_key_to_openai(self):
        with self.assertRaisesRegex(ValueError, 'BASE_URL'):
            model_registry(dict(GROQ_API_KEY='test-secret', GROQ_MODEL='test-model'))

    def test_registry_metadata_contains_no_credentials(self):
        models = model_registry(dict(GROQ_API_KEY='test-secret', GROQ_MODEL='test-model', GROQ_BASE_URL='https://example.com/v1'))
        self.assertEqual(models[0]['key_env'], 'GROQ_API_KEY')
        self.assertNotIn('test-secret', str(models))

    def invoke(self, responses, executor):
        graph = build_graph(FakeListChatModel(responses=responses), executor, '(:Activity)')
        return graph.invoke(dict(question='Count activities', gold_cypher='RETURN 1 AS count', retries=0))

    def test_extract_fenced_and_plain(self):
        self.assertEqual(extract_cypher('```cypher\nRETURN 1;\n```'), 'RETURN 1')
        self.assertEqual(extract_cypher('RETURN 1;'), 'RETURN 1')

    def test_reject_writes_procedures_and_obfuscation(self):
        for query in ['MATCH (n) DETACH DELETE n', 'MATCH (n) CALL custom.proc() RETURN n',
                      'RETURN 1; RETURN 2', 'MATCH (n) CALL/**/db.labels() RETURN n',
                      'MATCH (n) SET n.x=1 RETURN n', 'MATCH (`n`) RETURN `n`']:
            with self.subTest(query=query), self.assertRaises(ValueError):
                guard_query(query)

    def test_normal_read_allowed(self):
        guard_query("MATCH (a:Activity) WHERE a.publisher = 'wfp' RETURN count(a) AS count")

    def test_guard_failure_never_executes_or_matches_empty_gold(self):
        executor = MagicMock(return_value=[])
        result = self.invoke(['MATCH (n) DELETE n'], executor)
        self.assertFalse(result['match'])
        self.assertEqual(result['retries'], 1)
        executor.assert_not_called()

    def test_execution_failure_never_matches_empty_gold(self):
        executor = MagicMock(side_effect=ValueError('invalid syntax'))
        result = self.invoke(['RETURN ('], executor)
        self.assertFalse(result['match'])
        self.assertEqual(executor.call_count, 2)
        self.assertEqual(result['error'], 'execution:ValueError')

    def test_retry_recovers_and_tracks_total_generation(self):
        result = self.invoke(['MATCH (n) DELETE n', 'RETURN 1 AS count'], lambda q: [{'count': 1}])
        self.assertTrue(result['match'])
        self.assertEqual(result['retries'], 1)
        self.assertGreater(result['generation_s'], 0)

    def test_reference_error_is_distinct(self):
        def executor(query):
            if query == 'RETURN 1 AS count':
                raise ValueError('reference failed')
            return [{'count': 1}]
        result = self.invoke(['RETURN 2 AS count'], executor)
        self.assertFalse(result['match'])
        self.assertEqual(result['error'], 'reference:ValueError')

    def test_alias_mismatch_remains_explicit(self):
        result = self.invoke(['RETURN 1 AS total'], lambda q: [{'total': 1}] if 'total' in q else [{'count': 1}])
        self.assertFalse(result['match'])

    def test_read_executor_requests_read_routing_timeout_and_limits(self):
        from neo4j import READ_ACCESS
        driver = MagicMock()
        session = driver.session.return_value.__enter__.return_value
        session.run.return_value = iter([{'x': 1}, {'x': 2}])
        with self.assertRaisesRegex(ValueError, 'row limit'):
            read_executor(driver, 'evaluation', timeout=4, max_rows=1)('RETURN 1')
        driver.session.assert_called_with(database='evaluation', default_access_mode=READ_ACCESS)
        self.assertEqual(session.run.call_args.args[0].timeout, 4)

    def test_generation_error_does_not_leak_error_text(self):
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError('secret-like provider error body')
        graph = build_graph(llm, MagicMock(), 'schema')
        result = graph.invoke(dict(question='test', gold_cypher='RETURN 1', retries=0))
        self.assertFalse(result['match'])
        self.assertNotIn('secret-like', str(result))

    @unittest.skip('notebook 04 is retired; the team loader is fa26/retrieval/load_neo4j.py, tested in fa26/retrieval/tests')
    def test_loader_preserves_distinct_source_rows_and_shared_codelists(self):
        import pandas as pd
        from iati_codelists import ORG_TYPE
        root = Path(__file__).resolve().parents[1]
        path, = (root/'notebooks').glob('04_*.ipynb')
        notebook = json.loads(path.read_text())
        driver = MagicMock()
        namespace = dict(sys=sys, FA26=root, pd=pd, driver=driver, DB='evaluation')
        exec(''.join(notebook['cells'][2]['source']), namespace)
        self.assertEqual(namespace['ORG_TYPE'], ORG_TYPE)
        namespace['NODES'] = {}
        namespace['RELS'] = [('rel_participates', 'PARTICIPATES_IN', 'Organisation', 'org_ref', 'ref',
                              'Activity', 'iati_identifier', 'iati_identifier', None)]
        namespace['tables'] = {'rel_participates': pd.DataFrame([
            dict(org_ref='org', iati_identifier='act', role='1', source_id='rel_participates.csv:row:1'),
            dict(org_ref='org', iati_identifier='act', role='4', source_id='rel_participates.csv:row:2')])}
        exec(''.join(notebook['cells'][4]['source']), namespace)
        call = driver.session.return_value.__enter__.return_value.run.call_args
        self.assertIn('source_id: r.source_id', call.args[0])
        self.assertEqual([row['p']['role'] for row in call.kwargs['rows']], ['1', '4'])
        self.assertEqual(len({row['source_id'] for row in call.kwargs['rows']}), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
