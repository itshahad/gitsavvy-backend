# from fastapi import HTTPException, status

# class NotFoundException(HTTPException):
#     def __init__(self, detail="Resource not found"):
#         super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class ExternalServiceError():
    def __init__(self, service: str, message: str | None = None):
        return f"External Service Error(service: {service}, message: {message})"
    
class ExternalServiceTimeout(ExternalServiceError):
    def __init__(self, service: str):
        super().__init__(service=service, message=f"{service} timed out")

        
class ExternalServiceUnavailable(ExternalServiceError):
    def __init__(self, service: str):
        super().__init__(service=service, message=f"{service} unavailable")

