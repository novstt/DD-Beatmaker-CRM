from decimal import Decimal, ROUND_DOWN
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel
from sqlalchemy import select,or_
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models import Artist,Beat,BeatCredit,BeatProducer,BeatSend,User,UserArtist,Notification
from app.schemas import BeatCreate,BeatUpdate,BeatOut,BeatSendCreate
router=APIRouter()

class BulkBeatUpdate(BaseModel):
    beat_ids: list[int]
    bpm: int | None = None
    musical_key: str | None = None
    status: str | None = None
    add_tag: str | None = None
ALIASES={
    "slv":"slv1","slv1":"slv1","prod_slv":"slv1","prod.slv":"slv1","quikinnnslv":"slv1",
    "deplug":"deplugboy","deplugg":"deplugboy","deplugboy":"deplugboy","de_plug":"deplugboy","de plug":"deplugboy","de-plug":"deplugboy",
    "daddykar":"daddykar_official","daddy kar":"daddykar_official","daddykarofficial":"daddykar_official","daddykar_official":"daddykar_official","daddy-kar":"daddykar_official"
}
DISPLAY={"slv1":"SLV","deplugboy":"DE PLUG","daddykar_official":"DADDY KAR"}

# Known account-name variants. The canonical target above is only a preferred
# username; real test/prod accounts may use a different username while still
# representing the same producer brand. Resolve against all known variants.
USER_VARIANTS={
    "slv1": {"slv1","slv","prod_slv","prod.slv","quikinnnslv"},
    "deplugboy": {"deplugboy","deplug","deplugg","de_plug","de plug","de-plug"},
    "daddykar_official": {"daddykar_official","daddykar","daddykarofficial","daddy kar","daddy-kar"},
}

def key(v): return (v or "").strip().lstrip("@").casefold()

def canonical(v):
    k=key(v); return DISPLAY.get(ALIASES.get(k,k),(v or "").strip().lstrip("@"))

def resolve_user(db,v):
    raw=(v or "").strip()
    if not raw:
        return None
    k=key(raw)

    # 1) Exact username first. This also supports arbitrary usernames that are
    # not in the built-in alias list.
    u=db.scalar(select(User).where(User.username.ilike(raw.lstrip("@"))))
    if u:
        return u

    # 2) Resolve known producer aliases. Try every known username variant for
    # the canonical producer instead of assuming a single production username.
    target=ALIASES.get(k)
    if target:
        candidates=USER_VARIANTS.get(target,{target})
        for candidate in candidates:
            u=db.scalar(select(User).where(User.username.ilike(candidate)))
            if u:
                return u

    # 3) Exact email (case-insensitive).
    email_value=raw.lower() if "@" in raw else k
    u=db.scalar(select(User).where(User.email.ilike(email_value)))
    if u:
        return u

    # 4) As a final safety net for names such as "DADDY KAR" / "DE PLUG",
    # compare canonicalized usernames for all registered users. This makes
    # producer lookup robust when the real account username differs from the
    # alias table but normalizes to the same display identity.
    users=db.scalars(select(User).order_by(User.id)).all()
    requested=canonical(raw).casefold()
    for candidate_user in users:
        if canonical(candidate_user.username).casefold()==requested:
            return candidate_user

    return None
def pct_list(n):
    if n<=0:return []
    base=(Decimal("100")/Decimal(n)).quantize(Decimal("0.01"),rounding=ROUND_DOWN)
    return [base]*(n-1)+[Decimal("100")-base*Decimal(n-1)]
def beat_payload(beat,db):
    rows=db.scalars(select(BeatProducer).where(BeatProducer.beat_id==beat.id).order_by(BeatProducer.id)).all()
    credits=db.scalars(select(BeatCredit).where(BeatCredit.beat_id==beat.id).order_by(BeatCredit.id)).all()
    producers=[]
    for p in rows:
        u=db.get(User,p.user_id); producers.append({"user_id":p.user_id,"username":u.username if u else None,"display_name":DISPLAY.get(u.username,u.username) if u else None,"share_percent":p.share_percent})
    for c in credits:
        producers.append({"user_id":c.user_id,"username":c.user.username if c.user else c.handle,"display_name":c.display_name,"share_percent":c.share_percent})
    owner=db.get(User,beat.user_id); messenger=db.get(User,beat.messenger_id) if beat.messenger_id else None
    lead = next((p for p in producers if p.get("username")), None)
    return {"id":beat.id,"user_id":beat.user_id,"name":beat.name,"bpm":beat.bpm,"musical_key":beat.musical_key,"status":beat.status,"google_drive_link":None,"created_at":beat.created_at,"producer_username":(lead or {}).get("username"),"messenger_id":beat.messenger_id,"messenger_username":messenger.username if messenger else None,"producers":producers}
@router.get("",response_model=list[BeatOut])
def list_beats(search:str=Query(default=""),limit:int=Query(default=100,ge=1,le=200),offset:int=Query(default=0,ge=0),db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    stmt=select(Beat).outerjoin(BeatProducer, BeatProducer.beat_id==Beat.id).where(or_(Beat.user_id==current_user.id,Beat.messenger_id==current_user.id,BeatProducer.user_id==current_user.id)).distinct().order_by(Beat.created_at.desc()).offset(offset).limit(limit)
    if search.strip(): stmt=stmt.where(Beat.name.ilike(f"%{search.strip()}%"))
    return [beat_payload(b,db) for b in db.scalars(stmt).all()]
@router.post("",response_model=BeatOut,status_code=201)
def create_beat(data:BeatCreate,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    # The creator owns the CRM record, but is NOT automatically a producer.
    # Only names explicitly entered in Producer / Co-producers receive credits
    # and revenue shares. This prevents the current account from silently
    # becoming a co-producer or messenger.
    producer=resolve_user(db,data.producer_username)
    if not producer:
        raise HTTPException(404,"Producer account not found")
    users=[]; external=[]; seen_ids=set(); seen_external=set()
    def add_user(u):
        if u and u.id not in seen_ids:
            users.append(u); seen_ids.add(u.id)
    add_user(producer)
    for raw in data.co_producer_usernames:
        raw=(raw or '').strip()
        if not raw: continue
        u=resolve_user(db,raw)
        if u: add_user(u)
        elif key(raw) not in seen_external:
            external.append(raw); seen_external.add(key(raw))
    shares=pct_list(len(users)+len(external))
    # user_id is the workspace owner/creator, not a producer credit.
    beat=Beat(user_id=current_user.id,messenger_id=None,name=data.name.strip(),bpm=data.bpm,musical_key=data.musical_key.strip() if data.musical_key else None,status=data.status)
    db.add(beat); db.flush()
    for idx,u in enumerate(users):
        db.add(BeatProducer(beat_id=beat.id,user_id=u.id,share_percent=shares[idx]))
        if u.id != current_user.id:
            db.add(Notification(user_id=u.id,type="co_producer_added",title="You were added to a beat",message=f'{current_user.username} added you to "{beat.name}". Your share is {shares[idx]}%.',is_read=False))
    for idx,raw in enumerate(external,start=len(users)):
        db.add(BeatCredit(beat_id=beat.id,user_id=None,display_name=canonical(raw),handle=raw if raw.startswith("@") else None,share_percent=shares[idx]))
    db.commit(); db.refresh(beat); return beat_payload(beat,db)

@router.put("/{beat_id}",response_model=BeatOut)
def update_beat(beat_id:int,data:BeatUpdate,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    beat=db.scalar(select(Beat).outerjoin(BeatProducer,BeatProducer.beat_id==Beat.id).where(Beat.id==beat_id,or_(Beat.user_id==current_user.id,Beat.messenger_id==current_user.id,BeatProducer.user_id==current_user.id)).distinct())
    if not beat: raise HTTPException(404,"Beat not found")
    producer=resolve_user(db,data.producer_username)
    if not producer: raise HTTPException(404,"Producer account not found")
    old_registered_ids={p.user_id for p in list(beat.producers) if p.user_id}
    users=[]; external=[]; seen_ids=set(); seen_external=set()
    def add_user(u):
        if u and u.id not in seen_ids:
            users.append(u); seen_ids.add(u.id)
    # Do not add the editor automatically. Credits come only from the fields.
    add_user(producer)
    for raw in data.co_producer_usernames:
        raw=(raw or '').strip()
        if not raw: continue
        u=resolve_user(db,raw)
        if u: add_user(u)
        elif key(raw) not in seen_external:
            external.append(raw); seen_external.add(key(raw))
    shares=pct_list(len(users)+len(external))
    # Keep the original workspace owner when possible. For old records created
    # with the previous bug, ownership remains the account that created/edited it;
    # the producer list is now the single source of truth for credits and splits.
    beat.messenger_id=None; beat.name=data.name.strip(); beat.bpm=data.bpm; beat.musical_key=data.musical_key.strip() if data.musical_key else None; beat.status=data.status
    for p in list(beat.producers): db.delete(p)
    for c in list(beat.credits): db.delete(c)
    db.flush()
    for idx,u in enumerate(users):
        db.add(BeatProducer(beat_id=beat.id,user_id=u.id,share_percent=shares[idx]))
        if u.id not in old_registered_ids and u.id != current_user.id:
            db.add(Notification(user_id=u.id,type="co_producer_added",title="You were added to a beat",message=f'{current_user.username} added you to "{beat.name}". Your share is {shares[idx]}%.',is_read=False))
    for idx,raw in enumerate(external,start=len(users)):
        db.add(BeatCredit(beat_id=beat.id,user_id=None,display_name=canonical(raw),handle=raw if raw.startswith("@") else None,share_percent=shares[idx]))
    db.commit(); db.refresh(beat); return beat_payload(beat,db)

@router.delete("/{beat_id}")
def delete_beat(
    beat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Beat)
        .outerjoin(BeatProducer, BeatProducer.beat_id == Beat.id)
        .where(
            Beat.id == beat_id,
            or_(
                Beat.user_id == current_user.id,
                Beat.messenger_id == current_user.id,
                BeatProducer.user_id == current_user.id,
            ),
        )
        .distinct()
    )
    beat = db.scalar(stmt)
    if not beat:
        raise HTTPException(404, "Beat not found")
    beat.status = "archived"
    db.commit()
    return {"status": "archived", "beat_id": beat_id}
@router.post("/send",status_code=201)
def send_beat(data:BeatSendCreate,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    beat=db.scalar(select(Beat).where(Beat.id==data.beat_id,or_(Beat.user_id==current_user.id,Beat.messenger_id==current_user.id)))
    artist=db.get(Artist,data.artist_id)
    link=db.scalar(select(UserArtist).where(UserArtist.user_id==current_user.id,UserArtist.artist_id==data.artist_id))
    if not beat or not artist or not link: raise HTTPException(404,"Beat or artist not found")
    existing=db.scalar(select(BeatSend).where(BeatSend.user_id==current_user.id,BeatSend.artist_id==data.artist_id,BeatSend.beat_id==data.beat_id))
    if existing:return {"status":"already_sent","send_id":existing.id}
    db.add(BeatSend(user_id=current_user.id,artist_id=data.artist_id,artist_contact_id=link.id,beat_id=data.beat_id,status="sent")); db.commit(); return {"status":"ok"}

@router.post("/bulk-update")
def bulk_update(data:BulkBeatUpdate,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    if not data.beat_ids: raise HTTPException(422,"No beats selected")
    if data.status is not None and data.status not in {"available","archived"}:
        raise HTTPException(422,"Unsupported beat status")
    if data.bpm is not None and (data.bpm < 1 or data.bpm > 400):
        raise HTTPException(422,"BPM must be between 1 and 400")
    rows = list(
        db.scalars(
            select(Beat)
            .outerjoin(
                BeatProducer,
                BeatProducer.beat_id == Beat.id,
            )
            .where(
                Beat.id.in_(data.beat_ids),
                or_(
                    Beat.user_id == current_user.id,
                    Beat.messenger_id == current_user.id,
                    BeatProducer.user_id == current_user.id,
                ),
            )
            .distinct()
        ).all()
    )
    if len(rows)!=len(set(data.beat_ids)):
        raise HTTPException(403,"One or more selected beats are not accessible")
    tag_name=(data.add_tag or "").strip().lower()[:60]
    updated=0
    for beat in rows:
        if data.bpm is not None: beat.bpm=data.bpm
        if data.musical_key is not None: beat.musical_key=data.musical_key.strip() or None
        if data.status is not None: beat.status=data.status
        if tag_name:
            from app.workspace_models import WorkspaceTag
            existing=db.scalar(select(WorkspaceTag).where(WorkspaceTag.user_id==current_user.id,WorkspaceTag.beat_id==beat.id,WorkspaceTag.name==tag_name))
            if not existing: db.add(WorkspaceTag(user_id=current_user.id,beat_id=beat.id,name=tag_name))
        updated+=1
    db.commit()
    return {"status":"ok","updated":updated}
