"""Generate deterministic evaluator artifacts after independent calculation checks."""
from collections import Counter
from engine import ROOT,QUESTIONS,BENCHMARK_ID,calculate
from common import save_json
from score_v2 import evaluate

def public(q):
    result={k:q[k] for k in ('id','question')}
    if q.get('legacy'):
        from catalog import public_questions
        original=next(x for x in public_questions() if x['id']==q['id'])
        result.update(value_type=original['value_type'],contract=original['contract'])
    return result

def template(qs,snapshot,split):
    return dict(benchmark_id=BENCHMARK_ID,snapshot_id=snapshot,split=split,run_name='replace-with-model-and-workflow',cost_usd=None,answers=[dict(id=q['id'],status='answer',facts={},reasons=[],latency_ms=None) for q in qs])

def main():
    reference=calculate();independent=calculate(True)
    assert reference==independent,'Python/SQLite disagreement'
    assert Counter(q['split'] for q in QUESTIONS)==dict(regression=20,development=40,heldout=40)
    save_json(ROOT/'questions.json',[public(q) for q in QUESTIONS])
    save_json(ROOT/'evaluator_catalog.json',QUESTIONS)
    save_json(ROOT/'reference_answers.json',reference)
    save_json(ROOT/'splits.json',{s:[q['id'] for q in QUESTIONS if q['split']==s] for s in ('regression','development','heldout')})
    save_json(ROOT/'submission_template.json',template(QUESTIONS,reference['snapshot_id'],'all'))
    examples=[]
    for category in ('direct','two_step','organisation','financial','limitations'):
        examples.extend(q['id'] for q in [q for q in QUESTIONS if q['category']==category][:2])
    save_json(ROOT/'review_examples.json',dict(question_ids=examples,automated_check='Python and SQLite agree',human_review='pending'))
    sample=dict(independent,split='all',run_name='synthetic/sqlite-reference',synthetic=True)
    scored=evaluate(sample,reference)
    save_json(ROOT/'results'/'offline_baseline.json',dict(benchmark_id=BENCHMARK_ID,snapshot_id=reference['snapshot_id'],verification='Python and SQLite agree on all answers and evidence. Shared question specifications require human review.',live_model_runs=0,result=scored))
    lines=['# Benchmark v2 answer review','','Evaluator-only. Answers describe the frozen export, not independently verified real-world facts. Human review is pending.','']
    for q,a in zip(QUESTIONS,reference['answers']):
        lines.extend([f"## {q['id']} ({q['split']}): {q['question']}",'',q['contract'],'',f"Expected status: {a['status']}. {q.get('explanation','')}",''])
        for k,f in a['facts'].items():lines.append(f"- {k}: {f['value']} ({len(f['evidence'])} source references; IDs in reference_answers.json)")
        if a['reasons']:lines.append('Reasons: '+', '.join(a['reasons']))
        lines.append('')
    (ROOT/'ANSWER_KEY.md').write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    print('Built 100 questions; 20 regression / 40 development / 40 held-out. Synthetic baseline: '+str(scored['summary']['overall_pct']))
if __name__=='__main__':main()
