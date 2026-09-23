import json
import os
import stat
import sys
from types import SimpleNamespace
import pytest
from reporting.credentials import credential_environment, save_credentials, load_saved, Vault
from reporting.provider import safe_connection_error, PlugReader


def sample(secret='unit-test-secret-not-real', brand='namuh'):
    return {'brand': brand, 'app_key': 'unit-test-key-not-real', 'app_secret': secret}


def test_encrypted_vault_roundtrip_and_no_plaintext(tmp_path):
    target=tmp_path/'private'/'plug-vault.json';values=sample()
    save_credentials(values,target)
    assert load_saved(target)['NHPLUG_APP_KEY']==values['app_key']
    for path in target.parent.iterdir():
        assert values['app_key'].encode() not in path.read_bytes()
        assert values['app_secret'].encode() not in path.read_bytes()
    if os.name!='nt':
        assert stat.S_IMODE(target.stat().st_mode)==0o600
        assert stat.S_IMODE(target.parent.stat().st_mode)==0o700
    assert load_saved(tmp_path/'missing.json') is None


@pytest.mark.parametrize('brand',['other','https://attacker.example',None,''])
def test_brand_requires_explicit_official_choice(brand):
    with pytest.raises(ValueError):credential_environment({**sample(),'brand':brand})


def test_n2_keys_use_matching_official_domains():
    assert credential_environment(sample(brand='n2'))['NHPLUG_AUTH_URL']=='https://api.n2plug.com:8443'


@pytest.mark.parametrize('raw',[{'error_code':'IGW40031','error_description':'secret-value'},json.dumps({'error_code':'IGW40031','error_description':'secret-value'})])
def test_invalid_app_key_is_identified_without_raw_text(raw):
    text=safe_connection_error(SimpleNamespace(raw=raw,code=None,status=403,category='auth'))
    assert 'IGW40031' in text and 'secret-value' not in text


def test_arbitrary_sdk_exception_never_echoes_raw_secrets():
    assert 'secret' not in safe_connection_error(SimpleNamespace(raw='secret',code='secret',status=500,message='secret'))


@pytest.fixture
def broker(monkeypatch):
    import requests
    issued=[];calls=[]
    def post(url,**kwargs):
        if url.endswith('/oauth2/token'):
            p=kwargs['params'];secret=p['appsecretkey'];issued.append((url,secret))
            if secret=='invalid-test-secret' or ('n2plug' in url):
                return SimpleNamespace(status_code=403,text=json.dumps({'error_code':'IGW40031','error_description':secret}))
            return SimpleNamespace(status_code=200,json=lambda:{'access_token':'synthetic-token-'+secret,'expires_in':86400})
        calls.append(kwargs['headers'])
        return SimpleNamespace(ok=True,status_code=200,headers={},text='',json=lambda:{'Output_0':[{'acct_no':'1234567890','acct_type':'01'}]})
    monkeypatch.setattr(requests,'post',post)
    return issued,calls


def test_web_candidate_ignores_parent_env_and_cached_secret_survives_restart(tmp_path,monkeypatch,broker):
    parent=tmp_path/'parent';child=parent/'app';child.mkdir(parents=True)
    (parent/'.env').write_text('NHPLUG_APP_KEY=wrong-parent-key\nNHPLUG_APP_SECRET=wrong-parent-secret\nUNRELATED_TEST_VALUE=should-not-load\n',encoding='utf-8')
    monkeypatch.chdir(child)
    monkeypatch.setenv('APP_KEY','wrong-process-key')
    monkeypatch.setenv('NHPLUG_APP_SECRET','wrong-process-secret')
    monkeypatch.setenv('NHPLUG_TOKEN_CACHE_DIR',str(tmp_path/'sdk-cache'))
    original=dict(os.environ);path=tmp_path/'private'/'plug-vault.json'
    for secret in ('original-test-secret','replacement-test-secret'):
        c=PlugReader(path,candidate=sample(secret));c.list_accounts()
        save_credentials(sample(secret),path,token=c.candidate_token);c.forget()
    # New reader uses the saved replacement token, not the old key or secret cache.
    PlugReader(path).list_accounts()
    issued,calls=broker
    assert [x[1] for x in issued]==['original-test-secret','replacement-test-secret']
    assert all('replacement-test-secret' in str(h) for h in calls[-2:])
    assert dict(os.environ)==original
    assert not (tmp_path/'sdk-cache').exists()
    assert b'synthetic-token' not in path.read_bytes()


def test_bad_key_or_brand_preserves_prior_vault(tmp_path,broker):
    path=tmp_path/'plug-vault.json';save_credentials(sample(),path);before=path.read_bytes()
    for values in (sample('invalid-test-secret'),sample(brand='n2')):
        candidate=PlugReader(path,candidate=values)
        with pytest.raises(ValueError,match='IGW40031'):candidate.list_accounts()
        candidate.forget()
        assert path.read_bytes()==before
        assert load_saved(path)['NHPLUG_APP_SECRET']==sample()['app_secret']


def test_network_exception_with_secret_is_sanitized_and_env_restored(tmp_path,monkeypatch):
    import requests
    monkeypatch.setattr('time.sleep',lambda _:None)
    def fail(*a,**k):raise requests.Timeout('https://x?appkey=unit-test-key-not-real&secret=private-value')
    monkeypatch.setattr(requests,'post',fail)
    before=dict(os.environ)
    with pytest.raises(ValueError) as error:PlugReader(tmp_path/'vault.json',candidate=sample()).list_accounts()
    assert 'private-value' not in str(error.value) and 'unit-test-key' not in str(error.value)
    assert dict(os.environ)==before


def test_no_saved_key_never_falls_back_to_env(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_KEY','legacy-value')
    with pytest.raises(ValueError,match='저장된 API 키'):PlugReader(tmp_path/'missing.json').list_accounts()


def test_duplicate_last_four_stable_and_distinguishable(tmp_path,monkeypatch):
    rows=[{'acct_no':'11115555','acct_type':'01'},{'acct_no':'22225555','acct_type':'01'}]
    def fetch(self,*a,**k):
        self.brand='namuh';return {'Output_0':list(rows)},SimpleNamespace(has_next=False,cts_flag='N')
    monkeypatch.setattr(PlugReader,'fetch',fetch)
    path=tmp_path/'vault.json';a=PlugReader(path).list_accounts();rows.reverse();b=PlugReader(path).list_accounts()
    assert a==b and len({x['ref'] for x in a})==2 and len({x['label'] for x in a})==2
    assert '11115555' not in json.dumps(a)
    v=Vault(path)
    assert v.account_id('namuh','01','11115555')!=v.account_id('n2','01','11115555')


@pytest.mark.native_keyring
@pytest.mark.skipif(os.environ.get('RUN_NATIVE_KEYRING_TESTS')!='1' or sys.platform not in ('darwin','win32'),reason='opt-in native credential store')
def test_native_os_keyring_roundtrip(tmp_path):
    from reporting.credentials import os_keyring,SERVICE
    from reporting.storage import read_json
    path=tmp_path/'vault.json'
    try:
        save_credentials(sample(),path)
        assert load_saved(path)['NHPLUG_APP_SECRET']==sample()['app_secret']
    finally:
        meta=path.parent/'installation.json'
        if meta.exists():os_keyring().delete_password(SERVICE,read_json(meta)['id'])
