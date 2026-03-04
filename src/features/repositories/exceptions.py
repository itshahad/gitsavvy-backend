from typing import NoReturn
import requests
from requests.exceptions import HTTPError
from src.exceptions import ExternalServiceError


class RepoNotFoundError(Exception):
    def __init__(self, owner: str, repo: str):
        super().__init__(f"Repository {owner}/{repo} not found")


def raise_request_exception(e: Exception, owner: str, repo_name: str) -> NoReturn:
    if isinstance(e, HTTPError):
        status = e.response.status_code if e.response is not None else None
        if status == 404:
            raise RepoNotFoundError(owner, repo_name) from e
        if status in (401, 403):
            raise ExternalServiceError(
                service="auth/forbidden", status_code=status
            ) from e
        if status == 429:
            raise ExternalServiceError(
                service="rate_limited", status_code=status
            ) from e
        raise ExternalServiceError(service="http_error", status_code=status) from e

    if isinstance(e, requests.exceptions.RequestException):
        raise ExternalServiceError(service="GitHub", message=str(e)) from e

    raise e
