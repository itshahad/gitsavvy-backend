from fastapi import HTTPException

class UpstreamHTTPException(HTTPException):
    def __init__(self, detail: str | None = None,  status_code: int | None = None):
        msg = detail if detail is not None else "unknown upstream error"
        super().__init__(status_code=status_code, detail= f"External Service Error(message: {msg})")

class ExternalServiceError(Exception):
    def __init__(self, service: str, message: str | None = None):
        self.service = service
        self.message = message
        super().__init__(f"{service}: {message or 'external service error'}")


class StorageError(Exception):
    def __init__(self, message: str | None = None):
        self.message = message
        super().__init__(message or "storage error")
