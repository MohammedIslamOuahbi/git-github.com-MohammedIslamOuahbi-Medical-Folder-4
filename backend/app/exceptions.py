from __future__ import annotations

from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(self, status_code: int, message: str, details: dict | None = None) -> None:
        super().__init__(status_code=status_code, detail={"message": message, "details": details or {}})


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", details: dict | None = None) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, message, details)


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request", details: dict | None = None) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, message, details)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized", details: dict | None = None) -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, message, details)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden", details: dict | None = None) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, message, details)


class ConflictException(AppException):
    def __init__(self, message: str = "Conflict", details: dict | None = None) -> None:
        super().__init__(status.HTTP_409_CONFLICT, message, details)


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "Service unavailable", details: dict | None = None) -> None:
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, message, details)


class GatewayTimeoutException(AppException):
    def __init__(self, message: str = "Gateway timeout", details: dict | None = None) -> None:
        super().__init__(status.HTTP_504_GATEWAY_TIMEOUT, message, details)


class UnprocessableEntityAppException(AppException):
    def __init__(self, message: str = "Unprocessable entity", details: dict | None = None) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, message, details)
