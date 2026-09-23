import json
import threading
import urllib.request
import urllib.error
import http.cookiejar
import pytest
import server
from reporting.engine import demo_snapshot
from reporting.storage import write_json

@pytest.fixture
def web(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'PRIVATE',tmp_path)
    monkeypatch.setattr(server,'state',{'snapshot':None,'cached':False})
    monkeypatch.setattr(server,'BOOTSTRAP','test-launch-nonce')
    http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    threading.Thread(target=http.serve_forever,daemon=True).start()
    cookies=__import__('http.cookiejar',fromlist=['CookieJar']).CookieJar()
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    base=f'http://127.0.0.1:{http.server_port}'
    def request(path,data=None,anonymous=False,**headers):
        h={'Content-Type':'application/json',**headers}
        req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
        return (urllib.request.urlopen if anonymous else client.open)(req)
    yield request,base,tmp_path,http
    http.shutdown();http.server_close()


def login(request):return request('/api/session',{'nonce':'test-launch-nonce'})


def test_sensitive_gets_require_cookie_no_tokens_in_json(web):
    req,base,_,_=web
    for route in ('/api/report','/api/connection','/api/delivery','/api/mail-preview','/api/export/html','/api/export/eml'):
        with pytest.raises(urllib.error.HTTPError) as ex:req(route,anonymous=True)
        assert ex.value.code==401
    response=login(req)
    assert 'HttpOnly' in response.headers['Set-Cookie'] and 'SameSite=Strict' in response.headers['Set-Cookie']
    assert "frame-ancestors 'self'" in response.headers['Content-Security-Policy']
    body=json.load(req('/api/report'))
    assert body['report'] is None and 'token' not in body
    assert server.TOKEN not in json.dumps(body)
    with pytest.raises(urllib.error.HTTPError):login(req)


def test_csrf_and_external_hosts_blocked(web):
    req,base,_,_=web;login(req)
    for headers in ({'Host':'evil.example'},{'Origin':'https://evil.example'},{'Sec-Fetch-Site':'cross-site'}):
        with pytest.raises(urllib.error.HTTPError) as ex:req('/api/demo',{},**headers)
        assert ex.value.code==403


def test_demo_is_explicit_and_does_not_overwrite_real_snapshot(web):
    req,base,p,_=web;login(req)
    assert json.load(req('/api/report'))['report'] is None
    result=json.load(req('/api/demo',{}))
    assert result['report']['snapshot']['mode']=='demo'
    assert not (p/'last-snapshot.json').exists()
    assert '가상 예시' in req('/api/export/html').read().decode('utf-8')


def test_stored_snapshot_is_restored_as_cached(web):
    _,_,p,_=web;s=demo_snapshot();s['mode']='live'
    write_json(p/'last-snapshot.json',s);server.restore_snapshot()
    assert server.state['cached'] is True and server.state['snapshot']['mode']=='live'


def test_pending_research_blocks_final_exports(web,monkeypatch):
    req,_,_,_=web;login(req)
    s=demo_snapshot();s['mode']='live';monkeypatch.setitem(server.state,'snapshot',s)
    for route in ('/api/mail-preview','/api/export/html','/api/export/eml','/api/export/md'):
        with pytest.raises(urllib.error.HTTPError) as ex:req(route)
        assert ex.value.code==400


def test_bad_key_is_not_saved_or_echoed(web,monkeypatch):
    req,_,p,_=web;login(req)
    def reject(self):raise ValueError('API 키 인증 실패 (IGW40031)')
    monkeypatch.setattr(server.PlugReader,'list_accounts',reject)
    with pytest.raises(urllib.error.HTTPError) as ex:req('/api/credentials',{'brand':'namuh','app_key':'do-not-output-key','app_secret':'do-not-output-secret'})
    body=ex.value.read().decode('utf-8')
    assert '저장하지 않았습니다' in body and 'do-not-output' not in body
    assert not (p/'plug-vault.json').exists()


def test_port_collision_chooses_available_loopback_port(web):
    _,_,_,busy=web
    fallback=server.bind_server(busy.server_port)
    try:assert fallback.server_port!=busy.server_port and fallback.server_address[0]=='127.0.0.1'
    finally:fallback.server_close()
