"""Deliberately corrupted and evidence-free controls, derived from SQL output."""
from copy import deepcopy
from common import ROOT, load_json, save_json


def main():
    base=load_json(ROOT/'runs/sqlite_baseline.json')
    bad=deepcopy(base);bad['run_name']='deliberately_wrong_control'
    no_evidence=deepcopy(base);no_evidence['run_name']='correct_values_without_evidence_control'
    for answer in bad['answers']:
        answer['latency_ms']=None
        if answer['status']=='answer':
            for fact in answer['facts'].values(): fact.update(value='definitely-not-the-answer',evidence=['invented.csv:row:999'])
        else:
            answer.update(status='answer',reasons=[],facts={'unsupported_claim':{'value':'999','evidence':[]}})
    for answer in no_evidence['answers']:
        answer['latency_ms']=None
        for fact in answer['facts'].values(): fact['evidence']=[]
    save_json(ROOT/'runs/deliberately_wrong.json',bad)
    save_json(ROOT/'runs/no_evidence.json',no_evidence)
    print('Saved two synthetic controls; neither is a model run')


if __name__=='__main__': main()
