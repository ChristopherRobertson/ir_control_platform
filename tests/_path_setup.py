"""Local test helper for importing repository packages."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for relative_path in (
    "contracts/src",
    "platform/src",
    "drivers/src",
    "experiment-engine/src",
    "data-pipeline/src",
    "processing/src",
    "analysis/src",
    "ui-shell/src",
    "reports/src",
    "simulators/src",
):
    package_root = ROOT / relative_path
    if package_root.exists():
        sys.path.insert(0, str(package_root))
