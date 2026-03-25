import os
import firebase_admin
from firebase_admin import credentials, auth

_initialized = False


def init_firebase():
    global _initialized

    if _initialized:
        return

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")

    if not cred_path:
        raise RuntimeError("FIREBASE_CREDENTIALS_PATH not set")

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

    _initialized = True


def verify_token(id_token: str):
    init_firebase()
    decoded = auth.verify_id_token(id_token)
    return decoded

