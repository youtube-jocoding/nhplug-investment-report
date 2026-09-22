#!/usr/bin/env python3
"""Run pytest in a protected, disposable temp base; zero tests is a failure."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reporting.storage import protect_directory
base = protect_directory(ROOT / '.test-tmp')
with tempfile.TemporaryDirectory(prefix='pytest-', dir=base) as run:
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '--basetemp', str(Path(run) / 'cases'), *sys.argv[1:]], cwd=ROOT)
raise SystemExit(result.returncode)
