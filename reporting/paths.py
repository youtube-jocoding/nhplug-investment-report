import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
_configured_private = Path(os.environ.get('REPORT_PRIVATE_DIR', 'private')).expanduser()
# A scheduler's working directory must not change where a relative config points.
PRIVATE = (_configured_private if _configured_private.is_absolute() else ROOT / _configured_private).resolve()
