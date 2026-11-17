"""Independent SQL aggregation baseline. Does not read reference_answers.json."""
import sqlite3
import time
from decimal import Decimal
from common import ROOT, read_tables, save_json, verify_snapshot
from catalog import QUESTIONS

# Each query produces observations: fact key, item to aggregate, two source IDs.
QUERIES={
 'Q01': 'SELECT publisher k,iati_identifier item,_source s1,NULL s2 FROM nodes_activities',
 'Q02': "SELECT a.publisher k,r.country_code item,r._source s1,a._source s2 FROM rel_targets_country r JOIN nodes_activities a USING(iati_identifier) WHERE r.is_hotspot='true'",
 'Q03': "SELECT a.publisher k,a.iati_identifier item,r._source s1,a._source s2 FROM rel_targets_country r JOIN nodes_activities a USING(iati_identifier) WHERE r.country_code='SO'",
 'Q04': 'SELECT r.org_ref k,a.iati_identifier item,r._source s1,a._source s2 FROM rel_participates r JOIN nodes_activities a USING(iati_identifier) WHERE r.org_ref IN (SELECT p.org_ref FROM rel_participates p JOIN nodes_activities b USING(iati_identifier) GROUP BY p.org_ref HAVING COUNT(DISTINCT b.publisher)>=2)',
 'Q05': 'SELECT role k,org_ref item,_source s1,NULL s2 FROM rel_participates',
 'Q06': 'SELECT match_basis k,iati_identifier item,_source s1,NULL s2 FROM nodes_activities',
 'Q07': "SELECT 'count' k,a.iati_identifier item,r._source s1,a._source s2 FROM rel_classified_as r JOIN nodes_activities a USING(iati_identifier) WHERE a.publisher='wfp' AND r.sector_key='1:72040'",
 'Q08': "SELECT publisher k,iati_identifier item,_source s1,NULL s2 FROM nodes_activities WHERE COALESCE(NULLIF(start_actual,''),start_planned)>='2020-01-01' AND COALESCE(NULLIF(start_actual,''),start_planned)<'2026-01-01'",
 'Q09': "SELECT publisher k,SUBSTR(last_updated,1,10) item,_source s1,NULL s2 FROM nodes_activities WHERE last_updated<>''",
 'Q10': "SELECT 'total' k,t.value item,t._source s1,a._source s2 FROM nodes_transactions t JOIN nodes_activities a USING(iati_identifier) WHERE a.publisher='wfp' AND t.type='1' AND t.currency='USD' AND t.date>='2020-01-01' AND t.date<'2021-01-01'",
 'Q11': "SELECT 'total' k,t.value item,t._source s1,a._source s2 FROM nodes_transactions t JOIN nodes_activities a USING(iati_identifier) WHERE a.publisher='oxfamgb' AND t.type='3' AND t.currency='GBP' AND t.date>='2020-01-01' AND t.date<'2021-01-01'",
 'Q12': "SELECT 'total' k,t.value item,t._source s1,a._source s2 FROM nodes_transactions t JOIN nodes_activities a USING(iati_identifier) WHERE a.publisher='oxfamus' AND t.type='4' AND t.currency='USD'",
 'Q13': 'SELECT a.publisher k,t.tx_id item,t._source s1,a._source s2 FROM nodes_transactions t JOIN nodes_activities a USING(iati_identifier) WHERE IS_NEGATIVE(t.value)=1',
 'Q14': "SELECT 'total' k,value item,_source s1,NULL s2 FROM nodes_budgets WHERE type='1' AND status='2' AND currency='USD'",
 'Q15': 'SELECT sdg_key k,iati_identifier item,_source s1,NULL s2 FROM rel_contributes_to',
 'Q16': 'SELECT a.publisher k,a.iati_identifier item,r._source s1,a._source s2 FROM rel_located_at r JOIN nodes_activities a USING(iati_identifier)',
}


class DecimalSum:
    def __init__(self): self.value=Decimal(0)
    def step(self,value): self.value+=Decimal(value)
    def finalize(self): return str(self.value)


def calculate():
    con=sqlite3.connect(':memory:')
    con.create_aggregate('DECIMAL_SUM',1,DecimalSum)
    con.create_function('IS_NEGATIVE',1,lambda value:int(Decimal(value)<0))
    for name,rows in read_tables().items():
        if not rows: continue
        fields=list(rows[0])
        con.execute(f'CREATE TABLE "{name}" ('+','.join(f'"{f}" TEXT' for f in fields)+')')
        con.executemany(f'INSERT INTO "{name}" VALUES ('+','.join('?' for _ in fields)+')',[[r[f] for f in fields] for r in rows])
    answers=[]
    for qid,_,_,kind,contract in QUESTIONS:
        start=time.perf_counter()
        if kind=='unsupported':
            status,reasons,_=contract.split('|')
            answer=dict(id=qid,status=status,reasons=reasons.split(','),facts={})
        else:
            query=QUERIES[qid]
            aggregate='DECIMAL_SUM(item)' if kind=='decimal' else 'MAX(item)' if kind=='date' else 'COUNT(DISTINCT item)'
            facts={str(k):dict(value=str(v),evidence=[]) for k,v in con.execute(f'SELECT k,{aggregate} FROM ({query}) GROUP BY k')}
            if not facts and qid in ['Q07','Q10','Q11','Q12','Q14']:
                facts['count' if qid=='Q07' else 'total']=dict(value='0',evidence=[])
            for k in facts:
                facts[k]['evidence']=sorted({s for row in con.execute(f'SELECT s1,s2 FROM ({query}) WHERE k=?',(k,)) for s in row if s})
                if not facts[k]['evidence']:
                    scope=['rel_classified_as.csv','nodes_activities.csv'] if qid=='Q07' else ['nodes_budgets.csv'] if qid=='Q14' else ['nodes_transactions.csv','nodes_activities.csv']
                    facts[k]['evidence']=sorted('manifest:'+name for name in scope)
            answer=dict(id=qid,status='answer',reasons=[],facts=facts)
        answer['latency_ms']=round((time.perf_counter()-start)*1000,3)
        answers.append(answer)
    con.close()
    return dict(run_name='sqlite_baseline_not_an_LLM',snapshot_id=verify_snapshot()['snapshot_id'],answers=answers)


if __name__=='__main__':
    save_json(ROOT/'runs/sqlite_baseline.json',calculate())
    print('Saved independent SQL baseline')
