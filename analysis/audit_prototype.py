"""Read-only baseline audit. Run: python analysis/audit_prototype.py

Runs the inherited parser/resolver against temporary synthetic inputs only.
App analytics are loaded from their AST without launching Gradio or a server.
Requires pandas and plotly for analytical probes; does not download any data.
"""
import ast
import contextlib
import csv
import io
import json
from collections import Counter
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'fa26/src'))
import parse_filter as parser
import resolve_orgs as resolver
import download
import pandas as pd
import plotly.graph_objects as go


def read(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def audit():
    graph = ROOT / 'fa26/data/graph'
    tables = {p.stem: read(p) for p in sorted(graph.glob('*.csv'))}
    acts = tables['nodes_activities']
    tx = tables['nodes_transactions']
    orgs = tables['nodes_organisations']
    act_ids = {a['iati_identifier'] for a in acts}
    org_ids = {o['ref'] for o in orgs}
    countries = {c['code'] for c in tables['nodes_countries']}
    profile = {
        'row_counts': {k: len(v) for k, v in tables.items()},
        'publisher_activities': dict(Counter(a['publisher'] for a in acts)),
        'match_basis': dict(Counter(a['match_basis'] for a in acts)),
        'transaction_types': dict(Counter(t['type'] for t in tx)),
        'transaction_currencies': dict(Counter(t['currency'] for t in tx)),
        'blank_org_names': sum(not o['name'] for o in orgs),
        'name_only_orgs': sum(o['ref'].startswith('name:') for o in orgs),
        'activity_dates_by_publisher': {
            p: {k: sorted({a[k] for a in acts if a['publisher'] == p and a[k]})
                for k in ['start_actual', 'start_planned', 'last_updated']}
            for p in sorted({a['publisher'] for a in acts})},
        'missing_country_targets': [r for r in tables['rel_targets_country'] if r['country_code'] not in countries],
        'external_related_count': sum(r['related_ref'] not in act_ids for r in tables['rel_related_activity']),
        'external_related_examples': [r for r in tables['rel_related_activity'] if r['related_ref'] not in act_ids][:8],
        'duplicate_rows': {k: len(v)-len({tuple(r.items()) for r in v}) for k,v in tables.items()},
        'missing_org_endpoints': {k: sum(r['org_ref'] not in org_ids for r in tables[k]) for k in ['rel_reports','rel_participates','rel_transaction_edges']},
        'multicountry_activities': sum('|' in a['hotspot_countries'] for a in acts),
        'tx_country_populated': sum(bool(t['recipient_country']) for t in tx),
        'negative_transactions': sum(float(t['value']) < 0 for t in tx if t['value']),
    }
    probes = {}
    probes['general_emergency_toggle'] = {'configured': parser.INCLUDE_GENERAL_EMERGENCY, '72010_matches': parser.is_hunger_sector('72010','1')}
    probes['keyword_false_positive'] = {'text': 'Flipchart training', 'regex_match': parser.KW_RE.search('Flipchart training').group(0)}
    fixture = ET.parse(ROOT/'fa26/tests/fixture_iati_2.03.xml')
    probes['fixture_filter'] = [{'id': rec['activity']['iati_identifier'], 'keep': bool(parser.hotspot_codes(rec)) and parser.hunger_match(rec)[0]} for a in fixture.findall('iati-activity') for rec in [parser.parse_activity(a,'fixture')]]
    def activity(iid='TEST', title='Food assistance', extra='', country='SS', updated='2026-01-01'):
        return f'<iati-activity last-updated-datetime="{updated}" default-currency="USD"><iati-identifier>{iid}</iati-identifier><title><narrative>{title}</narrative></title><reporting-org ref="ORG"/><recipient-country code="{country}"/><sector code="72040"/>{extra}</iati-activity>'
    with tempfile.TemporaryDirectory(prefix='iati-audit-') as td:
        tmp = Path(td)
        raw = tmp/'raw'; (raw/'oxfamgb').mkdir(parents=True)
        out = tmp/'graph'
        def run_xml(body):
            (raw/'oxfamgb/a.xml').write_text('<iati-activities>'+body+'</iati-activities>',encoding='utf-8')
            with patch.object(parser,'RAW_DIR',raw), patch.object(parser,'GRAPH_DIR',out), contextlib.redirect_stdout(io.StringIO()):
                parser.run('oxfamgb')
            return read(out/'nodes_activities.csv')
        result = run_xml(activity(title='Food old')+activity(title='Food new',updated='2026-10-01'))
        probes['duplicate_first_wins'] = result[0]['title']
        result = run_xml(activity(title='Food excluded',country='KE')+activity(title='Food eligible'))
        probes['excluded_duplicate_blocks_eligible'] = len(result)
        run_xml(activity(extra='<recipient-country code="TD"/>'))
        probes['nonhotspot_endpoint_missing'] = 'TD' not in {c['code'] for c in read(out/'nodes_countries.csv')} and any(r['country_code']=='TD' for r in read(out/'rel_targets_country.csv'))
        tx_xml = '<transaction ref="stable-ref"><transaction-type code="1"/><value>100</value><provider-org ref="P" provider-activity-id="SOURCE-ACT"/></transaction>'
        rec = parser.parse_activity(ET.fromstring(activity(extra=tx_xml)),'oxfamgb')
        probes['source_transaction_and_activity_refs'] = rec['transactions'][0]
        with patch.object(parser,'RAW_DIR',tmp/'missing'), patch.object(parser,'GRAPH_DIR',out), contextlib.redirect_stdout(io.StringIO()):
            parser.run('oxfamgb')
        probes['missing_raw_overwrites_graph'] = len(read(out/'nodes_activities.csv'))
        index = tmp/'index.json'; index.write_text(json.dumps({'datasets':[{'reporting_org_short_name':'wfp','short_name':'wfp-ss','source_url':'https://example.invalid/data.xml'}]}))
        with patch.object(download,'RAW_DIR',raw), patch.object(download.urllib.request,'urlopen',side_effect=OSError('simulated failed download')), patch.object(download.time,'sleep'), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            probes['download_failure_returns_normally'] = download.run(['wfp'],index_file=index) is None
        def write_csv(name,fields,rows):
            with (out/name).open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=fields); w.writeheader();w.writerows(rows)
        collision_orgs=[{'ref':'REAL-A','name':'Shared Charity','type':''},{'ref':'REAL-B','name':'Shared Charity','type':''},{'ref':'name:Shared Charity','name':'Shared Charity','type':''}]
        write_csv('nodes_organisations.csv',['ref','name','type'],collision_orgs)
        with patch.object(resolver,'GRAPH_DIR',out),contextlib.redirect_stdout(io.StringIO()): resolver.main(offline=True)
        probes['ambiguous_name_merge'] = json.loads((out/'resolution_report.json').read_text())['merges']

    # Execute only three existing analytic functions, with synthetic DataFrames.
    module=ast.parse((ROOT/'fa26/spaces/app.py').read_text(encoding='utf-8'))
    names={'q_top_funders','insight_sankey','q_budgets'}
    functions=ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
    ns={'pd':pd,'go':go,'PUB_LABELS':{'wfp':'WFP'},'PUB2ACT':{'A':'wfp'},'ORG_NAME':{'P':'Donor'}}
    ns['ACT']=pd.DataFrame([{'iati_identifier':'A','countries':['SS','YE'],'publisher':'wfp'}])
    ns['TX']=pd.DataFrame([{'tx_id':f't{i}','iati_identifier':'A','type':kind,'value':'100','currency':'USD','recipient_country':'YE'} for i,kind in enumerate(['1','11','3'])])
    ns['TXE']=pd.DataFrame([{'tx_id':f't{i}','edge':'PROVIDED_BY','org_ref':'P'} for i in range(3)])
    ns['BUD']=pd.DataFrame([{'iati_identifier':'A','status':'2','type':kind,'value':value,'period_start':'2026-01-01','currency':'USD'} for kind,value in [('1','100'),('2','150')]])
    exec(compile(functions,'inherited_app_analytics','exec'),ns)
    probes['top_funders_mixed_types_wrong_country'] = ns['q_top_funders']('SS — South Sudan').to_dict('records')
    probes['sankey_incoming_plus_commitment'] = list(ns['insight_sankey']('SS — South Sudan','USD').data[0].link.value)
    probes['original_plus_revised_budget'] = ns['q_budgets']().to_dict('records')
    for p in list((ROOT/'fa26/src').glob('*.py')) + [ROOT/'fa26/spaces/app.py']:
        ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    return {'profile':profile,'probes':probes,'syntax':'all 7 Python files parse'}


if __name__ == '__main__':
    result=audit()
    target=Path(__file__).with_name('audit_results.json')
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({**result, 'profile':{k:v for k,v in result['profile'].items() if k != 'activity_dates_by_publisher'}},indent=2,ensure_ascii=True))
