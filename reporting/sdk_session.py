"""Fence SDK 0.4.0's dotenv and global caches; only our vault supplies secrets."""
import hashlib
import os
import threading
from contextlib import contextmanager
from unittest.mock import patch
from .credentials import credential_environment

SDK_LOCK = threading.RLock()


def fingerprint(credentials):
    return hashlib.sha256('\0'.join(credentials[k].strip() for k in ('brand', 'app_key', 'app_secret')).encode()).hexdigest()


@contextmanager
def session(credentials, token, base_url=None):
    env = credential_environment(credentials)
    if base_url: env['NHPLUG_BASE_URL'] = base_url
    scope = fingerprint(credentials)
    with SDK_LOCK:
        old = {k: v for k, v in os.environ.items() if k.startswith('NHPLUG_') or k in ('APP_KEY', 'APP_SECRET', 'PYTHON_DOTENV_DISABLED')}
        for k in old: os.environ.pop(k, None)
        os.environ.update(env)
        os.environ['PYTHON_DOTENV_DISABLED'] = '1'
        auth = None
        try:
            # Both functions are fenced before the first SDK import. No .env contents
            # (including unrelated environment values) can enter this process.
            with patch('dotenv.find_dotenv', return_value=''), patch('dotenv.load_dotenv', return_value=False):
                from nhplug import auth, call
            auth._cache.update(token=None, exp=0.0, scope=None)
            if token.get('credential_scope') == scope:
                auth._cache.update(token=token.get('token'), exp=token.get('exp', 0.0), scope=auth._cache_scope())
            yield call
            token.clear()
            token.update(credential_scope=scope, token=auth._cache.get('token'), exp=auth._cache.get('exp', 0.0))
        finally:
            if auth: auth._cache.update(token=None, exp=0.0, scope=None)
            for k in list(os.environ):
                if k.startswith('NHPLUG_') or k in ('APP_KEY', 'APP_SECRET', 'PYTHON_DOTENV_DISABLED'): os.environ.pop(k, None)
            os.environ.update(old)
