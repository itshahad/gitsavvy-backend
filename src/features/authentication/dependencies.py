

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.database import get_db
from .firebase_auth import verify_token
from src.features.authentication.models import User

# security = HTTPBearer(auto_error=False)


# def get_current_claims(
#     creds: HTTPAuthorizationCredentials = Depends(security),
# ):
#     if not creds:
#         raise HTTPException(status_code=401, detail="Missing token")

#     try:
#         decoded = verify_token(creds.credentials)
#     except Exception:
#         raise HTTPException(status_code=401, detail="Invalid Firebase token")

#     provider = decoded.get("firebase", {}).get("sign_in_provider")

#     if provider != "github.com":
#         raise HTTPException(status_code=403, detail="GitHub login required")

#     return decoded


# def get_current_user(
#     claims=Depends(get_current_claims),
#     db: Session = Depends(get_db),
# ):
#     firebase_uid = claims["uid"]

#     user = db.query(User).filter(
#         User.firebase_uid == firebase_uid
#     ).first()

#     if not user:
#         raise HTTPException(
#             status_code=428,
#             detail="First login requires /auth/github/sync",
#         )

#     return user

security = HTTPBearer(auto_error=False)


def get_current_claims(
    creds: HTTPAuthorizationCredentials = Depends(security),
):
    if not creds:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        decoded = verify_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

    provider = decoded.get("firebase", {}).get("sign_in_provider")

    if provider != "github.com":
        raise HTTPException(status_code=403, detail="GitHub login required")

    return decoded


def get_current_user(
    claims=Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    firebase_uid = claims["uid"]

    user = db.query(User).filter(
        User.firebase_uid == firebase_uid
    ).first()

    if not user:
        raise HTTPException(
            status_code=428,
            detail="First login requires /auth/github/sync",
        )

    return user


def get_current_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    return user