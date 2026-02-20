import os
import requests
from sqlalchemy.orm import Session
from sqlalchemy import select

from authentication.models import User
from authentication.schemas import GitHubUser, UserRead
from authentication.utils import create_access_token


CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI")

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


def _exchange_code_for_token(code: str):
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise RuntimeError("Missing GitHub OAuth env vars")

    token_res = requests.post(
        GITHUB_TOKEN_URL,
        headers={"Accept": "application/json"},
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=15,
    )
    token_res.raise_for_status()

    access_token = token_res.json().get("access_token")
    if not access_token:
        raise ValueError("Token exchange failed")

    return access_token


def _fetch_github_user(access_token: str):
    user_res = requests.get(
        GITHUB_USER_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    user_res.raise_for_status()
    return GitHubUser.model_validate(user_res.json())


def _upsert_user(db: Session, gh_user: GitHubUser):
    stmt = select(User).where(User.github_id == gh_user.github_id)
    user = db.execute(stmt).scalar_one_or_none()

    if user:
        user.username = gh_user.username
        user.name = gh_user.name
    else:
        user = User(
            github_id=gh_user.github_id,
            username=gh_user.username,
            name=gh_user.name,
        )
        db.add(user)

    db.commit()
    db.refresh(user)
    return user


def login_with_github_code(db: Session, code: str):
    access_token = _exchange_code_for_token(code)
    gh_user = _fetch_github_user(access_token)
    user = _upsert_user(db, gh_user)

    jwt_token = create_access_token(
        subject=str(user.id),
        extra={"github_id": user.github_id, "username": user.username},
    )

    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": UserRead.model_validate(user).model_dump(),
    }

# import re
# from sqlalchemy.orm import Session
# from sqlalchemy import select

# from authentication.models import User


# def extract_github_id(sub: str) -> int:
#     # sub مثل: github|12345678
#     m = re.match(r"^github\|(\d+)$", sub or "")
#     if not m:
#         raise ValueError("Not a GitHub login")
#     return int(m.group(1))


# def get_or_create_user(db: Session, claims: dict) -> User:
#     sub = claims["sub"]
#     github_id = extract_github_id(sub)

#     username = (
#         claims.get("nickname")
#         or claims.get("preferred_username")
#         or claims.get("name")
#         or f"github_{github_id}"
#     )

#     name = claims.get("name")

#     stmt = select(User).where(User.github_id == github_id)
#     user = db.execute(stmt).scalar_one_or_none()

#     if user:
#         user.username = username
#         user.name = name
#         db.commit()
#         db.refresh(user)
#         return user

#     user = User(
#         github_id=github_id,
#         username=username,
#         name=name,
#     )

#     db.add(user)
#     db.commit()
#     db.refresh(user)
#     return user

