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
