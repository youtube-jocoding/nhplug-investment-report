import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path(os.environ.get('REPORT_PRIVATE_DIR',ROOT/'private')).resolve()
