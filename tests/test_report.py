from copy import deepcopy
from types import SimpleNamespace
from email import policy
from email.parser import BytesParser
import json
import threading
import urllib.request
import urllib.error
import pytest
from reporting.engine import analyze, demo_snapshot
from reporting.provider import collect_pages, normalize, PlugReader, BALANCE
from reporting.export import html_report, email_message










def test_zero_assets_is_not_a_fake_success():
    s=demo_snapshot();s.update(holdings=[],cash=0)
    with pytest.raises(ValueError):analyze(s)




def meta(more=False,key=None):
    return SimpleNamespace(has_next=more,cts_flag='Y' if more else 'N',cts=key)


def test_pagination_uses_final_totals_and_all_lots():
    calls=[]
    def fetch(path,payload,**kwargs):
        calls.append(kwargs)
        if len(calls)==1:return {'Output_1':[{'eal_amt':10}]},meta(True,'full-key-001')
        return {'Output_0':{'tot_eal_amt':30},'Output_1':[{'eal_amt':20}]},meta()
    rows,total=collect_pages(fetch,BALANCE,{})
    assert len(rows)==2 and total['tot_eal_amt']==30
    assert calls[1]['cts']=='full-key-001'


@pytest.mark.parametrize('key',[None,'repeated'])
def test_broken_continuation_never_silently_returns_partial(key):
    def fetch(*args,**kwargs):return {'Output_1':[]},meta(True,key)
    with pytest.raises(ValueError):collect_pages(fetch,BALANCE,{})


def test_final_page_cannot_reuse_earlier_totals():
    pages=iter([({'Output_0':{'tot_eal_amt':10}},meta(True,'x')),({'Output_1':[]},meta())])
    with pytest.raises(ValueError):collect_pages(lambda *a,**k:next(pages),BALANCE,{})


def test_http_200_business_failure_is_rejected():
    def fetch(*a,**k):return {'message':{'usr_msg':'조회 권한이 없습니다.'},'Output_0':{}},meta()
    with pytest.raises(ValueError):collect_pages(fetch,BALANCE,{})


def test_live_normalization_whitelists_fields_and_leaves_unknown_sector():
    row={'iem_cd':'001','iem_nm':'테스트','eal_amt':1000,'byn_amt':900,'eal_pls_amt':100,'act_no':'11122233344','cus_fnm':'민감정보'}
    r=normalize([row],{'tot_eal_amt':1000,'dca':200,'act_no':'11122233344'},'****3344','live','2026-09-23')
    assert '11122233344' not in json.dumps(r)
    assert '민감정보' not in json.dumps(r,ensure_ascii=False)
    assert r['holdings'][0]['sector']=='분류 미확인'
    assert r['withdrawable'] is None
    assert r['as_of'] is None
    assert analyze(r)['top_sector'] is None


def test_inconsistent_totals_rejected():
    with pytest.raises(ValueError):normalize([{'iem_cd':'1','iem_nm':'x','eal_amt':100}],{'tot_eal_amt':1000,'dca':0},'x','live','now')


def test_order_path_cannot_reach_sdk():
    r=PlugReader()
    with pytest.raises(ValueError):r.fetch('/krstock/order/v1/orderCashBuy',{})


def test_exports_escape_untrusted_names_and_eml_has_no_recipient():
    s=demo_snapshot();s['holdings'][0]['name']='<img src=x onerror=alert(1)>'
    r=analyze(s)
    assert '<img src=x' not in html_report(r)
    assert '&lt;img' in html_report(r)
    msg=BytesParser(policy=policy.default).parsebytes(email_message(r).as_bytes())
    assert msg['To'] is None
    assert msg.get_body(preferencelist=('html',))


def test_local_server_rejects_csrf_and_external_hosts(tmp_path,monkeypatch):
    import server
    monkeypatch.setattr(server,'PRIVATE',tmp_path)
    http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
    url=f'http://127.0.0.1:{http.server_port}'
    try:
        req=urllib.request.Request(url+'/api/report',headers={'Host':'127.0.0.1:8766'})
        assert json.load(urllib.request.urlopen(req))['report']['snapshot']['mode']=='demo'
        for headers in [{'Host':'evil.example'}, {'Host':'127.0.0.1:8766'},{'Host':'127.0.0.1:8766','X-Report-Token':server.TOKEN,'Origin':'https://evil.example'}]:
            req=urllib.request.Request(url+'/api/demo',data=b'{}',headers=headers)
            with pytest.raises(urllib.error.HTTPError) as exc:urllib.request.urlopen(req)
            assert exc.value.code==403
    finally:http.shutdown();http.server_close()
