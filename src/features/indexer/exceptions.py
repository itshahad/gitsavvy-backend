from fastapi import HTTPException, status
import requests
from requests.exceptions import HTTPError
from src.exceptions import ExternalServiceError, UpstreamHTTPException

class RepoNotFoundError(Exception):
    def __init__(self, owner: str, repo: str):
        super().__init__(f"Repository {owner}/{repo} not found")

def raise_request_exception(e:Exception, owner: str, repo_name: str):
    if isinstance(e, HTTPError):
        status = e.response.status_code if e.response is not None else None
        if status == 404:
            raise RepoNotFoundError(owner, repo_name) from e
        if status in (401, 403):
            raise UpstreamHTTPException(detail="auth/forbidden", status_code=status) from e
        if status == 429:
            raise UpstreamHTTPException(detail="rate_limited", status_code=status) from e
        raise UpstreamHTTPException(detail="http_error", status_code=status) from e

    if isinstance(e, requests.exceptions.RequestException):
        raise ExternalServiceError(service="GitHub",message=str(e)) from e
    
    raise e