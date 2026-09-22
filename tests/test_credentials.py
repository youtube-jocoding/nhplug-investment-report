import json
import os
import stat
from types import SimpleNamespace
from pathlib import Path
import pytest
from reporting.credentials import credential_environment,save_credentials,load_saved
from reporting.provider import safe_connection_error


def sample():
    return {'brand':'namuh','app_key':'unit-test-key-not-real','app_secret':'unit-test-secret-not-real'}


def test_credentials_stored_owner_only_and_original_settings_untouched(tmp_path):
    target=tmp_path/'private'/'plug-credentials.json'
    values=sample()
    assert save_credentials(values,target) is None
    assert stat.S_IMODE(target.stat().st_mode)==0o600
    assert stat.S_IMODE(target.parent.stat().st_mode)==0o700
    loaded=load_saved(target)
    assert loaded['NHPLUG_APP_KEY']==values['app_key']
    assert loaded['NHPLUG_AUTH_URL']=='https://api.nhplug.com:8443'
    assert list(target.parent.iterdir())==[target]


@pytest.mark.parametrize('brand',['other','https://attacker.example',None])
def test_credentials_cannot_choose_arbitrary_host(brand):
    with pytest.raises(ValueError):credential_environment({**sample(),'brand':brand})


def test_n2_keys_use_matching_official_domains():
    values=credential_environment({**sample(),'brand':'n2'})
    assert values['NHPLUG_AUTH_URL']=='https://api.n2plug.com:8443'
    assert values['NHPLUG_INSTRUMENTS_BASE']=='https://www.n2plug.com/instruments'


@pytest.mark.parametrize('raw',[{'error_code':'IGW40031','error_description':'secret-value'},json.dumps({'error_code':'IGW40031','error_description':'secret-value'})])
def test_invalid_app_key_is_identified_without_raw_text(raw):
    text=safe_connection_error(SimpleNamespace(raw=raw,code=None,status=403,category='auth'))
    assert 'IGW40031' in text
    assert 'secret-value' not in text


def test_arbitrary_sdk_exception_never_echoes_raw_secrets():
    error=SimpleNamespace(raw='some-secret-value',code='key-masquerading-as-code',status=500,message='secret')
    text=safe_connection_error(error)
    assert 'secret' not in text
    assert 'key-masquerading' not in text


def test_rejected_new_key_restores_environment_and_does_not_persist(tmp_path,monkeypatch):
    import server,threading,urllib.request,urllib.error
    monkeypatch.setattr(server,'PRIVATE',tmp_path)
    monkeypatch.setenv('NHPLUG_APP_KEY','previous-test-key')
    monkeypatch.setenv('NHPLUG_APP_SECRET','previous-test-secret')
    def reject(self): raise ValueError('API 키 인증 실패 (IGW40031)')
    monkeypatch.setattr(server.PlugReader,'list_accounts',reject)
    http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    threading.Thread(target=http.serve_forever,daemon=True).start()
    try:
        req=urllib.request.Request(f'http://127.0.0.1:{http.server_port}/api/credentials',data=json.dumps(sample()).encode(),headers={'Host':'127.0.0.1:8766','X-Report-Token':server.TOKEN,'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as ex:urllib.request.urlopen(req)
        body=ex.value.read().decode()
        assert 'IGW40031' in body and 'unit-test-key' not in body
        assert os.environ['NHPLUG_APP_KEY']=='previous-test-key'
        assert os.environ['NHPLUG_APP_SECRET']=='previous-test-secret'
        assert not (tmp_path/'plug-credentials.json').exists()
    finally:http.shutdown();http.server_close()
