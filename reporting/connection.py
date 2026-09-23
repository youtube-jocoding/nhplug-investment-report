"""Upgrade app-owned credentials without consulting .env or changing accounts."""
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from .paths import PRIVATE
from .storage import file_lock, read_json, write_json
from .credentials import Vault, credential_environment, save_credentials
from .provider import PlugReader


class ConnectionProblem(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _read_optional(path):
    try:
        value = read_json(path) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _record(directory, code, message, **fields):
    write_json(directory / 'connection-check.json', {
        'code': code, 'message': message,
        'checked_at': datetime.now(timezone.utc).isoformat(), **fields})


def record_connected(directory=None):
    directory = Path(directory or PRIVATE)
    message = 'PLUG 키와 선택한 계좌의 잔고 조회를 확인했습니다.'
    pending = (directory / 'plug-credentials.json').is_file()
    if pending:
        message += ' 이전 평문 키 파일을 정리하지 못했습니다. 파일을 사용 중인 프로그램을 닫고 정리하세요.'
    _record(directory, 'ready', message, cleanup_pending=pending)


def _stored_credentials(directory):
    vault = Vault(directory / 'plug-vault.json')
    if not vault.path.exists():
        return False
    # Do not mistake a locked/corrupt vault for an empty one or try a plaintext fallback.
    try:
        with vault.transaction() as data:
            return bool(data.get('credentials'))
    except (ValueError, OSError):
        raise ConnectionProblem('secure_store_unavailable',
            '저장된 암호화 키를 열지 못했습니다. 이 PC의 OS 보안 저장소 잠금·권한을 확인하세요. 키가 없는 상태와는 다릅니다.') from None


def _selection(directory, accounts, legacy):
    previous = _read_optional(directory / 'selected-account.json')
    if previous.get('account_id'):
        matches = [a for a in accounts if a['ref'] == previous['account_id']]
    elif legacy and previous.get('label'):
        # Only upgrading the same app-owned legacy file may use its previous label.
        # Duplicate masked numbers have distinct labels, so cannot match here.
        matches = [a for a in accounts if a['label'] == previous['label']]
    else:
        matches = []
    if len(matches) == 1 and previous.get('market') in ('us', 'kr'):
        return {'account_id': matches[0]['ref'], 'label': matches[0]['label'], 'market': previous['market']}
    return None


def save_verified_connection(values, directory=None, legacy=False):
    """Validate once; preserve prior data on auth failure; keep a matching selection."""
    directory = Path(directory or PRIVATE)
    credential_environment(values)
    candidate = PlugReader(directory / 'plug-vault.json', candidate=values)
    committed = False
    try:
        with file_lock(directory / '.connection.lock'):
            # A web connection may have completed while migration was waiting.
            # Never overwrite that newer secure connection with an old file.
            if legacy and _stored_credentials(directory):
                return {'accounts': [], 'saved': True, 'restored_selection': False,
                        'already_secure': True, 'message': '암호화된 기존 연결을 유지했습니다.'}
            accounts = candidate.list_accounts()
            selected = _selection(directory, accounts, legacy)
            save_credentials(values, directory / 'plug-vault.json', token=candidate.candidate_token)
            committed = True
            # Never delete the existing selection/snapshot on a key refresh.
            # An unmatched selection must be resolved explicitly before collection.
            if selected:
                write_json(directory / 'selected-account.json', selected)
            cleanup_pending = False
            try:
                (directory / 'plug-credentials.json').unlink(missing_ok=True)
            except OSError:
                cleanup_pending = True
            code = 'ready' if selected else 'account_selection_required'
            message = '키 검증과 암호화 저장이 완료됐고 기존 계좌 선택을 유지했습니다.' if selected else '키 검증과 암호화 저장이 완료됐습니다. 분석할 계좌와 시장을 선택하세요.'
            if cleanup_pending:
                message += ' 이전 평문 키 파일 삭제를 완료하지 못했습니다. 해당 파일을 사용 중인 프로그램을 닫고 정리하세요.'
            _record(directory, code, message, cleanup_pending=cleanup_pending)
            return {'accounts': accounts, 'saved': True, 'restored_selection': bool(selected),
                    'selected_ref': selected['account_id'] if selected else None,
                    'market': selected['market'] if selected else None, 'message': message,
                    'cleanup_pending': cleanup_pending}
    except (ValueError, OSError):
        if committed:
            raise ConnectionProblem('connection_saved_incomplete',
                '새 키의 검증·암호화 저장은 완료됐지만 계좌 선택 또는 상태 기록을 저장하지 못했습니다. 폴더 권한을 확인한 뒤 계좌를 다시 선택하세요.') from None
        raise
    finally:
        candidate.forget()


def migrate_legacy(directory=None, retry=False):
    """One-time import of this app's own file, with fresh remote validation."""
    directory = Path(directory or PRIVATE)
    with file_lock(directory / '.migration.lock'):
        if _stored_credentials(directory):
            return {'migrated': False, 'reason': 'already_secure'}
        legacy = directory / 'plug-credentials.json'
        if not legacy.is_file():
            raise ConnectionProblem('credentials_missing',
                '이 저장소에 저장된 PLUG 키가 없습니다. PLUG 연결 화면에서 브랜드와 키를 입력하세요. 다른 PC의 키는 자동 복사되지 않습니다.')
        values = {}
        digest = None
        try:
            raw = legacy.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            previous = _read_optional(directory / 'connection-check.json')
            if not retry and previous.get('legacy_digest') == digest and previous.get('code') == 'legacy_credentials_rejected':
                raise ConnectionProblem('legacy_credentials_rejected',
                    '이전 PLUG 키 파일은 있지만 마지막 인증에서 거절되어 암호화 이전을 완료하지 못했습니다 (IGW40031). 현재 유효한 키로 다시 연결하세요.')
            import json
            values = json.loads(raw.decode('utf-8'))
            del raw
            if not isinstance(values, dict):
                raise ValueError()
            result = save_verified_connection(values, directory, legacy=True)
            return {**result, 'migrated': not result.get('already_secure', False)}
        except ConnectionProblem:
            raise
        except (ValueError, OSError) as error:
            # Only our adapter's recognized code is used, never arbitrary raw text.
            rejected = 'IGW40031' in str(error) and type(error) is ValueError
            code = 'legacy_credentials_rejected' if rejected else 'legacy_migration_failed'
            message = ('이전 PLUG 키 파일은 있지만 PLUG 인증에서 거절되어 암호화 이전을 완료하지 못했습니다 (IGW40031). 현재 유효한 키로 다시 연결하세요.'
                       if rejected else '이전 PLUG 키 파일은 있지만 검증·암호화 이전을 완료하지 못했습니다. 파일 형식, 네트워크 또는 OS 보안 저장소 상태를 확인하세요. 기존 파일과 계좌 선택은 유지했습니다.')
            _record(directory, code, message, legacy_digest=digest)
            raise ConnectionProblem(code, message) from None
        finally:
            if isinstance(values, dict):
                values.clear()


def ensure_credentials(directory=None):
    directory = Path(directory or PRIVATE)
    if _stored_credentials(directory):
        return {'migrated': False}
    return migrate_legacy(directory)


def connection_status(directory=None):
    """No secrets/decryption/network calls in the browser's status response."""
    from .credentials import legacy_detected
    directory = Path(directory or PRIVATE)
    vault = directory / 'plug-vault.json'
    public = _read_optional(vault)
    last = _read_optional(directory / 'connection-check.json')
    legacy = (directory / 'plug-credentials.json').is_file()
    if public.get('configured'):
        source = 'secure_store'
        code = last.get('code', 'stored')
        message = last.get('message', '암호화된 키가 저장되어 있습니다. 계좌 목록을 조회해 연결을 확인하세요.')
    elif vault.exists() and not public:
        source, code, message = 'secure_store', 'secure_store_unavailable', '암호화 설정 파일을 읽지 못했습니다. OS 보안 저장소와 파일 상태를 확인하세요.'
    elif legacy:
        source = 'legacy_file'
        code = last.get('code', 'legacy_pending')
        message = last.get('message', '이전 버전의 PLUG 키가 남아 있습니다. 검증 후 암호화 이전하면 기존 연결을 이어서 사용할 수 있습니다.')
    else:
        source, code, message = 'none', 'credentials_missing', '이 저장소에 연결된 PLUG 키가 없습니다. 브랜드와 키를 입력하세요.'
    return {'source': source, 'code': code, 'message': message,
            'legacy_env_ignored': legacy_detected(), 'legacy_local_file': legacy,
            'metadata': public.get('metadata', {}) if public.get('configured') else {}}
