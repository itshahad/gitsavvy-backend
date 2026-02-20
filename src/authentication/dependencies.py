# # authentication/dependencies.py

# import os
# from fastapi import Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordBearer
# from jose import JWTError
# from sqlalchemy.orm import Session
# from sqlalchemy import select

# from database import get_db
# from authentication.models import User
# from authentication.utils import decode_access_token

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/github/login")

# def get_current_user(
#     token: str = Depends(oauth2_scheme),
#     db: Session = Depends(get_db),
# ) -> User:
#     try:
#         payload = decode_access_token(token)
#     except JWTError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or expired token",
#         )

#     user_id = payload.get("sub")
#     if not user_id:
#         raise HTTPException(status_code=401, detail="Token missing subject")

#     stmt = select(User).where(User.id == int(user_id))
#     user = db.execute(stmt).scalar_one_or_none()

#     if not user:
#         raise HTTPException(status_code=401, detail="User not found")

#     return user

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session
from sqlalchemy import select

from database import get_db
from authentication.models import User
from authentication.utils import decode_access_token

bearer_scheme = HTTPBearer()

def get_current_user(
    creds = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    token = creds.credentials 
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")

    stmt = select(User).where(User.id == int(user_id))
    user = db.execute(stmt).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

