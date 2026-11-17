"""V2 scorer. Preserves v1 weighting; compares structured answers, not prose."""
import argparse,importlib.util,json
from pathlib import Path
from statistics import mean
from engine import ROOT,BENCHMARK_ID,QUESTIONS,calculate
from common import load_json,save_json,verify_snapshot

# Load a private instance so adapting the catalog never changes v1 globals.
spec=importlib.util.spec_from_file_location('_v2_legacy_score',ROOT.parent/'score.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)

def selection(split):
    return [q for q in QUESTIONS if split=='all' or q['split']==split]

def summarize(rows):
    def avg(key):
        values=[r[key] for r in rows if r.get(key) is not None]
        return round(100*mean(values),2) if values else None
    lat=[r['latency_ms'] for r in rows if r.get('latency_ms') is not None]
    return dict(questions=len(rows),correctness_pct=avg('correctness'),evidence_f1_pct=avg('evidence_f1'),behavior_pct=avg('behavior'),overall_pct=avg('score'),latency_samples=len(lat),mean_latency_ms=mean(lat) if lat else None)

def evaluate(submission,reference,split='all'):
    if submission.get('benchmark_id')!=BENCHMARK_ID:raise ValueError('Wrong benchmark_id')
    if submission.get('split')!=split:raise ValueError('Wrong split')
    qs=selection(split)
    legacy.QUESTIONS=[(q['id'],q['category'],q['question'],q['value_type'],q['contract']) for q in qs]
    legacy.validate(submission,reference)
    ref={a['id']:a for a in reference['answers']};actual={a['id']:a for a in submission['answers']};rows=[]
    known_evidence=set()
    manifest=verify_snapshot()
    # Evidence must refer to a row in the pinned inventory or a manifest table.
    import csv
    for name in manifest['files']:
        known_evidence.add('manifest:'+name)
        with (ROOT.parent/'snapshot'/name).open() as f:
            count=sum(1 for _ in csv.DictReader(f))
        known_evidence.update(f'{name}:row:{i}' for i in range(1,count+1))
    for a in submission['answers']:
        for fact in a['facts'].values():
            if any(e not in known_evidence for e in fact.get('evidence',[])):raise ValueError('Unknown evidence ID')
    for q in qs:
        gold=ref[q['id']];a=actual.get(q['id']);row=dict(id=q['id'],category=q['category'],split=q['split'],submitted=a is not None,correctness=0.,evidence_f1=None,behavior=None,score=0.,latency_ms=a.get('latency_ms') if a else None)
        if q['value_type']=='unsupported':
            score=0.
            if a and a['status']==gold['status'] and not a['facts']:
                wanted=set(gold['reasons']);given=set(a.get('reasons',[]));score=legacy.f1(len(wanted&given),len(wanted),len(given))
            row.update(correctness=score,behavior=score,score=score)
        else:
            good=set();facts=a['facts'] if a else {};expected=gold['facts']
            if a and a['status']==gold['status'] and not a.get('reasons'):
                good={k for k,v in facts.items() if k in expected and legacy.equal_value(v['value'],expected[k]['value'],q['value_type'])}
            correctness=legacy.f1(len(good),len(facts),len(expected)) if a and a['status']=='answer' and not a.get('reasons') else 0.
            ev=[]
            for k in set(facts)|set(expected):
                found=set(facts.get(k,{}).get('evidence',[]));needed=set(expected.get(k,{}).get('evidence',[]))
                ev.append(legacy.f1(len(found&needed),len(found),len(needed)) if k in good and correctness>0 else 0.)
            evidence=mean(ev) if ev else 0.
            row.update(correctness=correctness,evidence_f1=evidence,score=.7*correctness+.3*evidence)
        rows.append(row)
    cost=submission.get('cost_usd')
    if cost is not None:
        import math
        if isinstance(cost,bool) or not isinstance(cost,(int,float)) or not math.isfinite(cost) or cost<0:raise ValueError('Invalid cost_usd')
    return dict(run_name=submission['run_name'],synthetic=submission.get('synthetic',False),summary=summarize(rows),cost_usd=cost,by_category={k:summarize([r for r in rows if r['category']==k]) for k in sorted({r['category'] for r in rows})},by_split={k:summarize([r for r in rows if r['split']==k]) for k in sorted({r['split'] for r in rows})},questions=rows)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('submissions',nargs='+',type=Path);parser.add_argument('--split',choices=['all','regression','development','heldout'],default='all');parser.add_argument('--output',type=Path,default=ROOT/'results'/'live');args=parser.parse_args()
    reference=calculate()
    if reference!=load_json(ROOT/'reference_answers.json'):raise ValueError('Stale reference answers; rebuild and review')
    runs=[evaluate(load_json(p),reference,args.split) for p in args.submissions]
    if len({r['run_name'] for r in runs})!=len(runs):raise ValueError('Duplicate run names')
    save_json(args.output/'comparison.json',dict(benchmark_id=BENCHMARK_ID,snapshot_id=reference['snapshot_id'],split=args.split,runs=runs))
    import csv
    args.output.mkdir(parents=True,exist_ok=True)
    with (args.output/'comparison.csv').open('w',newline='') as f:
        fields=['run_name','cost_usd',*runs[0]['summary']];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in runs:w.writerow(dict(run_name=r['run_name'],cost_usd=r['cost_usd'],**r['summary']))
    print(json.dumps([{k:v for k,v in r.items() if k!='questions'} for r in runs],indent=2))
if __name__=='__main__':main()
