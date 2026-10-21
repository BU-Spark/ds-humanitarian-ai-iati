"""Behavioral regression checks for benchmark correctness and scoring."""
import copy
import csv
import hashlib
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
import common
from common import ROOT, load_json, read_tables
from reference import calculate
from score import evaluate, equal_value
from sql_baseline import calculate as sql_calculate


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref=calculate()
        cls.base=sql_calculate()

    def test_independent_sql_matches_all_values_and_evidence(self):
        self.assertEqual(len(self.ref['answers']),20)
        for r,a in zip(self.ref['answers'],self.base['answers']):
            self.assertEqual(r['id'],a['id'])
            for field in ['status','facts','reasons']: self.assertEqual(r[field],a[field],(r['id'],field))
        self.assertEqual(evaluate(self.base,self.ref)['summary']['overall_pct'],100)

    def test_known_counts_and_money_independent_decimal_loop(self):
        facts={a['id']:a['facts'] for a in self.ref['answers']}
        self.assertEqual({k:v['value'] for k,v in facts['Q01'].items()},{'oxfamgb':'412','oxfamus':'11','wfp':'82'})
        t=read_tables();ids={r['iati_identifier'] for r in t['nodes_activities'] if r['publisher']=='oxfamgb'}
        values=[Decimal(r['value']) for r in t['nodes_transactions'] if r['iati_identifier'] in ids and r['type']=='3' and r['currency']=='GBP' and r['date'].startswith('2020-')]
        self.assertTrue(values)
        self.assertEqual(Decimal(facts['Q11']['total']['value']),sum(values))
        self.assertEqual({k:v['value'] for k,v in facts['Q13'].items()},{'oxfamgb':'2102','wfp':'3235'})

    def test_precision_and_numeric_attack_values(self):
        self.assertTrue(equal_value('100.01','100','decimal'))
        self.assertFalse(equal_value('100.02','100','decimal'))
        self.assertFalse(equal_value('11.01','11','integer'))
        for bad in ['NaN','Infinity','-Infinity',True,None,{},[]]: self.assertFalse(equal_value(bad,'11','integer'))

    def test_wrong_answer_with_correct_citations_gets_no_credit(self):
        run=copy.deepcopy(self.base)
        for fact in run['answers'][0]['facts'].values(): fact['value']='999999'
        scored=evaluate(run,self.ref)['questions'][0]
        self.assertEqual(scored['correctness'],0)
        self.assertEqual(scored['evidence_f1'],0)

    def test_missing_extra_and_partial_facts_are_penalized(self):
        run=copy.deepcopy(self.base)
        run['answers'][0]['facts'].pop('wfp')
        self.assertLess(evaluate(run,self.ref)['questions'][0]['correctness'],1)
        run['answers'][0]['facts']['invented']={'value':'1','evidence':[]}
        self.assertLess(evaluate(run,self.ref)['questions'][0]['correctness'],.8)
        run['answers']=[]
        self.assertEqual(evaluate(run,self.ref)['summary']['overall_pct'],0)

    def test_evidence_spam_partial_and_repeated_sources(self):
        run=copy.deepcopy(self.base);fact=run['answers'][0]['facts']['oxfamus']
        original=fact['evidence'][:]
        fact['evidence']=original+original
        self.assertEqual(evaluate(run,self.ref)['questions'][0]['evidence_f1'],1)
        fact['evidence']=original+['invented.csv:row:1']
        self.assertLess(evaluate(run,self.ref)['questions'][0]['evidence_f1'],1)
        fact['evidence']=original[:1]
        self.assertLess(evaluate(run,self.ref)['questions'][0]['evidence_f1'],1)

    def test_abstention_requires_reason_and_no_claims(self):
        run=copy.deepcopy(self.base)
        run['answers'][16]['reasons']=[]
        self.assertEqual(evaluate(run,self.ref)['questions'][16]['behavior'],0)
        run=copy.deepcopy(self.base)
        run['answers'][16]['facts']={'country':{'value':'Sudan','evidence':[]}}
        self.assertEqual(evaluate(run,self.ref)['questions'][16]['behavior'],0)
        run=copy.deepcopy(self.base)
        run['answers'][18]['status']='abstain'
        self.assertEqual(evaluate(run,self.ref)['questions'][18]['behavior'],0)

    def test_snapshot_id_duplicates_unknown_and_latency_validation(self):
        for mutate in [lambda r:r.update(snapshot_id='wrong'),lambda r:r['answers'].append(r['answers'][0]),lambda r:r['answers'][0].update(id='Q99'),lambda r:r['answers'][0].update(latency_ms=-1),lambda r:r['answers'][0].update(latency_ms=float('nan'))]:
            run=copy.deepcopy(self.base);mutate(run)
            with self.assertRaises(ValueError): evaluate(run,self.ref)

    def test_snapshot_hash_tampering_detected_without_touching_snapshot(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='test-snapshot-') as temp:
            dest=Path(temp)
            for name in load_json(ROOT/'manifest.json')['files']:
                (dest/name).write_bytes((common.SNAPSHOT/name).read_bytes())
            with (dest/'nodes_activities.csv').open('ab') as f:f.write(b'\n')
            with patch.object(common,'SNAPSHOT',dest),self.assertRaisesRegex(ValueError,'hash mismatch'):common.verify_snapshot()

    def test_all_evidence_resolves_and_zero_count_has_scope(self):
        tables=read_tables()
        valid={r['_source'] for rows in tables.values() for r in rows}
        valid|={'manifest:'+name for name in load_json(ROOT/'manifest.json')['files']}
        for a in self.ref['answers']:
            for fact in a['facts'].values():
                self.assertTrue(fact['evidence'])
                self.assertTrue(set(fact['evidence'])<=valid)
        q10=self.ref['answers'][9]['facts']['total']
        self.assertEqual(q10['value'],'0')
        self.assertTrue(all(x.startswith('manifest:') for x in q10['evidence']))

    def test_synthetic_controls(self):
        self.assertEqual(evaluate(load_json(ROOT/'runs/deliberately_wrong.json'),self.ref)['summary']['overall_pct'],0)
        no_evidence=evaluate(load_json(ROOT/'runs/no_evidence.json'),self.ref)['summary']
        self.assertEqual(no_evidence['correctness_pct'],100)
        self.assertEqual(no_evidence['evidence_f1_pct'],0)
        self.assertEqual(no_evidence['overall_pct'],76)


if __name__=='__main__': unittest.main(verbosity=2)
