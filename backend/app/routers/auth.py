from datetime import datetime, timezone
from collections import defaultdict, deque
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.auth import create_access_token,get_current_user,hash_password,verify_password
from app.database import get_db
from app.models import User
from app.schemas import LoginIn,RegisterIn,Token,UserOut,UserSettingsUpdate
router=APIRouter()
_LOGIN_ATTEMPTS=defaultdict(deque)

def _check_rate(email):
    now=time.time(); q=_LOGIN_ATTEMPTS[email]
    while q and now-q[0]>60: q.popleft()
    if len(q)>=8: raise HTTPException(429,"Too many login attempts. Try again in a minute.")
    q.append(now)
@router.post("/register",response_model=UserOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(get_db)):
    email=str(data.email).lower(); username=data.username.strip()
    if db.scalar(select(User).where(or_(User.email==email,User.username==username))): raise HTTPException(409,"Username or email already exists")
    u=User(username=username,email=email,password_hash=hash_password(data.password)); db.add(u); db.commit(); db.refresh(u); return u
@router.post("/login",response_model=Token)
def login(data:LoginIn,db:Session=Depends(get_db)):
    email=str(data.email).lower()
    _check_rate(email)
    u=db.scalar(select(User).where(User.email==email))
    if not u or not verify_password(data.password,u.password_hash): raise HTTPException(status.HTTP_401_UNAUTHORIZED,"Invalid email or password")
    if not u.is_active: raise HTTPException(403,"Account is disabled")
    u.last_login=datetime.now(timezone.utc); db.commit(); return Token(access_token=create_access_token(u.id))
@router.get("/me",response_model=UserOut)
def me(current_user=Depends(get_current_user)): return current_user
@router.put("/settings",response_model=UserOut)
def settings(data:UserSettingsUpdate,db:Session=Depends(get_db),current_user=Depends(get_current_user)):
    if data.theme and data.theme not in {"dark","light"}: raise HTTPException(422,"Invalid theme")
    if data.currency and data.currency not in {"USD","EUR","CHF"}: raise HTTPException(422,"Invalid currency")
    if data.theme: current_user.theme=data.theme
    if data.currency: current_user.currency=data.currency
    db.commit(); db.refresh(current_user); return current_user
