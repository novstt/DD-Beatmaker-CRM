from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User

ALGORITHM="HS256"
password_hash=PasswordHash.recommended()
bearer=HTTPBearer(auto_error=False)

def hash_password(p): return password_hash.hash(p)
def verify_password(p,h): return password_hash.verify(p,h)
def create_access_token(user_id:int):
    exp=datetime.now(timezone.utc)+timedelta(days=30)
    return jwt.encode({"sub":str(user_id),"exp":exp},settings.JWT_SECRET,algorithm=ALGORITHM)

def get_current_user(credentials:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    if not credentials: raise HTTPException(status_code=401,detail="Not authenticated")
    try: payload=jwt.decode(credentials.credentials,settings.JWT_SECRET,algorithms=[ALGORITHM]); uid=int(payload["sub"])
    except (JWTError,KeyError,ValueError): raise HTTPException(status_code=401,detail="Invalid token")
    user=db.get(User,uid)
    if not user or not user.is_active: raise HTTPException(status_code=401,detail="Account unavailable")
    return user

def ensure_admin(db:Session):
    user=db.scalar(select(User).where(User.email.ilike(settings.ADMIN_EMAIL)))
    if user and not user.is_admin:
        user.is_admin=True; db.commit()

def require_admin(current_user=Depends(get_current_user)):
    if current_user.email.casefold()!=settings.ADMIN_EMAIL.casefold():
        raise HTTPException(status_code=403,detail="Admin access required")
    return current_user
