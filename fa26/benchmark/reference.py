"""Reference answers using Python sets and Decimal over CSV records."""
from collections import defaultdict
from decimal import Decimal
from common import ROOT, read_tables, save_json, verify_snapshot
from catalog import QUESTIONS, public_questions


def calculate():
    t = read_tables()
    acts = {r['iati_identifier']: r for r in t['nodes_activities']}
    if len(acts) != len(t['nodes_activities']):
        raise ValueError('Activity IDs must be unique')
    groups = {q[0]: defaultdict(list) for q in QUESTIONS[:16]}
    def add(q, key, value, *rows):
        groups[q][key].append((value, {r['_source'] for r in rows}))
    for a in acts.values():
        pub, iid = a['publisher'], a['iati_identifier']
        add('Q01',pub,iid,a)
        add('Q06',a['match_basis'],iid,a)
        start=a['start_actual'] or a['start_planned']
        if '2020-01-01' <= start < '2026-01-01': add('Q08',pub,iid,a)
        if a['last_updated']: add('Q09',pub,a['last_updated'][:10],a)
    for r in t['rel_targets_country']:
        a=acts[r['iati_identifier']]
        if r['is_hotspot']=='true': add('Q02',a['publisher'],r['country_code'],r,a)
        if r['country_code']=='SO': add('Q03',a['publisher'],a['iati_identifier'],r,a)
    partner_pubs=defaultdict(set)
    for r in t['rel_participates']:
        partner_pubs[r['org_ref']].add(acts[r['iati_identifier']]['publisher'])
    for r in t['rel_participates']:
        a=acts[r['iati_identifier']]
        if len(partner_pubs[r['org_ref']])>=2: add('Q04',r['org_ref'],a['iati_identifier'],r,a)
        add('Q05',r['role'],r['org_ref'],r)
    groups['Q07']['count'] # Preserve a zero count if no matches.
    for r in t['rel_classified_as']:
        a=acts[r['iati_identifier']]
        if a['publisher']=='wfp' and r['sector_key']=='1:72040': add('Q07','count',a['iati_identifier'],r,a)
    for q in ['Q10','Q11','Q12','Q14']: groups[q]['total']
    for r in t['nodes_transactions']:
        a=acts[r['iati_identifier']]; pub=a['publisher']; amount=Decimal(r['value'])
        if not amount.is_finite(): raise ValueError('Non-finite transaction amount')
        in2020='2020-01-01'<=r['date']<'2021-01-01'
        if pub=='wfp' and r['type']=='1' and r['currency']=='USD' and in2020: add('Q10','total',amount,r,a)
        if pub=='oxfamgb' and r['type']=='3' and r['currency']=='GBP' and in2020: add('Q11','total',amount,r,a)
        if pub=='oxfamus' and r['type']=='4' and r['currency']=='USD': add('Q12','total',amount,r,a)
        if amount<0: add('Q13',pub,r['tx_id'],r,a)
    for r in t['nodes_budgets']:
        if (r['type'],r['status'],r['currency'])==('1','2','USD'): add('Q14','total',Decimal(r['value']),r)
    for r in t['rel_contributes_to']: add('Q15',r['sdg_key'],r['iati_identifier'],r)
    for r in t['rel_located_at']:
        a=acts[r['iati_identifier']]; add('Q16',a['publisher'],a['iati_identifier'],r,a)
    answers=[]
    for qid,_,_,kind,contract in QUESTIONS:
        if kind=='unsupported':
            status,reasons,explanation=contract.split('|')
            answers.append(dict(id=qid,status=status,reasons=reasons.split(','),facts={},explanation=explanation))
            continue
        facts={}
        for key, rows in sorted(groups[qid].items()):
            values=[v for v,_ in rows]
            value=sum(values,Decimal(0)) if kind=='decimal' else max(values) if kind=='date' else len(set(values))
            evidence=sorted({s for _,sources in rows for s in sources})
            if not evidence:
                scope = ['rel_classified_as.csv','nodes_activities.csv'] if qid=='Q07' else ['nodes_budgets.csv'] if qid=='Q14' else ['nodes_transactions.csv','nodes_activities.csv']
                evidence = sorted('manifest:'+name for name in scope)
            facts[key]=dict(value=str(value),evidence=evidence)
        answers.append(dict(id=qid,status='answer',reasons=[],facts=facts))
    return dict(snapshot_id=verify_snapshot()['snapshot_id'],answers=answers)


def main():
    reference=calculate()
    save_json(ROOT/'questions.json',public_questions())
    save_json(ROOT/'reference_answers.json',reference)
    lines=['# Questions and answer key','','These are reference answers for the pinned exported data, not verified real-world humanitarian facts.','']
    for q,a in zip(QUESTIONS,reference['answers']):
        lines += [f'## {q[0]}: {q[2]}','',f'Category: {q[1]}.','',f'Calculation contract: {q[4]}','']
        if a['status']=='answer':
            lines += ['| Answer key | Value | Contributing source rows |','| --- | ---: | ---: |']
            lines += [f"| {k} | {v['value']} | {len(v['evidence'])} |" for k,v in a['facts'].items()]
        else: lines += [f"Expected response: **{a['status']}**. {a['explanation']}"]
        lines += ['']
    (ROOT/'ANSWER_KEY.md').write_text('\n'.join(lines),encoding='utf-8')
    (ROOT/'QUESTIONS.md').write_text('# Questions for model testing\n\nUse only the pinned snapshot. Follow the calculation contracts in questions.json.\n\n'+'\n\n'.join(f'{q[0]}. {q[2]}' for q in QUESTIONS)+'\n',encoding='utf-8')
    # Copy this blank submission for each model run; reference answers stay evaluator-side.
    save_json(ROOT/'submission_template.json',dict(run_name='replace-with-model-and-agent-name',snapshot_id=reference['snapshot_id'],answers=[dict(id=q[0],status='answer',facts={},reasons=[],latency_ms=None) for q in QUESTIONS]))
    print('Generated 20 questions and reference answers')


if __name__=='__main__': main()
