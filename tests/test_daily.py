from copy import deepcopy
from datetime import datetime,timedelta
import json
import pytest
import daily
from reporting.engine import analyze,demo_snapshot,KST
from reporting.research import financials
from reporting.research_store import load,validate
from reporting.export import newsletter,html_report
from reporting.archive import public_entry,save_archive,load_archive

@pytest.fixture
def ready(tmp_path,monkeypatch):
    monkeypatch.setattr(daily,'PRIVATE',tmp_path)
    s=demo_snapshot();s.update(mode='live',fetched_at=datetime.now(KST).isoformat())
    data=load(True);data['as_of']=datetime.now(KST).date().isoformat()
    monkeypatch.setattr(daily,'load',lambda:data)
    daily.write(tmp_path/'last-snapshot.json',s)
    return s,data,tmp_path

def test_freshness_requires_real_current_data(ready):
    s,d,_=ready;daily.check_fresh(s,d)
    for broken in [{**s,'mode':'demo'},{**s,'fetched_at':(datetime.now(KST)-timedelta(hours=2)).isoformat()},{**s,'fetched_at':datetime.now().isoformat()}]:
        with pytest.raises(ValueError):daily.check_fresh(broken,d)
    with pytest.raises(ValueError):daily.check_fresh(s,{**d,'as_of':'2020-01-01'})
    d['stocks'].pop('MSFT')
    with pytest.raises(ValueError):daily.check_fresh(s,d)

def test_claim_guards_duplicate_and_uncertain_delivery(ready):
    _,_,p=ready
    r=daily.prepare('owner@example.com');run=r['run']
    payload=json.loads((p/'reports'/run/'gmail-payload.json').read_text())
    assert payload['to']=='me'
    assert payload['subject'].startswith('내 투자 브리핑 | ')
    assert 'PLUG-' not in payload['subject'] and '[' not in payload['subject']
    assert payload['payload']['parts'][1]['filename']=='report.html'
    daily.claim(run)
    with pytest.raises(ValueError):daily.claim(run)
    with pytest.raises(ValueError):daily.prepare('owner@example.com')
    result=daily.sent(run,'valid-test-message-123')
    assert result['status']=='sent' and 'mail.google.com' in result['gmail_url']
    with pytest.raises(ValueError):daily.sent(run,'valid-test-message-123')

def test_payload_cannot_change_between_prepare_and_claim(ready):
    _,_,p=ready;r=daily.prepare('owner@example.com')
    path=p/'reports'/r['run']/'gmail-payload.json';path.write_text('{}')
    with pytest.raises(ValueError):daily.claim(r['run'])

def test_sent_requires_claim_and_real_response_id(ready):
    r=daily.prepare('owner@example.com')
    with pytest.raises(FileNotFoundError):daily.sent(r['run'],'valid-id-123')
    daily.claim(r['run'])
    with pytest.raises(ValueError):daily.sent(r['run'],'<script>')

def test_cash_flow_computation_and_noncomparable_periods():
    b=load(True)['stocks']['GOOGL'];f=financials(b)
    assert f['simple_fcf']==-5855
    assert f['operating_margin']==pytest.approx(34.033,abs=0.001)
    b=deepcopy(b);b['financials']['rows'][3]['period']='6개월 누적'
    assert financials(b)['simple_fcf'] is None

def test_research_source_and_nan_validation():
    d=load(True);bad=deepcopy(d);bad['sources']['msft']['url']='javascript:alert(1)'
    with pytest.raises(ValueError):validate(bad)
    bad=deepcopy(d);bad['stocks']['MSFT']['financials']['rows'][0]['value']=float('nan')
    with pytest.raises(ValueError):validate(bad)
    bad=deepcopy(d);bad['stocks']['MSFT']['sources']=['missing']
    with pytest.raises(ValueError):validate(bad)

def test_newsletter_is_short_and_full_report_separate():
    from html.parser import HTMLParser
    class Text(HTMLParser):
        text='';skip=False
        def handle_starttag(self,tag,attrs):
            if tag in ('style','script'):self.skip=True
        def handle_endtag(self,tag):
            if tag in ('style','script'):self.skip=False
        def handle_data(self,x):
            if not self.skip:self.text+=x
    r=analyze(demo_snapshot());body=newsletter(r,attachment=True);p=Text();p.feed(body)
    assert len(p.text)<1600
    assert 'report.html' in body and '첨부' in body
    assert '재무제표 핵심' not in body and '재무제표 핵심' in html_report(r)
    assert '내 기준' not in body+html_report(r)
    assert body.count('발표 원문')<=2

def test_unrelated_holdings_do_not_receive_sample_research():
    s=demo_snapshot();s['holdings'][0]['code']='UNRESEARCHED'
    r=analyze(s);card=next(c for c in r['consultation']['cards'] if c['code']=='UNRESEARCHED')
    assert card['research'] is None
    assert 'AI 성장' not in r['consultation']['headline']

def test_public_archive_keeps_research_but_removes_account_values(ready,tmp_path):
    snapshot,data,_=ready
    report=analyze(snapshot,data)
    entry=public_entry(report)
    text=json.dumps(entry,ensure_ascii=False)
    assert entry['stocks'] and entry['stocks'][0]['financials']
    assert snapshot['account_label'] not in text
    assert 'equity_weight' not in text and '평가액' not in text
    save_archive(report,tmp_path)
    assert load_archive(tmp_path)[0]['date']==data['as_of']
