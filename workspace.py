from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models import User, UserArtist, Artist, Beat, License, LicenseSplit, BeatSend
from app.workspace_models import WorkspaceFavorite, WorkspaceFollowUp, WorkspaceGoal, WorkspaceTag

router=APIRouter()

class FollowUpIn(BaseModel):
    artist_id:int
    due_at:datetime
    title:str=Field(default='Follow up',max_length=160)
    notes:str|None=None
    done:bool=False
class GoalIn(BaseModel):
    title:str=Field(min_length=1,max_length=160)
    target:Decimal
    current:Decimal=Decimal('0')
    period:str='month'
    currency:str='USD'
class FavoriteIn(BaseModel):
    entity_type:str
    entity_id:int
class TagIn(BaseModel):
    name:str=Field(min_length=1,max_length=60)

def _period_start(period, now):
    if period == 'year':
        return datetime(now.year, 1, 1, tzinfo=timezone.utc)
    if period == 'all':
        return None
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)

def _goal_metric(title):
    t=(title or '').casefold()
    if any(k in t for k in ['license','licenses','sale','sales']): return 'licenses'
    if any(k in t for k in ['artist','artists']): return 'artists'
    if any(k in t for k in ['beat','beats','sent']): return 'beats'
    return 'revenue'

@router.get('/overview')
def overview(db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    now=datetime.now(timezone.utc)
    followups=list(db.scalars(select(WorkspaceFollowUp).where(WorkspaceFollowUp.user_id==current_user.id,WorkspaceFollowUp.done.is_(False)).order_by(WorkspaceFollowUp.due_at.asc()).limit(8)).all())
    goals=list(db.scalars(select(WorkspaceGoal).where(WorkspaceGoal.user_id==current_user.id).order_by(WorkspaceGoal.created_at.desc()).limit(8)).all())
    favs=list(db.scalars(select(WorkspaceFavorite).where(WorkspaceFavorite.user_id==current_user.id)).all())
    due=sum(1 for x in followups if x.due_at <= now)
    # Personal revenue is based on immutable split amounts, including sales
    # recorded by collaborators.
    licenses=list(db.scalars(select(License).where(License.user_id==current_user.id, License.status!='void')).all())
    earned_split_rows=list(db.execute(
        select(LicenseSplit, License)
        .join(License, License.id==LicenseSplit.license_id)
        .where(LicenseSplit.user_id==current_user.id, License.status!='void')
    ).all())
    user_artists=list(db.scalars(select(UserArtist).where(UserArtist.user_id==current_user.id,UserArtist.status!='archived')).all())
    sends=list(db.scalars(select(BeatSend).where(BeatSend.user_id==current_user.id)).all())
    goal_out=[]
    for g in goals:
        metric=_goal_metric(g.title)
        started=g.created_at or now
        goal_currency=(getattr(g,'currency',None) or 'USD').upper()
        if metric=='revenue':
            current=sum((Decimal(str(split.amount)) for split, sale in earned_split_rows
                         if sale.status=='paid' and sale.currency==goal_currency
                         and sale.purchased_at and sale.purchased_at>=started), Decimal('0'))
        elif metric=='licenses':
            current=Decimal(str(sum(1 for x in licenses if x.status=='paid' and x.purchased_at and x.purchased_at>=started)))
        elif metric=='artists':
            current=Decimal(str(sum(1 for x in user_artists if x.created_at and x.created_at>=started)))
        else:
            current=Decimal(str(sum(1 for x in sends if x.sent_at and x.sent_at>=started)))
        # Never let a goal exceed 100% visually, but retain the full current value for history.
        target=Decimal(str(g.target or 0))
        pct=(current/target*Decimal('100')) if target>0 else Decimal('0')
        completed=bool(target>0 and current>=target)
        goal_out.append({'id':g.id,'title':g.title,'target':str(target),'current':str(current),'currency':goal_currency,'period':g.period,'metric':metric,'progress_percent':str(min(pct,Decimal('100'))),'completed':completed,'created_at':started.isoformat()})
    return {'followups':[{'id':x.id,'artist_id':x.artist_id,'due_at':x.due_at,'title':x.title,'notes':x.notes,'done':x.done} for x in followups], 'followups_due':due, 'goals':goal_out, 'favorites':[{'entity_type':x.entity_type,'entity_id':x.entity_id} for x in favs]}

@router.get('/artists/{artist_id}/timeline')
def artist_timeline(artist_id:int, db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    link=db.scalar(select(UserArtist).where(UserArtist.user_id==current_user.id,UserArtist.artist_id==artist_id,UserArtist.status!='archived'))
    if not link:
        raise HTTPException(404,'Artist not found in your list')
    events=[]
    sends=db.execute(select(BeatSend,Beat).join(Beat,Beat.id==BeatSend.beat_id).where(BeatSend.user_id==current_user.id,BeatSend.artist_id==artist_id).order_by(BeatSend.sent_at.desc())).all()
    for send,beat in sends:
        events.append({'kind':'beat_sent','at':send.sent_at.isoformat() if send.sent_at else None,'title':'Beat sent','detail':beat.name,'status':send.status})
    licenses=list(db.scalars(select(License).where(License.user_id==current_user.id,License.artist_id==artist_id).order_by(License.purchased_at.desc())).all())
    for lic in licenses:
        events.append({'kind':'license','at':lic.purchased_at.isoformat() if lic.purchased_at else None,'title':'License sold','detail':f"{str(lic.license_type).upper()} • ${lic.price}",'status':lic.status,'license_id':lic.id})
    followups=list(db.scalars(select(WorkspaceFollowUp).where(WorkspaceFollowUp.user_id==current_user.id,WorkspaceFollowUp.artist_id==artist_id).order_by(WorkspaceFollowUp.due_at.desc())).all())
    for f in followups:
        events.append({'kind':'followup','at':f.due_at.isoformat() if f.due_at else None,'title':f.title,'detail':f.notes or 'Follow-up','status':'done' if f.done else 'pending'})
    events.sort(key=lambda x:x.get('at') or '', reverse=True)
    return {'artist_id':artist_id,'events':events}

@router.post('/followups')
def create_followup(data:FollowUpIn,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    link=db.scalar(select(UserArtist).where(UserArtist.user_id==current_user.id,UserArtist.artist_id==data.artist_id,UserArtist.status!='archived'))
    if not link: raise HTTPException(404,'Artist not found in your list')
    f=WorkspaceFollowUp(user_id=current_user.id,artist_id=data.artist_id,due_at=data.due_at,title=data.title.strip() or 'Follow up',notes=data.notes,done=data.done)
    db.add(f); db.commit(); db.refresh(f)
    return {'id':f.id,'artist_id':f.artist_id,'due_at':f.due_at,'title':f.title,'notes':f.notes,'done':f.done}

@router.post('/followups/{followup_id}/done')
def finish_followup(followup_id:int,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    f=db.scalar(select(WorkspaceFollowUp).where(WorkspaceFollowUp.id==followup_id,WorkspaceFollowUp.user_id==current_user.id))
    if not f: raise HTTPException(404,'Follow-up not found')
    f.done=True; db.commit(); return {'status':'ok','id':f.id}

@router.post('/goals')
def create_goal(data:GoalIn,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    if data.target <= 0: raise HTTPException(422,'Goal target must be greater than 0')
    currency=(data.currency or 'USD').upper()
    if currency not in {'USD','EUR','CHF'}: raise HTTPException(422,'Unsupported goal currency')
    g=WorkspaceGoal(user_id=current_user.id,title=data.title.strip(),target=data.target,current=Decimal('0'),period=data.period,currency=currency)
    db.add(g); db.commit(); db.refresh(g)
    return {'id':g.id,'title':g.title,'target':str(g.target),'current':'0','period':g.period}

@router.put('/goals/{goal_id}')
def update_goal(goal_id:int,data:GoalIn,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    g=db.scalar(select(WorkspaceGoal).where(WorkspaceGoal.id==goal_id,WorkspaceGoal.user_id==current_user.id))
    if not g: raise HTTPException(404,'Goal not found')
    currency=(data.currency or getattr(g,'currency',None) or 'USD').upper()
    if currency not in {'USD','EUR','CHF'}: raise HTTPException(422,'Unsupported goal currency')
    g.title=data.title.strip(); g.target=data.target; g.period=data.period; g.currency=currency
    # Goal progress is always measured from the original creation date. Editing a target
    # must not wipe the progress already earned since that date.
    db.commit(); db.refresh(g)
    return {'id':g.id,'title':g.title,'target':str(g.target),'current':str(g.current),'period':g.period}

@router.delete('/goals/{goal_id}')
def delete_goal(goal_id:int,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    g=db.scalar(select(WorkspaceGoal).where(WorkspaceGoal.id==goal_id,WorkspaceGoal.user_id==current_user.id))
    if not g: raise HTTPException(404,'Goal not found')
    db.delete(g); db.commit(); return {'status':'deleted','id':goal_id}

@router.post('/favorites')
def toggle_favorite(data:FavoriteIn,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    existing=db.scalar(select(WorkspaceFavorite).where(WorkspaceFavorite.user_id==current_user.id,WorkspaceFavorite.entity_type==data.entity_type,WorkspaceFavorite.entity_id==data.entity_id))
    if existing:
        db.delete(existing); db.commit(); return {'favorite':False}
    db.add(WorkspaceFavorite(user_id=current_user.id,entity_type=data.entity_type,entity_id=data.entity_id)); db.commit(); return {'favorite':True}

@router.get('/favorites')
def favorites(db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    rows=db.scalars(select(WorkspaceFavorite).where(WorkspaceFavorite.user_id==current_user.id)).all()
    return [{'entity_type':x.entity_type,'entity_id':x.entity_id} for x in rows]

@router.post('/beats/{beat_id}/tags')
def add_tag(beat_id:int,data:TagIn,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    beat=db.scalar(select(Beat).where(Beat.id==beat_id, (Beat.user_id==current_user.id)|(Beat.messenger_id==current_user.id)))
    if not beat: raise HTTPException(404,'Beat not found')
    name=data.name.strip().lower()
    row=db.scalar(select(WorkspaceTag).where(WorkspaceTag.user_id==current_user.id,WorkspaceTag.beat_id==beat_id,WorkspaceTag.name==name))
    if not row: db.add(WorkspaceTag(user_id=current_user.id,beat_id=beat_id,name=name)); db.commit()
    return {'status':'ok','beat_id':beat_id,'tag':name}

@router.get('/beats/{beat_id}/tags')
def list_tags(beat_id:int,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    return [x.name for x in db.scalars(select(WorkspaceTag).where(WorkspaceTag.user_id==current_user.id,WorkspaceTag.beat_id==beat_id).order_by(WorkspaceTag.name)).all()]

@router.get('/trash')
def trash(db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    artists=db.execute(select(UserArtist,Artist).join(Artist,Artist.id==UserArtist.artist_id).where(UserArtist.user_id==current_user.id,UserArtist.status=='archived')).all()
    beats=db.scalars(select(Beat).where((Beat.user_id==current_user.id)|(Beat.messenger_id==current_user.id),Beat.status=='archived')).all()
    return {'artists':[{'id':a.id,'name':artist.name} for a,artist in artists], 'beats':[{'id':b.id,'name':b.name} for b in beats]}

@router.post('/trash/{entity_type}/{entity_id}/restore')
def restore(entity_type:str,entity_id:int,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    if entity_type=='artist':
        row=db.scalar(select(UserArtist).where(UserArtist.user_id==current_user.id,UserArtist.artist_id==entity_id,UserArtist.status=='archived'))
        if not row: raise HTTPException(404,'Archived artist not found')
        row.status='new'; db.commit(); return {'status':'restored'}
    if entity_type=='beat':
        row=db.scalar(select(Beat).where(Beat.id==entity_id, (Beat.user_id==current_user.id)|(Beat.messenger_id==current_user.id),Beat.status=='archived'))
        if not row: raise HTTPException(404,'Archived beat not found')
        row.status='available'; db.commit(); return {'status':'restored'}
    raise HTTPException(400,'Unsupported trash entity')

@router.get('/backup/export')
def export_backup(db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    artists=db.execute(select(UserArtist,Artist).join(Artist,Artist.id==UserArtist.artist_id).where(UserArtist.user_id==current_user.id)).all()
    beats=db.scalars(select(Beat).where((Beat.user_id==current_user.id)|(Beat.messenger_id==current_user.id))).all()
    licenses=db.scalars(select(License).where(License.user_id==current_user.id).order_by(License.id)).all()
    beat_rows=[]
    for b in beats:
        beat_rows.append({'id':b.id,'name':b.name,'bpm':b.bpm,'musical_key':b.musical_key,'status':b.status,'producer_username':(db.get(User,b.user_id).username if b.user_id else None),'messenger_username':(db.get(User,b.messenger_id).username if b.messenger_id else None)})
    artist_name_by_id={artist.id:artist.name for link,artist in artists}
    beat_name_by_id={b.id:b.name for b in beats}
    return {'version':'v27','exported_at':datetime.now(timezone.utc),'user':{'username':current_user.username,'email':current_user.email,'currency':current_user.currency,'theme':current_user.theme},'artists':[{'id':a.id,'name':artist.name,'status':a.status,'platform':a.platform,'artist_username':a.artist_username,'notes':a.notes} for a,artist in artists],'beats':beat_rows,'licenses':[{'id':x.id,'artist_name':artist_name_by_id.get(x.artist_id),'beat_name':beat_name_by_id.get(x.beat_id),'type':x.license_type,'price':str(x.price),'currency':x.currency,'status':x.status,'notes':x.notes,'purchased_at':x.purchased_at} for x in licenses]}

@router.get('/artists/{artist_id}/score')
def artist_score(artist_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    link=db.scalar(select(UserArtist).where(UserArtist.user_id==current_user.id,UserArtist.artist_id==artist_id,UserArtist.status!='archived'))
    if not link: raise HTTPException(404,'Artist not found in your list')
    sales=list(db.scalars(select(License).where(License.user_id==current_user.id,License.artist_id==artist_id)).all())
    paid=[s for s in sales if s.status=='paid']
    sends=list(db.scalars(select(BeatSend).where(BeatSend.user_id==current_user.id,BeatSend.artist_id==artist_id)).all())
    followups=list(db.scalars(select(WorkspaceFollowUp).where(WorkspaceFollowUp.user_id==current_user.id,WorkspaceFollowUp.artist_id==artist_id)).all())

    score=0
    reasons=[]
    if paid:
        score += min(45, len(paid)*15)
        reasons.append(f'{len(paid)} paid license(s)')
        if len(paid) >= 2:
            score += 10
            reasons.append('repeat buyer')
    if sends:
        score += min(15, len(sends)*3)
        reasons.append(f'{len(sends)} beat send(s)')
    completed=sum(1 for f in followups if f.done)
    open_fups=sum(1 for f in followups if not f.done)
    score += min(10, completed*3)
    if completed: reasons.append(f'{completed} completed follow-up(s)')
    if open_fups == 0 and followups:
        score += 5
        reasons.append('no overdue follow-ups')
    if link.cash_ready:
        score += 8
        reasons.append('cash-ready')
    status=(link.message_status or '').casefold()
    if status in {'replied','interested','active'}:
        score += 7
        reasons.append(f'active status: {status}')
    # recency: recent paid purchase or beat send is a strong signal
    from datetime import datetime, timezone, timedelta
    recent_dt=None
    for obj in paid+sends:
        for attr in ('purchased_at','sent_at','created_at'):
            d=getattr(obj,attr,None)
            if d and (recent_dt is None or d>recent_dt): recent_dt=d
    if recent_dt:
        if recent_dt.tzinfo is None: recent_dt=recent_dt.replace(tzinfo=timezone.utc)
        age=(datetime.now(timezone.utc)-recent_dt).days
        if age <= 7:
            score += 10; reasons.append('recent activity (7d)')
        elif age <= 30:
            score += 5; reasons.append('recent activity (30d)')
    score=min(100,score)
    category='VIP' if score>=85 and len(paid)>=2 else ('HOT' if score>=70 else ('WARM' if score>=35 else 'COLD'))
    return {'artist_id':artist_id,'score':score,'category':category,'reasons':reasons}

@router.post('/backup/import')
def import_backup(payload:dict,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    if not isinstance(payload,dict) or payload.get('version') is None:
        raise HTTPException(400,'Invalid D&D backup')
    imported={'artists':0,'beats':0,'licenses':0,'licenses_skipped':0}
    artist_map={}
    existing_artists={a.normalized_name:a for a in db.scalars(select(Artist).where(Artist.created_by==current_user.id)).all()}
    for row in payload.get('artists') or []:
        name=str(row.get('name') or '').strip(); norm=name.casefold()
        if not name: continue
        a=existing_artists.get(norm)
        if not a:
            a=Artist(name=name,normalized_name=norm,created_by=current_user.id); db.add(a); db.flush()
            db.add(UserArtist(user_id=current_user.id,artist_id=a.id,status=row.get('status') or 'new',platform=row.get('platform'),artist_username=row.get('artist_username'),notes=row.get('notes')))
            existing_artists[norm]=a; imported['artists']+=1
        artist_map[str(row.get('id'))]=a.id
    db.flush()
    beat_map={}
    existing_beats={b.name.casefold():b for b in db.scalars(select(Beat).where(Beat.user_id==current_user.id)).all()}
    for row in payload.get('beats') or []:
        name=str(row.get('name') or '').strip(); norm=name.casefold()
        if not name: continue
        b=existing_beats.get(norm)
        if not b:
            b=Beat(user_id=current_user.id,name=name,bpm=row.get('bpm'),musical_key=row.get('musical_key'),status=row.get('status') or 'available')
            db.add(b); db.flush(); existing_beats[norm]=b; imported['beats']+=1
        beat_map[str(row.get('id'))]=b.id
    db.flush()
    # License merge uses artist/beat names, preventing ID collisions between databases.
    existing_keys=set()
    for x in db.scalars(select(License).where(License.user_id==current_user.id)).all():
        existing_keys.add((x.artist_id,x.beat_id,x.license_type,str(x.price),x.currency,x.status))
    for row in payload.get('licenses') or []:
        artist_name=str(row.get('artist_name') or '').casefold(); beat_name=str(row.get('beat_name') or '').casefold()
        a=existing_artists.get(artist_name); b=existing_beats.get(beat_name) if beat_name else None
        if not a:
            imported['licenses_skipped']+=1; continue
        keyv=(a.id,b.id if b else None,str(row.get('type') or 'mp3'),str(row.get('price') or '0'),str(row.get('currency') or current_user.currency),str(row.get('status') or 'paid'))
        if keyv in existing_keys: imported['licenses_skipped']+=1; continue
        try: price=Decimal(str(row.get('price') or '0'))
        except Exception: imported['licenses_skipped']+=1; continue
        lic=License(user_id=current_user.id,artist_id=a.id,beat_id=(b.id if b else None),license_type=str(row.get('type') or 'mp3'),price=price,currency=str(row.get('currency') or current_user.currency),status=str(row.get('status') or 'paid'),notes=row.get('notes'))
        db.add(lic); existing_keys.add(keyv); imported['licenses']+=1
    db.commit()
    return {'status':'merged','imported':imported,'policy':'Existing records were preserved; matching records were skipped.'}

@router.delete('/trash/{entity_type}/{entity_id}/permanent')
def permanent_delete(entity_type:str,entity_id:int,db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    if entity_type=='artist':
        link=db.scalar(select(UserArtist).where(UserArtist.user_id==current_user.id,UserArtist.artist_id==entity_id,UserArtist.status=='archived'))
        if not link: raise HTTPException(404,'Archived artist not found')
        sales=db.scalar(select(func.count(License.id)).where(License.artist_id==entity_id,License.user_id==current_user.id)) or 0
        if sales: raise HTTPException(409,'This artist has license history and cannot be permanently deleted. Restore or keep archived instead.')
        db.delete(link); db.commit(); return {'status':'permanently_deleted','entity_type':'artist','id':entity_id}
    if entity_type=='beat':
        row=db.scalar(select(Beat).where(Beat.id==entity_id,(Beat.user_id==current_user.id)|(Beat.messenger_id==current_user.id),Beat.status=='archived'))
        if not row: raise HTTPException(404,'Archived beat not found')
        sales=db.scalar(select(func.count(License.id)).where(License.beat_id==entity_id)) or 0
        sends=db.scalar(select(func.count(BeatSend.id)).where(BeatSend.beat_id==entity_id)) or 0
        if sales or sends: raise HTTPException(409,'This beat has history and cannot be permanently deleted. Restore or keep archived instead.')
        db.delete(row); db.commit(); return {'status':'permanently_deleted','entity_type':'beat','id':entity_id}
    raise HTTPException(400,'Unsupported trash entity')

@router.post('/clear-all')
def clear_all_account_data(db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    """Development/test reset for the currently authenticated account only."""
    from sqlalchemy import delete
    from app.models import Notification, LicenseSplit, LicenseEvent, License, BeatSend, BeatProducer, BeatCredit, Beat, UserArtist, Artist
    # Personal notifications and personal sale records.
    db.execute(delete(Notification).where(Notification.user_id==current_user.id))
    own_license_ids=list(db.scalars(select(License.id).where(License.user_id==current_user.id)).all())
    if own_license_ids:
        db.execute(delete(LicenseEvent).where(LicenseEvent.license_id.in_(own_license_ids)))
        db.execute(delete(LicenseSplit).where(LicenseSplit.license_id.in_(own_license_ids)))
        db.execute(delete(License).where(License.id.in_(own_license_ids)))
    # Remove this user's collaboration rows without deleting beats owned by others.
    db.execute(delete(BeatProducer).where(BeatProducer.user_id==current_user.id))
    own_beat_ids=list(db.scalars(select(Beat.id).where(Beat.user_id==current_user.id)).all())
    if own_beat_ids:
        db.execute(delete(BeatSend).where(BeatSend.beat_id.in_(own_beat_ids)))
        db.execute(delete(BeatCredit).where(BeatCredit.beat_id.in_(own_beat_ids)))
        db.execute(delete(BeatProducer).where(BeatProducer.beat_id.in_(own_beat_ids)))
        db.execute(delete(Beat).where(Beat.id.in_(own_beat_ids)))
    artist_ids=list(db.scalars(select(UserArtist.artist_id).where(UserArtist.user_id==current_user.id)).all())
    db.execute(delete(UserArtist).where(UserArtist.user_id==current_user.id))
    if artist_ids:
        # Delete orphan artists that are no longer attached to another account.
        for aid in artist_ids:
            still=db.scalar(select(UserArtist).where(UserArtist.artist_id==aid))
            if not still:
                db.execute(delete(Artist).where(Artist.id==aid))
    db.commit()
    return {'status':'ok'}
