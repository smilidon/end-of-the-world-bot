# SPDX-License-Identifier: GPL-3.0-only
"""Local output configuration; no listener or live adapter is imported."""
import os
from pathlib import Path
ART=Path(os.environ.get('EOTWB_ARTIFACTS','runtime/artifacts')).resolve()
BASE=ART.as_uri()+'/'
FORMATS=('pdf','svg','png')
