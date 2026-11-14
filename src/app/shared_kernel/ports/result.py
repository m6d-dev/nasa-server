from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from src.app.shared_kernel.errors.app_exception import AppException, AppExceptionDetail
from src.app.shared_kernel.errors.constants import AppExceptionStatusCodes

TValue = TypeVar("TValue")
TError = TypeVar("TError")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class Ok(Generic[TValue]):
    value: TValue


@dataclass(frozen=True, slots=True)
class Err(Generic[TError]):
    error: TError


class Result(Generic[TValue, TError]):
    """Expected failure is a value, not an exception (see CLAUDE.md, rule 3)."""

    __slots__ = ("_inner",)

    OK: Result[Any, Any]

    def __init__(self, inner: Ok[TValue] | Err[TError]):
        self._inner = inner

    @classmethod
    def ok(cls, value: TValue) -> Result[TValue, TError]:
        return cls(Ok(value))

    @classmethod
    def err(cls, error: TError) -> Result[TValue, TError]:
        return cls(Err(error))

    def is_ok(self) -> bool:
        return isinstance(self._inner, Ok)

    def is_err(self) -> bool:
        return isinstance(self._inner, Err)

    def unwrap(self) -> TValue:
        if isinstance(self._inner, Ok):
            return self._inner.value
        raise RuntimeError(f"called unwrap() on Err: {self._inner}")

    def unwrap_or(self, default: TValue) -> TValue:
        return self._inner.value if isinstance(self._inner, Ok) else default

    def unwrap_err(self) -> TError:
        if isinstance(self._inner, Err):
            return self._inner.error
        raise RuntimeError(f"called unwrap_err() on Ok: {self._inner}")

    def map(self, fn: Callable[[TValue], U]) -> Result[U, TError]:
        if isinstance(self._inner, Ok):
            return Result.ok(fn(self._inner.value))
        return Result(self._inner)

    def as_app_exception(self) -> AppException:
        err = self.unwrap_err()
        if isinstance(err, AppException):
            return err
        if isinstance(err, AppExceptionDetail):
            err = [err]
        if isinstance(err, list) and err and isinstance(err[0], AppExceptionDetail):
            return AppException(details=err, status=err[0].status)
        raise RuntimeError(f"No AppException mapping for {type(err).__name__}")


Result.OK = Result.ok(None)

type ResultDetailed[TValue] = Result[TValue, list[AppExceptionDetail]]


def not_found(what: str, field: str | None = None) -> Result[Any, list[AppExceptionDetail]]:
    return Result.err(
        [AppExceptionDetail(status=AppExceptionStatusCodes.NOT_FOUND, message=what, field=field)]
    )


def invalid(what: str, field: str | None = None) -> Result[Any, list[AppExceptionDetail]]:
    return Result.err(
        [AppExceptionDetail(status=AppExceptionStatusCodes.INVALID, message=what, field=field)]
    )


def unavailable(what: str) -> Result[Any, list[AppExceptionDetail]]:
    return Result.err(
        [AppExceptionDetail(status=AppExceptionStatusCodes.UNAVAILABLE, message=what)]
    )
