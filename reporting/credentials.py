"""One credential source: authenticated ciphertext, with an OS-protected master key."""
import hashlib
import hmac
import os
import secrets
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from .paths import PRIVATE, ROOT
from .storage import file_lock, read_json, write_json

CREDENTIAL_PATH = PRIVATE / 'plug-vault.json'
SERVICE = 'nhplug-investment-report'


def os_keyring():
    # Explicit native backends: never accept keyrings.alt plaintext fallback.
    try:
        if sys.platform == 'darwin':
            from keyring.backends.macOS import Keyring
        elif os.name == 'nt':
            from keyring.backends.Windows import WinVaultKeyring as Keyring
        else:
            from keyring.backends.SecretService import Keyring
        backend = Keyring()
        if backend.priority <= 0: raise RuntimeError()
        return backend
    except Exception:
        raise ValueError('OS 보안 저장소를 사용할 수 없습니다. macOS 키체인 / Windows 자격 증명 관리자 / Linux Secret Service를 활성화하고 잠금을 해제하세요.') from None


def credential_environment(data):
    if not isinstance(data, dict) or data.get('brand') not in ('namuh', 'n2'):
        raise ValueError('API 키를 발급한 브랜드를 직접 선택하세요.')
    for name in ('app_key', 'app_secret'):
        value = data.get(name)
        if not isinstance(value, str) or not 8 <= len(value.strip()) <= 2048 or any(ord(c) < 32 for c in value):
            raise ValueError('앱키와 앱시크릿을 모두 입력하세요. 줄바꿈은 포함할 수 없습니다.')
    brand = 'nhplug' if data['brand'] == 'namuh' else 'n2plug'
    return {'NHPLUG_APP_KEY': data['app_key'].strip(), 'NHPLUG_APP_SECRET': data['app_secret'].strip(),
            'NHPLUG_AUTH_URL': f'https://api.{brand}.com:8443', 'NHPLUG_BASE_URL': f'https://api.{brand}.com:8443',
            'NHPLUG_INSTRUMENTS_BASE': f'https://www.{brand}.com/instruments', 'NHPLUG_TOKEN_CACHE': '0'}


class Vault:
    def __init__(self, path=None):
        self.path = Path(path or CREDENTIAL_PATH)

    def cipher(self):
        meta_path = self.path.parent / 'installation.json'
        meta = read_json(meta_path) if meta_path.exists() else {'id': uuid.uuid4().hex}
        if not meta_path.exists(): write_json(meta_path, meta)
        try:
            backend = os_keyring()
            key = backend.get_password(SERVICE, meta['id'])
            if key is None:
                if self.path.exists(): raise ValueError()
                key = Fernet.generate_key().decode('ascii')
                backend.set_password(SERVICE, meta['id'], key)
            return Fernet(key.encode('ascii'))
        except Exception:
            raise ValueError('OS 보안 저장소를 열지 못했습니다. 키체인·자격 증명 관리자·Secret Service의 잠금과 권한을 확인하세요. 다른 PC의 private 폴더는 복사하지 말고 키를 다시 연결하세요.') from None

    @contextmanager
    def transaction(self):
        with file_lock(self.path.parent / '.vault.lock'):
            cipher = self.cipher()
            try:
                import json
                data = json.loads(cipher.decrypt(read_json(self.path)['ciphertext'].encode()).decode('utf-8')) if self.path.exists() else {'identity_secret': secrets.token_hex(32)}
            except (InvalidToken, ValueError, KeyError, TypeError):
                raise ValueError('암호화된 API 설정을 읽지 못했습니다. OS 보안 저장소와 이 PC의 설정을 확인하세요.') from None
            before = json.dumps(data, sort_keys=True)
            try:
                yield data
                if not self.path.exists() or before != json.dumps(data, sort_keys=True):
                    write_json(self.path, {'version': 1, 'configured': bool(data.get('credentials')), 'metadata': {'brand': data.get('credentials', {}).get('brand'), 'validated_at': data.get('validated_at')}, 'ciphertext': cipher.encrypt(json.dumps(data).encode('utf-8')).decode('ascii')})
            finally:
                data.clear()

    def account_id(self, brand, kind, raw):
        with self.transaction() as data:
            return hmac.new(bytes.fromhex(data['identity_secret']), f'{brand}|{kind}|{raw}'.encode(), hashlib.sha256).hexdigest()


def load_saved(path=None):
    vault = Vault(path)
    if not vault.path.exists(): return None
    with vault.transaction() as data:
        return credential_environment(data['credentials']) if data.get('credentials') else None


def save_credentials(data, path=None, token=None):
    credential_environment(data)
    with Vault(path).transaction() as stored:
        stored['credentials'] = {k: data[k].strip() for k in ('brand', 'app_key', 'app_secret')}
        stored['token'] = token or {}
        from datetime import datetime, timezone
        stored['validated_at'] = datetime.now(timezone.utc).isoformat()



def legacy_detected():
    # Existence check only. Never read or import ancestor/global .env files.
    candidates = [p / '.env' for p in (ROOT, *ROOT.parents)] + [Path.home() / '.nhplug/.env']
    return any(p.is_file() for p in candidates)


def credential_status():
    try:
        public = read_json(CREDENTIAL_PATH) if CREDENTIAL_PATH.exists() else {}
        configured = public.get('configured', False)
        info = public.get('metadata', {}) if configured else {}
    except (OSError, ValueError, TypeError, AttributeError):
        configured = False; info = {}
    return {'source': 'secure_store' if configured else 'none',
            'legacy_env_ignored': legacy_detected(), 'legacy_local_file': (PRIVATE / 'plug-credentials.json').is_file(),
            'metadata': info}
