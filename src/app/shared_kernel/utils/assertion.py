import inspect
from typing import Any


def ensure_isimplementation(impl: type, proto: type) -> None:
    """Fail at import time if `impl` misses a member of the Protocol `proto`.

    A slimmed-down copy of the CRM helper: checks presence and, for callables,
    parameter names. Signature typing is left to mypy.
    """
    for name, member in inspect.getmembers(proto):
        if name.startswith("_") and name not in ("__call__",):
            continue
        if name in ("__call__",) and "__call__" not in proto.__dict__:
            continue
        if not hasattr(impl, name):
            raise TypeError(f"{impl.__name__} does not implement {proto.__name__}.{name}")
        proto_attr: Any = member
        impl_attr: Any = getattr(impl, name)
        if inspect.isfunction(proto_attr) and inspect.isfunction(impl_attr):
            p = list(inspect.signature(proto_attr).parameters)
            i = list(inspect.signature(impl_attr).parameters)
            if p != i:
                raise TypeError(
                    f"{impl.__name__}.{name}{i} does not match {proto.__name__}.{name}{p}"
                )
