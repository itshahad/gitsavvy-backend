from typing import NoReturn
import requests
from requests.exceptions import HTTPError


class ExternalServiceError(Exception):
    def __init__(
        self, service: str, message: str | None = None, status_code: int | None = None
    ):
        self.service = service
        self.message = message
        self.status_code = status_code

        base = f"{self.service}:"
        if self.status_code is not None:
            base += f"({self.status_code})"
        if self.message is not None:
            base += f" {self.message}"
        super().__init__(base)


class StorageError(Exception):
    def __init__(self, message: str | None = None):
        self.message = message
        super().__init__(message or "storage error")


class DatabaseError(Exception):
    pass


def raise_request_exception(
    e: Exception,
    not_found_exception: Exception,
) -> NoReturn:
    if isinstance(e, HTTPError):
        status = e.response.status_code if e.response is not None else None

        if status == 404:
            raise not_found_exception from e
        elif status in (401, 403):
            raise ExternalServiceError(
                service="auth/forbidden",
                status_code=status,
            ) from e
        elif status == 429:
            raise ExternalServiceError(
                service="rate_limited",
                status_code=status,
            ) from e
        else:
            raise ExternalServiceError(
                service="http_error",
                status_code=status,
            ) from e

    elif isinstance(e, requests.exceptions.RequestException):
        raise ExternalServiceError(
            service="GitHub",
            message=str(e),
        ) from e

    raise e
