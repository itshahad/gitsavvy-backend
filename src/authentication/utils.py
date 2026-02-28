# ########################FR Auth #################################
# import os
# from datetime import datetime, timedelta, timezone
# from typing import Any

# from jose import jwt

# JWT_SECRET = os.getenv("JWT_SECRET")
# JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
# JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES"))


# def create_access_token(*, subject: str, extra: dict[str, Any] | None = None):
#     now = datetime.now(timezone.utc)
#     exp = now + timedelta(minutes=JWT_EXPIRE_MINUTES)

#     payload: dict[str, Any] = {
#         "sub": subject,                 
#         "iat": int(now.timestamp()),
#         "exp": int(exp.timestamp()),
#     }
#     if extra:
#         payload.update(extra)

#     return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# def decode_access_token(token: str):
#     return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
import os
from cryptography.fernet import Fernet


def _fernet():
    key = os.getenv("GITHUB_TOKEN_ENC_KEY")
    if not key:
        raise RuntimeError("GITHUB_TOKEN_ENC_KEY not set")
    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(token_enc: str) -> str:
    return _fernet().decrypt(token_enc.encode()).decode()