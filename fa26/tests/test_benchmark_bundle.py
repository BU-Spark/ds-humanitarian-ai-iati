"""Public adapter checks and optional notebook integration (no live services)."""
import copy,json,os,sys,tempfile,unittest,contextlib
from pathlib import Path
from unittest.mock import patch
FA26=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(FA26/'src'));sys.path.insert(0,str(FA26/'benchmark/v2'))
from benchmark_bundle import load_bundle,submission,score_command
from export_inputs import export
from common import verify_snapshot

class AdapterTests(unittest.TestCase):
    def test_metadata_and_no_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=export(Path(tmp)/'bundle');b=load_bundle(p,verify_snapshot()['snapshot_id'])
            self.assertEqual(len(b['questions']),40)
            self.assertTrue(all(set(q)=={'id','question'} for q in b['questions']))
            result=submission(b,'fake/test',b['template']['snapshot_id'],[],True)
            self.assertEqual(result['split'],'development');self.assertTrue(result['synthetic'])
            self.assertIn('organisation_scope',b['reasons'])
    def test_tampered_inputs_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=export(Path(tmp)/'bundle');snapshot=verify_snapshot()['snapshot_id']
            q=json.loads((p/'questions.json').read_text());q[0]['contract']='secret'
            (p/'questions.json').write_text(json.dumps(q))
            with self.assertRaises(ValueError):load_bundle(p,snapshot)
            q[0].pop('contract');(p/'questions.json').write_text(json.dumps(q))
            with (p/'snapshot/nodes_activities.csv').open('a') as f:f.write('tampered')
            with self.assertRaises(ValueError):load_bundle(p,snapshot)
    def test_scorer_has_no_old_runs(self):
        b={'template':{'split':'development'}}
        cmd=score_command(sys.executable,FA26,['new.json'],'out',b)
        self.assertIn('development',cmd);self.assertNotIn('sqlite_baseline.json',' '.join(cmd))
    @unittest.skipUnless(os.environ.get('IATI_TEST_NOTEBOOKS')=='1','Set IATI_TEST_NOTEBOOKS=1 for fake-model notebook integration')
    def test_notebooks_all_modes(self):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'IATI_LIVE_EVAL':'0'}):
            for mode in ('v1','development','heldout','regression','all'):
                if mode=='v1':os.environ.pop('IATI_BENCHMARK_BUNDLE',None)
                else:os.environ['IATI_BENCHMARK_BUNDLE']=str(export(Path(tmp)/mode,mode))
                for num in ('05','06'):
                    path=next((FA26/'notebooks').glob(num+'_*.ipynb'));ns={'display':lambda *a:None}
                    with open(Path(tmp)/f'{mode}_{num}.log','w') as log,contextlib.redirect_stdout(log):
                        for i,c in enumerate(json.loads(path.read_text())['cells']):
                            if c['cell_type']=='code':exec(compile(''.join(c['source']),f'{path.name}:{i}','exec'),ns)
                    expected={'v1':20,'development':40,'heldout':40,'regression':20,'all':100}[mode]
                    for p in ns['submissions']:
                        result=json.loads(p.read_text());self.assertEqual(len(result['answers']),expected)
                        if mode!='v1':self.assertEqual(result['split'],mode)
                    if num=='05' and mode=='development':
                        calls=[]
                        def query(q):calls.append(q);raise RuntimeError('offline failure')
                        agent=ns['build_agent'](FakeListChatModel(responses=['not JSON']),query)
                        result=agent.invoke(dict(qid='X',question='test',contract='',value_type='auto',retries=0,model_calls=0))
                        self.assertEqual(result['model_calls'],3);self.assertEqual(result['facts'],{});self.assertFalse(calls)

if __name__=='__main__':unittest.main()
