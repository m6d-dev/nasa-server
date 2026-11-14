from enum import StrEnum


class AppExceptionStatusCodes(StrEnum):
    NOT_FOUND = "not_found"
    INVALID = "invalid"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"  # an upstream (vdev, db) is down


AppExcStatusToHttpMap: dict[AppExceptionStatusCodes, int] = {
    AppExceptionStatusCodes.NOT_FOUND: 404,
    AppExceptionStatusCodes.INVALID: 400,
    AppExceptionStatusCodes.CONFLICT: 409,
    AppExceptionStatusCodes.UNAVAILABLE: 503,
}
