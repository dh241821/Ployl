"""Compatibility helpers for runtime environments."""
from __future__ import annotations

import inspect
import sys
from typing import ForwardRef


_PATCHED_ATTR = "_plo_patch_forward_ref"


def patch_forward_ref_evaluate() -> None:
    """Patch ``typing.ForwardRef._evaluate`` for Python 3.12 + Pydantic v1.

    Python 3.12 introduced a keyword-only ``recursive_guard`` parameter to
    :func:`typing.ForwardRef._evaluate`.  Pydantic v1 still calls the method with
    the legacy positional signature which raises ``TypeError`` at import time
    when running under 3.12.  Newer versions of Pydantic remove this call but we
    keep the patch to support the current dependency set.
    """

    if sys.version_info < (3, 12):
        return

    # Avoid double patching when running in reloader processes.
    if getattr(ForwardRef, _PATCHED_ATTR, False):
        return

    signature = inspect.signature(ForwardRef._evaluate)
    parameter = signature.parameters.get("recursive_guard")
    if parameter is None or parameter.kind is not inspect.Parameter.KEYWORD_ONLY:
        return

    original = ForwardRef._evaluate

    def _patched_evaluate(self, globalns, localns, recursive_guard=None):
        if recursive_guard is None:
            recursive_guard = set()
        return original(self, globalns, localns, recursive_guard=recursive_guard)

    setattr(ForwardRef, _PATCHED_ATTR, True)
    ForwardRef._evaluate = _patched_evaluate  # type: ignore[assignment]

