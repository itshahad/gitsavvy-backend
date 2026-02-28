


import requests
from sqlalchemy.orm import Session

from authentication.models import User
from authentication.schemas import GitHubUser
from authentication.utils import encrypt_token


GITHUB_USER_API = "https://api.github.com/user"


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

    if not user:
        user = User(
            firebase_uid=firebase_uid,
            github_id=gh_user.github_id,
            username=gh_user.username,
            name=gh_user.name,
            github_access_token_enc=token_enc,
        )
        db.add(user)
    else:
        user.github_id = gh_user.github_id
        user.username = gh_user.username
        user.name = gh_user.name
        user.github_access_token_enc = token_enc

    db.commit()
    db.refresh(user)
    return user








