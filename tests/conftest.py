"""All tests use a disposable private dir, never a developer's actual account."""
import os,tempfile
_test_private=tempfile.TemporaryDirectory(prefix='plug-report-test-')
os.environ['REPORT_PRIVATE_DIR']=_test_private.name
