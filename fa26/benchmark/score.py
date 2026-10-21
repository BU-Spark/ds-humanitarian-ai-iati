"""Score structured model/agent submissions; never calls or judges with an LLM."""
import argparse
import csv
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean
from catalog import QUESTIONS
from common import ROOT, load_json, save_json, verify_snapshot


def f1(correct, predicted, expected):
    return 2*correct/(predicted+expected) if predicted+expected else 1.0


def equal_value(actual, expected, kind):
    if isinstance(actual,bool) or not isinstance(actual,(str,int,float)): return False
    if kind=='date': return isinstance(actual,str) and actual==expected
    try:
        a,b=Decimal(str(actual)),Decimal(str(expected))
        if not a.is_finite() or not b.is_finite(): return False
        return abs(a-b)<=Decimal('0.01') if kind=='decimal' else a==b
    except InvalidOperation:
        return False


def validate(submission, reference):
    if not isinstance(submission,dict): raise ValueError('Submission must be an object')
    if submission.get('snapshot_id')!=reference['snapshot_id']: raise ValueError('Wrong or missing snapshot_id')
    if not isinstance(submission.get('run_name'),str) or not submission['run_name'].strip(): raise ValueError('run_name is required')
    answers=submission.get('answers')
    if not isinstance(answers,list): raise ValueError('answers must be a list')
    known={q[0] for q in QUESTIONS}; seen=set()
    for a in answers:
        if not isinstance(a,dict): raise ValueError('Each answer must be an object')
        qid=a.get('id')
        if not isinstance(qid,str) or qid not in known or qid in seen: raise ValueError('Unknown or duplicate question ID')
        seen.add(qid)
        if a.get('status') not in ['answer','abstain','clarify']: raise ValueError('Invalid status')
        if not isinstance(a.get('facts'),dict): raise ValueError('facts must be an object')
        reasons=a.get('reasons',[])
        if not isinstance(reasons,list) or any(not isinstance(x,str) for x in reasons): raise ValueError('reasons must be a string list')
        for key,fact in a['facts'].items():
            if not isinstance(key,str) or not isinstance(fact,dict) or 'value' not in fact: raise ValueError('Invalid fact')
            evidence=fact.get('evidence',[])
            if not isinstance(evidence,list) or any(not isinstance(x,str) for x in evidence): raise ValueError('evidence must be a string list')
        latency=a.get('latency_ms')
        if latency is not None and (isinstance(latency,bool) or not isinstance(latency,(int,float)) or not math.isfinite(latency) or latency<0): raise ValueError('latency_ms must be finite and nonnegative, or null')


def evaluate(submission,reference):
    validate(submission,reference)
    submitted={a['id']:a for a in submission['answers']}
    expected={a['id']:a for a in reference['answers']}
    rows=[]
    for qid,category,_,kind,_ in QUESTIONS:
        r=expected[qid]; a=submitted.get(qid)
        row=dict(id=qid,category=category,submitted=a is not None,correctness=0.0,evidence_f1=None,behavior=None,score=0.0,latency_ms=a.get('latency_ms') if a else None)
        if a:
            status_ok=a['status']==r['status']
            if kind=='unsupported':
                reasons=set(a.get('reasons',[])); wanted=set(r['reasons'])
                behavior=f1(len(reasons&wanted),len(reasons),len(wanted)) if status_ok and not a['facts'] else 0.0
                row.update(correctness=behavior,behavior=behavior,score=behavior)
            else:
                actual=a['facts']; gold=r['facts']
                correct={k for k,v in actual.items() if k in gold and equal_value(v['value'],gold[k]['value'],kind)} if status_ok else set()
                correctness=f1(len(correct),len(actual),len(gold)) if status_ok and not a.get('reasons') else 0.0
                evidence_scores=[]
                for k in set(gold)|set(actual):
                    claimed=set(actual.get(k,{}).get('evidence',[]))
                    required=set(gold.get(k,{}).get('evidence',[]))
                    evidence_scores.append(f1(len(claimed&required),len(claimed),len(required)) if k in correct and correctness>0 else 0.0)
                evidence=mean(evidence_scores) if evidence_scores else 0.0
                row.update(correctness=correctness,evidence_f1=evidence,score=.7*correctness+.3*evidence)
        if kind!='unsupported' and row['evidence_f1'] is None: row['evidence_f1']=0.0
        if kind=='unsupported' and row['behavior'] is None: row['behavior']=0.0
        rows.append(row)
    latencies=[r['latency_ms'] for r in rows if r['latency_ms'] is not None]
    summary=dict(run_name=submission['run_name'],questions_submitted=len(submitted),questions_total=len(QUESTIONS),correctness_pct=round(100*mean(r['correctness'] for r in rows),2),evidence_f1_pct=round(100*mean(r['evidence_f1'] for r in rows if r['evidence_f1'] is not None),2),behavior_pct=round(100*mean(r['behavior'] for r in rows if r['behavior'] is not None),2),overall_pct=round(100*mean(r['score'] for r in rows),2),latency_samples=len(latencies),mean_latency_ms=round(mean(latencies),3) if latencies else None)
    return dict(summary=summary,questions=rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('submissions',nargs='+',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'results')
    args=parser.parse_args()
    verify_snapshot()
    # Recompute evaluator-side references to detect a stale or edited answer key.
    from reference import calculate
    reference=calculate()
    if reference!=load_json(ROOT/'reference_answers.json'): raise ValueError('Saved reference key differs from recalculation; run reference.py')
    results=[evaluate(load_json(p),reference) for p in args.submissions]
    names=[r['summary']['run_name'] for r in results]
    if len(names)!=len(set(names)): raise ValueError('Run names must be unique in a comparison')
    args.output.mkdir(parents=True,exist_ok=True)
    save_json(args.output/'details.json',dict(snapshot_id=reference['snapshot_id'],runs=results))
    summaries=[r['summary'] for r in results]
    with (args.output/'comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(summaries[0]));writer.writeheader();writer.writerows(summaries)
    lines=['# Benchmark comparison','','These are structured-answer checks on one pinned dataset. They do not establish real-world accuracy or evaluate prose.','','| Run | Correctness % | Evidence F1 % | Abstention/clarification % | Overall % | Latency samples | Mean ms |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for s in summaries:
        name=s['run_name'].replace('|','/').replace('\n',' ')
        lines.append(f"| {name} | {s['correctness_pct']} | {s['evidence_f1_pct']} | {s['behavior_pct']} | {s['overall_pct']} | {s['latency_samples']} | {s['mean_latency_ms'] if s['mean_latency_ms'] is not None else 'not supplied'} |")
    (args.output/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))


if __name__=='__main__': main()
