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
