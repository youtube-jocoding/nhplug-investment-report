"""Local, owner-only PLUG credential storage. Values never form an API response."""
import json
import os
import tempfile
from pathlib import Path

from .paths import PRIVATE
CREDENTIAL_PATH = PRIVATE / 'plug-credentials.json'


def credential_environment(data):
    if not isinstance(data, dict) or data.get('brand') not in ('namuh', 'n2'):
        raise ValueError('API 키를 발급한 브랜드를 선택하세요.')
    for name in ('app_key', 'app_secret'):
        value=data.get(name)
        if not isinstance(value,str) or not 8 <= len(value.strip()) <= 2048 or any(ord(c)<32 for c in value):
            raise ValueError('앱키와 앱시크릿을 모두 입력하세요. 줄바꿈은 포함할 수 없습니다.')
    brand='nhplug' if data['brand']=='namuh' else 'n2plug'
    return {'NHPLUG_APP_KEY':data['app_key'].strip(), 'NHPLUG_APP_SECRET':data['app_secret'].strip(), 'NHPLUG_AUTH_URL':f'https://api.{brand}.com:8443', 'NHPLUG_BASE_URL':f'https://api.{brand}.com:8443', 'NHPLUG_INSTRUMENTS_BASE':f'https://www.{brand}.com/instruments'}


def load_saved(path=CREDENTIAL_PATH):
    if not Path(path).is_file(): return None
    try:
        return credential_environment(json.loads(Path(path).read_text()))
    except (OSError,ValueError,TypeError):
        raise ValueError('로컬 API 설정 파일을 읽지 못했습니다. 앱에서 다시 연결하세요.') from None


def save_credentials(data,path=CREDENTIAL_PATH):
    credential_environment(data)
    path=Path(path)
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(path.parent,0o700)
    fd,temporary=tempfile.mkstemp(prefix='.plug-',dir=path.parent)
    try:
        if hasattr(os,"fchmod"):os.fchmod(fd,0o600)
        else:os.chmod(temporary,0o600)
        with os.fdopen(fd,'w') as f:
            json.dump({k:data[k].strip() for k in ('brand','app_key','app_secret')},f)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
