"""Evaluator-only question definitions. Do not give this module to an agent."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import public_questions, QUESTIONS as LEGACY_QUESTIONS

QUESTIONS = []
for row in LEGACY_QUESTIONS:
    q=dict(zip(('id','category','question','value_type','contract'),row))
    QUESTIONS.append(dict(q, split='regression', family=q['id'], legacy=True))

def add(category, text, table='nodes_activities', metric='count', field='iati_identifier', filters=None, links=None, group=None, status='answer', reason=None, explanation=None):
    n = sum(q['category']==category and not q.get('legacy') for q in QUESTIONS)
    cut = dict(direct=10,two_step=10,organisation=8,financial=7,limitations=5)[category]
    qid=f'V2Q{len(QUESTIONS)-19:03}'
    spec=dict(table=table,metric=metric,field=field,filters=filters or {},links=links or {},group=group)
    QUESTIONS.append(dict(id=qid,category=category,question=text,split='development' if n<cut else 'heldout',family=qid,legacy=False,value_type='unsupported' if status!='answer' else 'decimal' if metric=='sum' else 'date' if metric in ('min','max') else 'integer',spec=spec,status=status,reasons=[reason] if reason else [],explanation=explanation or '',contract='Evaluator-only selection: '+str(spec)))

def d(text,**kw):add('direct',text,**kw)
def t(text,**kw):add('two_step',text,**kw)
def o(text,**kw):add('organisation',text,**kw)
def f(text,**kw):add('financial',text,**kw)
def l(text,reason,explanation,status='abstain'):add('limitations',text,status=status,reason=reason,explanation=explanation)

# Twenty direct questions with no procedural calculation hints.
d('How many activities are recorded in this snapshot?')
d('How many activities are marked humanitarian?',filters={'humanitarian':'1'})
d('How many activities are recorded as completed?',filters={'status':'3'})
d('How many activities have no actual start date?',filters={'start_actual':''})
d('How many activities have no actual end date?',filters={'end_actual':''})
d('How many activities have a planned start date?',filters={'start_planned__ne':''})
d('How many activities have a planned end date?',filters={'end_planned__ne':''})
d('How many activities use GBP as their default currency?',filters={'default_currency':'GBP'})
d('How many distinct organisation references are recorded?',table='nodes_organisations',field='ref')
d('How many distinct named locations are recorded?',table='nodes_locations',field='location_id',filters={'name__ne':''})
d('How many activities are in implementation?',filters={'status':'2'})
d('What is the earliest recorded actual activity start date?',metric='min',field='start_actual',filters={'start_actual__ne':''})
d('What is the latest recorded actual activity end date?',metric='max',field='end_actual',filters={'end_actual__ne':''})
d('How many activities have no description?',filters={'description':''})
d('How many distinct transaction identifiers are recorded?',table='nodes_transactions',field='tx_id')
d('How many distinct budget identifiers are recorded?',table='nodes_budgets',field='budget_id')
d('How many distinct sector keys are recorded?',table='nodes_sectors',field='sector_key')
d('How many organisation references have no name?',table='nodes_organisations',field='ref',filters={'name':''})
d('How many locations have no latitude?',table='nodes_locations',field='location_id',filters={'lat':''})
d('How many activities have a publisher-reported update timestamp?',filters={'last_updated__ne':''})

# Each link condition adds a second relationship/table selection step.
t('How many Oxfam GB activities in Somalia are recorded as completed?',filters={'publisher':'oxfamgb','status':'3'},links={'rel_targets_country':{'country_code':'SO'}})
t('How many WFP activities in Yemen are in implementation?',filters={'publisher':'wfp','status':'2'},links={'rel_targets_country':{'country_code':'YE'}})
t('How many activities targeting Afghanistan have a recorded location?',links={'rel_targets_country':{'country_code':'AF'},'rel_located_at':{}})
t('How many activities targeting South Sudan have a funding organisation listed?',links={'rel_targets_country':{'country_code':'SS'},'rel_participates':{'role':'1'}})
t('How many WFP activities have both a sector classification and an implementing organisation?',filters={'publisher':'wfp'},links={'rel_classified_as':{},'rel_participates':{'role':'4'}})
t('How many Oxfam GB activities have both a recorded location and an implementing organisation?',filters={'publisher':'oxfamgb'},links={'rel_located_at':{},'rel_participates':{'role':'4'}})
t('How many activities targeting Yemen have an SDG link?',links={'rel_targets_country':{'country_code':'YE'},'rel_contributes_to':{}})
t('How many activities targeting Somalia have an actual start date before 2020?',filters={'start_actual__ne':'','start_actual__lt':'2020-01-01'},links={'rel_targets_country':{'country_code':'SO'}})
t('How many activities with a funding organisation have an actual end date before 2022?',filters={'end_actual__ne':'','end_actual__lt':'2022-01-01'},links={'rel_participates':{'role':'1'}})
t('How many Oxfam America activities have a transaction and a budget?',filters={'publisher':'oxfamus'},links={'nodes_transactions':{},'nodes_budgets':{}})
t('How many activities have both a negative transaction and an implementing organisation?',links={'nodes_transactions':{'value__negative':True},'rel_participates':{'role':'4'}})
t('How many activities have both a commitment and an expenditure transaction?',links={'nodes_transactions':{'type':'2'},'nodes_transactions#expenditure':{'type':'4'}})
t('How many activities have both incoming funds and disbursements?',links={'nodes_transactions':{'type':'1'},'nodes_transactions#disbursement':{'type':'3'}})
t('How many activities have both USD and GBP transactions?',links={'nodes_transactions':{'currency':'USD'},'nodes_transactions#gbp':{'currency':'GBP'}})
t('How many activities with a revised budget are marked completed?',filters={'status':'3'},links={'nodes_budgets':{'type':'2'}})
t('How many activities with a committed budget have an actual start date in 2021?',filters={'start_actual__gte':'2021-01-01','start_actual__lt':'2022-01-01'},links={'nodes_budgets':{'status':'2'}})
t('How many activities have a location link but no actual start date?',filters={'start_actual':''},links={'rel_located_at':{}})
t('How many activities with sector 1:72040 also have an SDG link?',links={'rel_classified_as':{'sector_key':'1:72040'},'rel_contributes_to':{}})
t('How many activities with incoming funds have no actual end date?',filters={'end_actual':''},links={'nodes_transactions':{'type':'1'}})
t('How many activities with an implementing organisation have a publisher-reported update in 2025?',filters={'last_updated__gte':'2025-01-01','last_updated__lt':'2026-01-01'},links={'rel_participates':{'role':'4'}})

# Ambiguous requests must not be resolved by guessing a financial policy.
for text,reason,explanation in [
 ('How much did the UK give?','funding_scope','Clarify government/agencies, transaction measure, currency and period.'),
 ('Show the total funding from Oxfam.','organisation_scope','Clarify Oxfam entity, measure, currency and period.'),
 ('How much did America contribute?','organisation_scope','America could mean a government or Oxfam America; clarify entity and financial scope.'),
 ('Which Congo projects did we support?','country_scope','Clarify which Congo and the organisation meant by we.'),
 ('How much funding came from the UN?','organisation_scope','Clarify which UN bodies and financial scope.'),
 ('How much did the government spend in Yemen?','organisation_scope','The government is unspecified; clarify the entity and financial scope.'),
 ('How much did our partners spend last year?','organisation_scope','Clarify our organisation, partners, absolute year, currency and measure.'),
 ('How much did the ministry contribute?','organisation_scope','No ministry or country is identified; clarify entity and financial scope.')]:
 o(text,status='clarify',reason=reason,explanation=explanation)
o('How many activities does the World Food Programme report?',filters={'publisher':'wfp'})
o('How many activities does Oxfam America report?',filters={'publisher':'oxfamus'})
o('How many activities does Oxfam Great Britain report?',filters={'publisher':'oxfamgb'})
o('How many activities list GB-CHC-202918 as an implementing organisation?',links={'rel_participates':{'org_ref':'GB-CHC-202918','role':'4'}})
o('How many activities list GB-CHC-202918 as a funding organisation?',links={'rel_participates':{'org_ref':'GB-CHC-202918','role':'1'}})
o('How many activities list GB-CHC-202918 as an extending organisation?',links={'rel_participates':{'org_ref':'GB-CHC-202918','role':'3'}})
o('How many activities target the Democratic Republic of the Congo?',links={'rel_targets_country':{'country_code':'CD'}})

f('What is the signed total of negative WFP incoming-fund transactions in USD?',table='nodes_transactions',metric='sum',field='value',filters={'publisher':'wfp','type':'1','currency':'USD','value__negative':True})
f('What is the total of positive WFP incoming-fund transactions in USD?',table='nodes_transactions',metric='sum',field='value',filters={'publisher':'wfp','type':'1','currency':'USD','value__positive':True})
f('How many zero-value transactions are recorded?',table='nodes_transactions',field='tx_id',filters={'value__zero':True})
f('What is the net GBP expenditure recorded for Oxfam GB across the snapshot?',table='nodes_transactions',metric='sum',field='value',filters={'publisher':'oxfamgb','type':'4','currency':'GBP'})
f('What is the net USD commitment amount recorded for WFP across the snapshot?',table='nodes_transactions',metric='sum',field='value',filters={'publisher':'wfp','type':'2','currency':'USD'})
f('What is the net USD expenditure recorded for WFP across the snapshot?',table='nodes_transactions',metric='sum',field='value',filters={'publisher':'wfp','type':'4','currency':'USD'})
f('How many Oxfam GB disbursement transactions have negative values?',table='nodes_transactions',field='tx_id',filters={'publisher':'oxfamgb','type':'3','value__negative':True})
f('What is the net incoming-fund amount by currency across all publishers?',table='nodes_transactions',metric='sum',field='value',filters={'type':'1'},group='currency')
f('What is the net expenditure by currency across all publishers?',table='nodes_transactions',metric='sum',field='value',filters={'type':'4'},group='currency')
f('What is the net USD incoming-fund amount for activities targeting Somalia?',table='nodes_transactions',metric='sum',field='value',filters={'type':'1','currency':'USD'},links={'rel_targets_country':{'country_code':'SO'}})
f('What is the net GBP disbursement amount for activities targeting Yemen?',table='nodes_transactions',metric='sum',field='value',filters={'type':'3','currency':'GBP'},links={'rel_targets_country':{'country_code':'YE'}})
f('What is the net USD expenditure dated in 2022 for activities targeting Afghanistan?',table='nodes_transactions',metric='sum',field='value',filters={'type':'4','currency':'USD','date__gte':'2022-01-01','date__lt':'2023-01-01'},links={'rel_targets_country':{'country_code':'AF'}})
f('What is the total value of revised indicative GBP budget rows across all periods?',table='nodes_budgets',metric='sum',field='value',filters={'type':'2','status':'1','currency':'GBP'})
f('What is the net USD incoming-fund amount dated before 2000?',table='nodes_transactions',metric='sum',field='value',filters={'type':'1','currency':'USD','date__ne':'','date__lt':'2000-01-01'})
f('What is the net EUR expenditure across the snapshot?',table='nodes_transactions',metric='sum',field='value',filters={'type':'4','currency':'EUR'})

l('How many people were lifted out of hunger by these projects?','outcomes_unavailable','No verified beneficiary outcome measure is present.')
l('Which project reduced child mortality the most?','outcomes_unavailable','No comparable causal mortality outcome measurements are present.')
l('How much funding was lost to corruption?','misuse_unavailable','Transactions do not establish misuse or corruption.')
l('What is the current bank balance of each implementing partner?','balances_unavailable','The snapshot is not a bank-account ledger.')
l('What are the real names behind every Oxfam Partner(s) entry?','identity_unavailable','Anonymised identities cannot be recovered from this export.')
l('Which country will have the worst hunger crisis next year?','forecast_unavailable','No validated forecast or future needs data is included.')
l('Which publisher is the most effective per dollar spent?','outcomes_unavailable','Comparable outcomes and a defensible effectiveness measure are absent.')
l('Give the funding total converted to euros at today’s exchange rates.','exchange_rates_unavailable','No current exchange-rate source is supplied.')
l('How much did every humanitarian organisation worldwide spend this year?','coverage_unavailable','This is a historical three-publisher slice, not complete global coverage.')
l('What is the home address of the person managing each project?','personal_details_unavailable','Project-manager residential addresses are not present.')
assert len(QUESTIONS)==100
orgs=[q for q in QUESTIONS if q['category']=='organisation']
for i,q in enumerate(orgs):q['split']='development' if i in [0,1,2,3,4,8,9,10] else 'heldout'
for q in orgs[11:14]:q['family']='organisation-role-counts'
