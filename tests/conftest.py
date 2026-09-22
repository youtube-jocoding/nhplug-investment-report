"""No real account, .env or keychain is used by ordinary tests."""
import os
import tempfile
from pathlib import Path
import pytest

# Explicit owned directory avoids Windows system-TEMP ACL differences.
base = Path(__file__).resolve().parents[1] / '.test-tmp'
base.mkdir(mode=0o700, exist_ok=True)
_test_private = tempfile.TemporaryDirectory(prefix='private-', dir=base)
os.environ['REPORT_PRIVATE_DIR'] = _test_private.name

@pytest.fixture(autouse=True)
def memory_keyring(monkeypatch, request):
    if request.node.get_closest_marker('native_keyring'): return
    from reporting import credentials
    values = {}
    class Memory:
        def get_password(self, service, user): return values.get((service, user))
        def set_password(self, service, user, secret): values[service, user] = secret
    monkeypatch.setattr(credentials, 'os_keyring', lambda: Memory())
    return values
