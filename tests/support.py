from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import uuid


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = WORKSPACE_ROOT / ".tmp-tests"
TEMP_ROOT.mkdir(exist_ok=True)


@contextmanager
def workspace_temp_dir():
    temp_dir = TEMP_ROOT / f"case-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
