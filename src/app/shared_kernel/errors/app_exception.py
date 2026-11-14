from typing import Any

from pydantic import BaseModel, Field

from src.app.shared_kernel.errors.constants import AppExceptionStatusCodes, AppExcStatusToHttpMap


class AppExceptionDetail(BaseModel):
    status: AppExceptionStatusCodes
    message: str | None = None
    field: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AppException(Exception):
    def __init__(
        self,
        details: list[AppExceptionDetail],
        status: AppExceptionStatusCodes,
        message: str | None = None,
    ):
        super().__init__(message or details[0].message or status.value)
        self.details = details
        self.status = status
        self.message = message or details[0].message or status.value

    @property
    def http_status(self) -> int:
        return AppExcStatusToHttpMap[self.status]

    def as_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "status": self.status.value,
            "details": [d.model_dump(exclude_none=True) for d in self.details],
        }
