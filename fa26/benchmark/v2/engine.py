"""Python and SQLite reference implementations; no network or model calls."""
import csv,sqlite3,sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from common import read_tables,verify_snapshot
from reference import calculate as legacy_python
from sql_baseline import calculate as legacy_sql
from catalog_v2 import QUESTIONS
BENCHMARK_ID='iati-v2-100-2026-10-29'

def match(row,filters):
    for name,want in filters.items():
        key,_,op=name.partition('__');v=row[key]
        if op=='negative':ok=Decimal(v)<0
        elif op=='positive':ok=Decimal(v)>0
        elif op=='zero':ok=Decimal(v)==0
        elif op=='ne':ok=v!=want
        elif op=='lt':ok=v<want
        elif op=='gte':ok=v>=want
        else:ok=v==want
        if not ok:return False
    return True

def python_rows(spec,tables):
    acts={a['iati_identifier']:a for a in tables['nodes_activities']};indexes={}
    for link in spec['links']:
        index=defaultdict(list)
        for r in tables[link.split('#')[0]]:index[r['iati_identifier']].append(r)
        indexes[link]=index
    for r in tables[spec['table']]:
        a=acts.get(r.get('iati_identifier'));joined={**(a or {}),**r}
        if not match(joined,spec['filters']):continue
        ev={r['_source']}
        if a:ev.add(a['_source'])
        for link,filters in spec['links'].items():
            found=[x for x in indexes[link].get(r.get('iati_identifier'),[]) if match(x,filters)]
            if not found:break
            ev.update(x['_source'] for x in found)
        else:yield joined,ev

def connect(tables):
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
    con.create_function('SIGN',1,lambda x:(Decimal(x)>0)-(Decimal(x)<0))
    for path in sorted((ROOT.parent/'snapshot').glob('*.csv')):
        with path.open() as stream:fields=next(csv.reader(stream))+['_source']
        con.execute(f'CREATE TABLE "{path.stem}" ('+','.join(f'"{f}" TEXT' for f in fields)+')')
        con.executemany(f'INSERT INTO "{path.stem}" VALUES ('+','.join('?' for _ in fields)+')',[[r[f] for f in fields] for r in tables[path.stem]])
        if 'iati_identifier' in fields:con.execute(f'CREATE INDEX "idx_{path.stem}" ON "{path.stem}"(iati_identifier)')
    return con

def conditions(filters,alias,params,fields=None):
    parts=[]
    for name,want in filters.items():
        key,_,op=name.partition('__');prefix='a' if fields is not None and key not in fields else alias;col=f'{prefix}."{key}"'
        if op in ('negative','positive','zero'):parts.append(f'SIGN({col}) '+{'negative':'<0','positive':'>0','zero':'=0'}[op])
        else:parts.append(col+{'':'=','ne':'<>','lt':'<','gte':'>='}[op]+'?');params.append(want)
    return ' AND '.join(parts) or '1'

def sql_rows(spec,con):
    table=spec['table'];fields=[r[1] for r in con.execute(f'PRAGMA table_info("{table}")')];joined='iati_identifier' in fields and table!='nodes_activities';params=[]
    where=conditions(spec['filters'],'r',params,set(fields))
    for i,(link,filters) in enumerate(spec['links'].items()):
        lt=link.split('#')[0];alias=f'l{i}';cond=conditions(filters,alias,params)
        where+=f' AND EXISTS(SELECT 1 FROM "{lt}" {alias} WHERE {alias}.iati_identifier=r.iati_identifier AND {cond})'
    select='r.*'+(',a._source AS activity_source,a.publisher AS publisher' if joined else '')
    sql=f'SELECT {select} FROM "{table}" r'+(' JOIN nodes_activities a ON a.iati_identifier=r.iati_identifier' if joined else '')+' WHERE '+where
    for row in con.execute(sql,params).fetchall():
        r=dict(row);ev={r['_source']}
        if joined:ev.add(r['activity_source'])
        for link,filters in spec['links'].items():
            params=[r['iati_identifier']];cond=conditions(filters,'l',params)
            ev.update(x[0] for x in con.execute(f'SELECT l._source FROM "{link.split("#")[0]}" l WHERE l.iati_identifier=? AND {cond}',params))
        yield r,ev

class DecimalSum:
    def __init__(self):self.total=Decimal(0)
    def step(self,x):self.total+=Decimal(x)
    def finalize(self):return str(self.total)

def facts(spec,rows,sql=False):
    groups=defaultdict(list);default='total' if spec['metric']=='sum' else 'date' if spec['metric'] in ('min','max') else 'count'
    for r,ev in rows:groups[r[spec['group']] if spec['group'] else default].append((r[spec['field']],ev))
    if not spec['group'] and not groups:groups[default]=[]
    result={}
    for key,items in sorted(groups.items()):
        vals=[v for v,_ in items]
        if sql:
            c=sqlite3.connect(':memory:');c.execute('CREATE TABLE v(x TEXT)');c.executemany('INSERT INTO v VALUES (?)',[(v,) for v in vals]);c.create_aggregate('DSUM',1,DecimalSum)
            expr={'sum':"COALESCE(DSUM(x),'0')",'count':'COUNT(DISTINCT x)','min':'MIN(x)','max':'MAX(x)'}[spec['metric']]
            value=c.execute('SELECT '+expr+' FROM v').fetchone()[0];c.close()
        elif spec['metric']=='sum':value=sum((Decimal(v) for v in vals),Decimal(0))
        elif spec['metric']=='count':value=len(set(vals))
        elif spec['metric']=='min':value=min(vals)
        else:value=max(vals)
        ev=sorted({e for _,es in items for e in es})
        if not ev:
            scope={spec['table'],*(k.split('#')[0] for k in spec['links'])}
            if 'publisher' in spec['filters']:scope.add('nodes_activities')
            ev=sorted('manifest:'+table+'.csv' for table in scope)
        result[key]=dict(value=str(value),evidence=ev)
    return result

def calculate(sql=False):
    tables=read_tables();con=connect(tables) if sql else None
    old={a['id']:a for a in (legacy_sql() if sql else legacy_python())['answers']};answers=[]
    for q in QUESTIONS:
        if q.get('legacy'):
            a=old[q['id']];answers.append(dict(id=a['id'],status=a['status'],facts=a['facts'],reasons=a.get('reasons',[])));continue
        a=dict(id=q['id'],status=q['status'],reasons=q['reasons'],facts={})
        if q['status']=='answer':a['facts']=facts(q['spec'],sql_rows(q['spec'],con) if sql else python_rows(q['spec'],tables),sql)
        answers.append(a)
    if con:con.close()
    return dict(benchmark_id=BENCHMARK_ID,snapshot_id=verify_snapshot()['snapshot_id'],answers=answers)

if __name__=='__main__':
    a=calculate();b=calculate(sql=True)
    assert a==b,'Python and SQLite disagree'
    print('Python and SQLite agree on all 100 answers and evidence sets.')
