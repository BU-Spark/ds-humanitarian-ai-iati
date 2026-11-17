import copy,json,tempfile,unittest
from collections import Counter
from pathlib import Path
from engine import QUESTIONS,ROOT,BENCHMARK_ID,calculate
from common import read_tables,verify_snapshot
from score_v2 import evaluate
from export_inputs import export
from build import public

class BenchmarkV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref=calculate();cls.sql=calculate(True);cls.good=dict(cls.sql,split='all',run_name='synthetic/test',synthetic=True)
    def test_independent_calculations_and_saved_reference(self):
        self.assertEqual(self.ref,self.sql)
        self.assertEqual(self.ref,json.loads((ROOT/'reference_answers.json').read_text()))
    def test_inventory(self):
        self.assertEqual(len({q['id'] for q in QUESTIONS}),100)
        self.assertEqual(Counter(q['split'] for q in QUESTIONS),dict(regression=20,development=40,heldout=40))
        self.assertEqual(Counter(q['category'] for q in QUESTIONS if not q.get('legacy')),dict(direct=20,two_step=20,organisation=15,financial=15,limitations=10))
        families={}
        for q in QUESTIONS:
            self.assertIn(q['split'],('regression','development','heldout'))
            self.assertEqual(families.setdefault(q['family'],q['split']),q['split'])
    def test_baseline_perfect(self):self.assertEqual(evaluate(self.good,self.ref)['summary']['overall_pct'],100)
    def test_v1_results_unchanged(self):
        from reference import calculate as old
        from score import evaluate as old_score
        v1=old();s=dict(v1,run_name='baseline')
        result=evaluate(dict(self.good,split='regression',answers=self.good['answers'][:20]),self.ref,'regression')
        self.assertEqual(result['summary']['overall_pct'],old_score(s,v1)['summary']['overall_pct'])
    def test_no_evidence_reduces_score(self):
        s=copy.deepcopy(self.good)
        for a in s['answers']:
            for f in a['facts'].values():f['evidence']=[]
        self.assertLess(evaluate(s,self.ref)['summary']['overall_pct'],100)
    def test_wrong_values_get_no_credit_even_with_correct_evidence(self):
        s=copy.deepcopy(self.good)
        for a in s['answers']:
            for fact in a['facts'].values():fact['value']='not-a-number-or-date'
        scored=evaluate(s,self.ref)
        for row in scored['questions']:
            if row['evidence_f1'] is not None:self.assertEqual(row['score'],0)
    def test_numeric_precision_and_invalid_values(self):
        from score_v2 import legacy
        self.assertTrue(legacy.equal_value('10.009','10.00','decimal'))
        self.assertFalse(legacy.equal_value('10.02','10.00','decimal'))
        for value in (True,'NaN','Infinity'):
            self.assertFalse(legacy.equal_value(value,'10','decimal'))
    def test_date_boundaries_and_repeated_relationship_rows(self):
        from engine import match,python_rows
        self.assertTrue(match({'date':'2022-01-01'},{'date__gte':'2022-01-01','date__lt':'2023-01-01'}))
        self.assertFalse(match({'date':'2023-01-01'},{'date__gte':'2022-01-01','date__lt':'2023-01-01'}))
        activity={'iati_identifier':'A','publisher':'wfp','_source':'nodes_activities.csv:row:1'}
        links=[{'iati_identifier':'A','role':'1','_source':f'rel_participates.csv:row:{i}'} for i in (1,2)]
        spec=dict(table='nodes_activities',filters={},links={'rel_participates':{'role':'1'}})
        rows=list(python_rows(spec,{'nodes_activities':[activity],'rel_participates':links}))
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0][1]),3)
    def test_missing_answers_are_zero(self):
        self.assertEqual(evaluate(dict(self.good,answers=[]),self.ref)['summary']['overall_pct'],0)
    def test_false_answers_to_ambiguous_questions_fail(self):
        s=copy.deepcopy(self.good)
        a=next(a for a in s['answers'] if a['status']=='clarify');qid=a['id'];a.update(status='answer',facts={'count':{'value':0,'evidence':[]}},reasons=[])
        self.assertEqual(next(r for r in evaluate(s,self.ref)['questions'] if r['id']==qid)['score'],0)
    def test_invalid_metadata_ids_and_values(self):
        for change in [lambda s:s.update(benchmark_id='v1'),lambda s:s.update(snapshot_id='wrong'),lambda s:s.update(split='heldout'),lambda s:s['answers'].append(s['answers'][0]),lambda s:s['answers'][0].update(id='unknown'),lambda s:s['answers'][0].update(latency_ms=-1),lambda s:s.update(cost_usd=float('nan'))]:
            s=copy.deepcopy(self.good);change(s)
            with self.assertRaises(ValueError):evaluate(s,self.ref)
    def test_unknown_evidence_rejected(self):
        s=copy.deepcopy(self.good);next(iter(s['answers'][0]['facts'].values()))['evidence']=['nodes_activities.csv:row:999999']
        with self.assertRaises(ValueError):evaluate(s,self.ref)
    def test_export_does_not_disclose_answers_or_heldout(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=export(Path(tmp)/'inputs');qs=json.loads((p/'questions.json').read_text());self.assertEqual(len(qs),40)
            self.assertTrue(all(set(q)=={'id','question'} for q in qs))
            self.assertEqual({q['id'] for q in qs},{q['id'] for q in QUESTIONS if q['split']=='development'})
            self.assertEqual({f.name for f in p.iterdir()},{'snapshot','manifest.json','questions.json','submission_template.json','README.md'})
            with self.assertRaises(ValueError):export(p)
    def test_direct_counts_and_role_preservation(self):
        answers={a['id']:a for a in self.ref['answers']};tables=read_tables()
        self.assertEqual(answers['V2Q001']['facts']['count']['value'],'505')
        roles=[q for q in QUESTIONS if q['family']=='organisation-role-counts']
        for q in roles:
            role=q['spec']['links']['rel_participates']['role']
            ids={r['iati_identifier'] for r in tables['rel_participates'] if r['org_ref']=='GB-CHC-202918' and r['role']==role}
            self.assertEqual(int(answers[q['id']]['facts']['count']['value']),len(ids))
    def test_zero_financial_answers_have_manifest_evidence(self):
        answers={a['id']:a for a in self.ref['answers']}
        for q in QUESTIONS:
            if 'EUR expenditure' in q['question'] or 'dated before 2000' in q['question']:
                fact=answers[q['id']]['facts']['total'];self.assertEqual(fact['value'],'0');self.assertTrue(all(e.startswith('manifest:') for e in fact['evidence']))
    def test_groups_separate_currencies(self):
        answers={a['id']:a for a in self.ref['answers']}
        for q in QUESTIONS:
            if q.get('spec',{}).get('group')=='currency':self.assertEqual(set(answers[q['id']]['facts']),{'USD','GBP'})

if __name__=='__main__':unittest.main()
