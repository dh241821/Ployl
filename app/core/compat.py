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
    if parameter is None:
        return

    expects_keyword_only = parameter.kind is inspect.Parameter.KEYWORD_ONLY
    type_params_param = signature.parameters.get("type_params")

    if not expects_keyword_only and type_params_param is None:
        # Nothing to do – signature already accepts the legacy positional call.
        return

    original = ForwardRef._evaluate

    def _patched_evaluate(self, globalns, localns, *args, **kwargs):
        # ``recursive_guard`` might be provided positionally (Pydantic < 1.10) or
        # as a keyword (stdlib / future callers).  Normalise it so we can call
        # the stdlib implementation regardless of Python version.
        recursive_guard = None
        remaining_args = list(args)
        if remaining_args:
            recursive_guard = remaining_args.pop(0)

        kw_recursive_guard = kwargs.pop("recursive_guard", None)
        if recursive_guard is None:
            recursive_guard = kw_recursive_guard
        elif kw_recursive_guard is not None:
            recursive_guard = kw_recursive_guard

        if recursive_guard is None:
            recursive_guard = set()

        if expects_keyword_only:
            kwargs["recursive_guard"] = recursive_guard
        else:
            remaining_args.insert(0, recursive_guard)

        if type_params_param is not None:
            _sentinel = object()
            type_params = _sentinel
            if remaining_args:
                type_params = remaining_args.pop(0)
            kw_type_params = kwargs.pop("type_params", _sentinel)
            if kw_type_params is not _sentinel:
                type_params = kw_type_params
            if type_params is not _sentinel:
                kwargs["type_params"] = type_params

        return original(self, globalns, localns, *remaining_args, **kwargs)

    setattr(ForwardRef, _PATCHED_ATTR, True)
    ForwardRef._evaluate = _patched_evaluate  # type: ignore[assignment]

