"""Which walkthrough to render: the engineer cut (script.py), the
executive cut (exec_script.py) or the deck (deck_script.py), and where its
output goes."""

from __future__ import annotations

import importlib
import pathlib
import sys
from types import ModuleType

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
MODULES = {"walkthrough": "script", "exec": "exec_script", "deck": "deck_script"}


def load(name: str) -> tuple[ModuleType, pathlib.Path]:
    """The script module and its output directory (demo/out, or demo/out/<name>)."""
    mod = importlib.import_module(MODULES[name])
    return mod, HERE / "out" if name == "walkthrough" else HERE / "out" / name
