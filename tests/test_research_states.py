from copy import deepcopy
from datetime import datetime
import pytest
from reporting.identity import identity, require_complete
from reporting.engine import analyze,demo_snapshot,KST
from reporting.research_store import load,validate

KEY='US|UNKNOWN|MSFT|UNKNOWN'


def test_pending_and_unresolved_do_not_produce_sector_weights():
    s=demo_snapshot();d=load(True)
    d['stocks'][KEY]={'status':'pending'}
    validate(d)
    r=analyze(s,d)
    assert r['research_status']['verified']==3 and not r['allocation'] and r['top_sector'] is None
    with pytest.raises(ValueError,match='조사 대기'):require_complete(s,d)
    d['stocks'][KEY]={'status':'unresolved','reason':'공식 자료에서 기간을 확인할 수 없음','checked_at':d['as_of'],'sources':['msft']}
    validate(d);assert require_complete(s,d)['final_ready']
    assert not analyze(s,d)['allocation']


def test_unresolved_requires_evidence_and_date():
    for fields in ({'reason':'이유'}, {'reason':'이유','checked_at':'2020-01-01','sources':['msft']}):
        d=load(True);d['stocks'][KEY]={'status':'unresolved',**fields}
        with pytest.raises(ValueError):validate(d)


def test_exact_research_set_rejects_extra_and_missing():
    s=demo_snapshot();d=load(True)
    d['stocks']['US|UNKNOWN|EXTRA|UNKNOWN']={'status':'pending'}
    with pytest.raises(ValueError,match='집합'):require_complete(s,d)
    d=load(True);d['stocks'].pop(KEY)
    with pytest.raises(ValueError,match='집합'):require_complete(s,d)


def test_exchange_adr_classes_and_punctuation_not_silently_merged():
    assert identity('us','xnys',' brk.b ','common')=='US|XNYS|BRK.B|COMMON'
    assert identity('US','XNYS','BRK.B','COMMON')!=identity('US','XNYS','BRK-B','COMMON')
    assert identity('US','XNYS','X','ADR')!=identity('US','XNYS','X','COMMON')
    assert identity('US','XNYS','X','COMMON')!=identity('US','XNAS','X','COMMON')
    d=load(True);d['stocks'][KEY]['identity']['code']='MSFT.A'
    with pytest.raises(ValueError,match='별칭'):validate(d)


def test_alias_requires_verified_mapping_sources():
    d=load(True);b=d['stocks'][KEY];b['identity']['code']='MSFT.A'
    b['code_alias']={'from':'MSFT','to':'MSFT.A','sources':['not-a-source']}
    with pytest.raises(ValueError):validate(d)


def test_fund_uses_fund_metrics_and_fixed_sector_taxonomy():
    d=load(True);d['stocks'][KEY]['identity']['product_type']='ETF'
    with pytest.raises(ValueError,match='ETF'):validate(d)
    d['stocks'][KEY]['financials']['kind']='fund';validate(d)
    d['stocks'][KEY]['sector_id']='AI-theme'
    with pytest.raises(ValueError,match='섹터'):validate(d)


def test_live_never_reads_example_file(monkeypatch):
    import reporting.research_store as rs
    s=demo_snapshot();s['mode']='live'
    calls=[]
    def empty(example=False):
        calls.append(example);return {'version':2,'stocks':{},'sources':{},'sectors':{},'events':[]}
    monkeypatch.setattr(rs,'load',empty)
    r=analyze(s)
    assert calls==[False] and r['research_status']['verified']==0


def test_separate_listing_lots_do_not_merge():
    s=demo_snapshot();s['holdings']=s['holdings'][:1]*2
    s['holdings']=deepcopy(s['holdings'])
    s['holdings'][0]={**s['holdings'][0],'exchange':'XNAS'}
    s['holdings'][1]={**s['holdings'][1],'exchange':'XNYS'}
    assert len(analyze(s)['consultation']['cards'])==2
