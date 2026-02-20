# # from fastapi import APIRouter, HTTPException
# # from fastapi.responses import RedirectResponse
# # import os, requests
# # from authentication.schemas import GitHubUser, UserBase

# # router = APIRouter(prefix="/auth/github")



# # @router.get("/login")
# # def github_login():
# #     client_id = os.getenv("GITHUB_CLIENT_ID")
# #     redirect_uri = os.getenv("GITHUB_REDIRECT_URI")
# #     scope = "read:user"

# #     url = (
# #         "https://github.com/login/oauth/authorize"
# #         f"?client_id={client_id}"
# #         f"&redirect_uri={redirect_uri}"
# #         f"&scope={scope}"
# #     )
# #     return RedirectResponse(url)




# # CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
# # CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
# # REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI")

# # @router.get("/callback")
# # def github_callback(code: str):
# #     if not code:
# #         raise HTTPException(status_code=400, detail="Missing code")

# #     # exchange code -> token
# #     token_res = requests.post(
# #         "https://github.com/login/oauth/access_token",
# #         headers={"Accept": "application/json"},
# #         data={
# #             "client_id": CLIENT_ID,
# #             "client_secret": CLIENT_SECRET,
# #             "code": code,
# #             "redirect_uri": REDIRECT_URI,
# #         },
# #         timeout=15,
# #     )
# #     token_res.raise_for_status()

# #     access_token = token_res.json().get("access_token")
# #     if not access_token:
# #         raise HTTPException(status_code=400, detail="Token exchange failed")

# #     # get GitHub user
# #     user_res = requests.get(
# #         "https://api.github.com/user",
# #         headers={"Authorization": f"Bearer {access_token}"},
# #         timeout=15,
# #     )
# #     user_res.raise_for_status()

# #     gh_json = user_res.json()

# #     # parse GitHub JSON
# #     gh_user = GitHubUser.model_validate(gh_json)

# #     # convert to your internal user shape
# #     user_data = UserBase(
# #         github_id=gh_user.github_id,
# #         username=gh_user.username,
# #         name=gh_user.name,
# #     )

# #     return {
# #         "message": "GitHub login success",
# #         "user": user_data.model_dump(),
# #     }



import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from authentication.services import login_with_github_code
from authentication.dependencies import get_current_user
from authentication.schemas import UserRead
from authentication.models import User

router = APIRouter(prefix="/auth/github")


@router.get("/login")
def github_login():
    client_id = os.getenv("GITHUB_CLIENT_ID")
    redirect_uri = os.getenv("GITHUB_REDIRECT_URI")
    scope = "read:user"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Missing GitHub OAuth env vars")

    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
    )
    return RedirectResponse(url)


@router.get("/callback")
def github_callback(code: str, db: Session = Depends(get_db)):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    try:
        return login_with_github_code(db=db, code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="GitHub login failed")


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return current_user


