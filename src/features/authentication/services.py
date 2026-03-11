

import os
import requests
from sqlalchemy.orm import Session

from src.features.authentication.models import User
from src.features.authentication.schemas import GitHubUser
from src.features.authentication.utils import encrypt_token


GITHUB_USER_API = "https://api.github.com/user"


def get_role_from_github_id(github_id: int) -> str:
    admin_ids_str = os.getenv("ADMIN_GITHUB_IDS", "")
    admin_ids = {
        int(x.strip())
        for x in admin_ids_str.split(",")
        if x.strip()
    }

    if github_id in admin_ids:
        return "admin"

    return "user"


def fetch_github_user(access_token: str) -> GitHubUser:
    r = requests.get(
        GITHUB_USER_API,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=15,
    )

    if r.status_code != 200:
        raise ValueError("Invalid GitHub token")

    return GitHubUser.model_validate(r.json())


def sync_user_first_login(
    db: Session,
    *,
    firebase_uid: str,
    github_access_token: str,
) -> User:

    gh_user = fetch_github_user(github_access_token)

    user = db.query(User).filter(
        User.firebase_uid == firebase_uid
    ).first()

    token_enc = encrypt_token(github_access_token)
    role = get_role_from_github_id(gh_user.github_id)

    if not user:
        user = User(
            firebase_uid=firebase_uid,
            github_id=gh_user.github_id,
            username=gh_user.username,
            name=gh_user.name,
            github_access_token_enc=token_enc,
            role=role,
        )
        db.add(user)
    else:
        user.github_id = gh_user.github_id
        user.username = gh_user.username
        user.name = gh_user.name
        user.github_access_token_enc = token_enc
        user.role = role

    db.commit()
    db.refresh(user)
    return user






