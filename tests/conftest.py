"""Make the pure modules importable without Home Assistant installed.

The package `__init__.py` imports Home Assistant, so the tests register an empty
package module for `custom_components.olo_waste` and load only the submodules
they need (`api`, `const`, `decoder`).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

for name, path in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.olo_waste", ROOT / "custom_components" / "olo_waste"),
):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
