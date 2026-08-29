from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import require_admin
from app.database import get_db
from app.models import User
from app.workspace_models import AdminAuditLog
router=APIRouter()
@router.get("/users")
def users(db:Session=Depends(get_db),_:User=Depends(require_admin)):
    return [{"id":u.id,"username":u.username,"email":u.email,"is_admin":u.is_admin,"is_active":u.is_active,"theme":u.theme,"created_at":u.created_at,"last_login":u.last_login} for u in db.scalars(select(User).order_by(User.created_at.desc())).all()]
@router.post("/users/{user_id}/toggle")
def toggle(user_id:int,db:Session=Depends(get_db),_:User=Depends(require_admin)):
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,"User not found")
    if u.email.casefold()=="quikinnnproducer@gmail.com": raise HTTPException(400,"Primary admin cannot be disabled")
    u.is_active=not u.is_active
    db.add(AdminAuditLog(admin_user_id=_.id, target_user_id=u.id, action="toggle_user", detail=f"is_active={u.is_active}"))
    db.commit(); return {"id":u.id,"is_active":u.is_active}


@router.get('/audit')
def audit(limit:int=100,db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    rows=db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(max(1,min(limit,500)))).all()
    return [{'id':r.id,'admin_user_id':r.admin_user_id,'target_user_id':r.target_user_id,'action':r.action,'detail':r.detail,'created_at':r.created_at} for r in rows]

@router.get('/health')
def system_health(db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    try:
        from sqlalchemy import text
        db.execute(text('SELECT 1'))
        db_ok=True
    except Exception:
        db_ok=False
    from app.routers.system import APP_VERSION
    return {'api':'ok','database':'ok' if db_ok else 'error','version':APP_VERSION}


@router.get('/overview')
def overview(db:Session=Depends(get_db),admin:User=Depends(require_admin)):
    from sqlalchemy import func
    from app.models import Artist, Beat, License
    users=db.scalar(select(func.count(User.id))) or 0
    active=db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    beats=db.scalar(select(func.count(Beat.id))) or 0
    artists=db.scalar(select(func.count(Artist.id))) or 0
    licenses=db.scalar(select(func.count(License.id))) or 0
    paid=db.scalar(select(func.count(License.id)).where(License.status=='paid')) or 0
    return {'users':users,'active_users':active,'artists':artists,'beats':beats,'licenses':licenses,'paid_licenses':paid,'version':__import__('app.routers.system',fromlist=['APP_VERSION']).APP_VERSION}
