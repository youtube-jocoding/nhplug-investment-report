import json
import os
from types import SimpleNamespace
import pytest
from reporting.connection import ensure_credentials, migrate_legacy, connection_status, save_verified_connection, ConnectionProblem
from reporting.credentials import save_credentials, load_saved
from reporting.storage import read_json, write_json
from reporting.provider import PlugReader


def values(secret='valid-test-secret'):
    return {'brand':'namuh','app_key':'legacy-test-key','app_secret':secret}


@pytest.fixture
def api(monkeypatch):
    import requests
    calls=[]
    rows=[{'acct_no':'1234567890','acct_type':'01'}]
    def post(url,**kwargs):
        calls.append(url)
        if url.endswith('/oauth2/token'):
            secret=kwargs['params']['appsecretkey']
            if secret=='invalid-test-secret':
                return SimpleNamespace(status_code=403,text=json.dumps({'error_code':'IGW40031','error_description':secret}))
            return SimpleNamespace(status_code=200,json=lambda:{'access_token':'test-token-never-output','expires_in':86400})
        return SimpleNamespace(ok=True,status_code=200,headers={},text='',json=lambda:{'Output_0':list(rows)})
    monkeypatch.setattr(requests,'post',post)
    return calls,rows


def legacy(directory,secret='valid-test-secret'):
    write_json(directory/'plug-credentials.json',values(secret))
    write_json(directory/'selected-account.json',{'label':'운영 계좌 · ****7890','market':'us'})
    write_json(directory/'last-snapshot.json',{'stored':'unchanged'})


def test_collect_upgrades_existing_connection_and_preserves_market(tmp_path,monkeypatch,api):
    import daily
    legacy(tmp_path)
    monkeypatch.setattr(daily,'PRIVATE',tmp_path)
    def balance(self,ref,market):
        assert ref in self.accounts and market=='us'
        return {'mode':'live','market':market,'fetched_at':'2026-09-23T08:00:00+09:00','account_id':ref,'holdings':[]}
    monkeypatch.setattr(PlugReader,'balance',balance)
    result=daily.collect()
    assert result['status']=='collected'
    assert not (tmp_path/'plug-credentials.json').exists()
    saved=read_json(tmp_path/'selected-account.json')
    assert len(saved['account_id'])==64 and saved['market']=='us'
    assert load_saved(tmp_path/'plug-vault.json')['NHPLUG_APP_SECRET']=='valid-test-secret'
    assert len([x for x in api[0] if x.endswith('/oauth2/token')])==1
    # Reopening via a new reader uses the same encrypted credentials and token.
    assert PlugReader(tmp_path/'plug-vault.json').list_accounts()[0]['ref']==saved['account_id']
    assert len([x for x in api[0] if x.endswith('/oauth2/token')])==1


def test_invalid_legacy_reports_auth_failure_not_missing_and_does_not_retry(tmp_path,api):
    legacy(tmp_path,'invalid-test-secret')
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    for _ in range(2):
        with pytest.raises(ConnectionProblem) as ex:ensure_credentials(tmp_path)
        assert ex.value.code=='legacy_credentials_rejected'
        assert 'IGW40031' in str(ex.value) and 'invalid-test-secret' not in str(ex.value)
    assert len(api[0])==1
    for name,content in before.items():assert (tmp_path/name).read_bytes()==content
    status=connection_status(tmp_path)
    assert status['source']=='legacy_file' and status['code']=='legacy_credentials_rejected'
    assert '키가 없습니다' not in status['message']
    assert 'invalid-test-secret' not in json.dumps(read_json(tmp_path/'connection-check.json'))


def test_changed_legacy_key_can_be_validated_after_previous_rejection(tmp_path,api):
    legacy(tmp_path,'invalid-test-secret')
    with pytest.raises(ConnectionProblem):ensure_credentials(tmp_path)
    write_json(tmp_path/'plug-credentials.json',values('new-valid-test-secret'))
    result=ensure_credentials(tmp_path)
    assert result['migrated'] and result['restored_selection']
    assert connection_status(tmp_path)['code']=='ready'


def test_secure_credentials_always_win_over_invalid_legacy(tmp_path,api):
    save_credentials(values(),tmp_path/'plug-vault.json')
    legacy(tmp_path,'invalid-test-secret')
    assert not ensure_credentials(tmp_path)['migrated']
    assert not api[0]
    assert load_saved(tmp_path/'plug-vault.json')['NHPLUG_APP_SECRET']=='valid-test-secret'


def test_locked_vault_never_falls_back_to_legacy(tmp_path,monkeypatch,api):
    save_credentials(values(),tmp_path/'plug-vault.json');legacy(tmp_path)
    from reporting import credentials
    monkeypatch.setattr(credentials,'os_keyring',lambda:None)
    with pytest.raises(ConnectionProblem) as ex:ensure_credentials(tmp_path)
    assert ex.value.code=='secure_store_unavailable' and not api[0]


def test_duplicate_masked_accounts_require_selection(tmp_path,api):
    legacy(tmp_path)
    api[1].append({'acct_no':'8888567890','acct_type':'01'})
    result=ensure_credentials(tmp_path)
    assert result['migrated'] and not result['restored_selection']
    assert connection_status(tmp_path)['code']=='account_selection_required'
    assert not read_json(tmp_path/'selected-account.json').get('account_id')


def test_key_refresh_preserves_stable_selection_and_previous_snapshot(tmp_path,api):
    legacy(tmp_path);migrate_legacy(tmp_path)
    selected=read_json(tmp_path/'selected-account.json')
    result=save_verified_connection(values('rotated-test-secret'),tmp_path)
    assert result['restored_selection'] and result['selected_ref']==selected['account_id']
    assert read_json(tmp_path/'selected-account.json')==selected
    assert read_json(tmp_path/'last-snapshot.json')=={'stored':'unchanged'}


def test_failed_key_refresh_preserves_old_secure_state(tmp_path,api):
    legacy(tmp_path);migrate_legacy(tmp_path)
    before={name:(tmp_path/name).read_bytes() for name in ('plug-vault.json','selected-account.json','last-snapshot.json')}
    with pytest.raises(ValueError):save_verified_connection(values('invalid-test-secret'),tmp_path)
    for name,content in before.items():assert (tmp_path/name).read_bytes()==content


def test_new_keys_do_not_guess_an_account_from_an_old_masked_label(tmp_path,api):
    legacy(tmp_path)
    result=save_verified_connection(values('replacement-test-secret'),tmp_path)
    assert not result['restored_selection']
    assert not read_json(tmp_path/'selected-account.json').get('account_id')


def test_missing_keys_never_scan_parent_env(tmp_path,monkeypatch,api):
    (tmp_path/'.env').write_text('APP_KEY=parent-key\nAPP_SECRET=parent-secret\n',encoding='utf-8')
    child=tmp_path/'repo';child.mkdir();monkeypatch.chdir(child)
    with pytest.raises(ConnectionProblem) as ex:ensure_credentials(child)
    assert ex.value.code=='credentials_missing' and not api[0]


def test_malformed_legacy_file_keeps_selection_and_does_not_leak(tmp_path,api):
    legacy(tmp_path)
    (tmp_path/'plug-credentials.json').write_text('{secret-never-echo',encoding='utf-8')
    with pytest.raises(ConnectionProblem) as ex:ensure_credentials(tmp_path)
    assert ex.value.code=='legacy_migration_failed' and 'secret-never-echo' not in str(ex.value)
    assert (tmp_path/'selected-account.json').exists()


def test_relative_private_path_is_independent_of_launch_directory(tmp_path,monkeypatch):
    import runpy
    from reporting.paths import ROOT
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('REPORT_PRIVATE_DIR','private')
    settings=runpy.run_path(str(ROOT/'reporting/paths.py'))
    assert settings['PRIVATE']==ROOT/'private'


def test_migration_cannot_overwrite_a_secure_connection_saved_by_web(tmp_path,api):
    save_credentials(values(),tmp_path/'plug-vault.json')
    result=save_verified_connection(values('invalid-test-secret'),tmp_path,legacy=True)
    assert result['already_secure'] and not api[0]
    assert load_saved(tmp_path/'plug-vault.json')['NHPLUG_APP_SECRET']=='valid-test-secret'


def test_post_commit_failure_is_not_reported_as_unsaved(tmp_path,api,monkeypatch):
    import reporting.connection as connection
    legacy(tmp_path)
    original=connection.write_json
    def disk_failure(path,data):
        if path.name=='selected-account.json':raise OSError('test-disk-error')
        return original(path,data)
    monkeypatch.setattr(connection,'write_json',disk_failure)
    with pytest.raises(ConnectionProblem) as ex:migrate_legacy(tmp_path)
    assert ex.value.code=='connection_saved_incomplete'
    assert load_saved(tmp_path/'plug-vault.json')


def test_successful_account_query_clears_old_selection_required_status(tmp_path,api):
    from reporting.connection import record_connected
    save_verified_connection(values(),tmp_path)
    assert connection_status(tmp_path)['code']=='account_selection_required'
    record_connected(tmp_path)
    assert connection_status(tmp_path)['code']=='ready'
