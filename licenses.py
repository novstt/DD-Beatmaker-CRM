from datetime import datetime,timezone
from decimal import Decimal,ROUND_DOWN
import json
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models import Artist,Beat,BeatCredit,BeatProducer,License,LicenseEvent,LicenseSplit,Notification,User,UserArtist
from app.workspace_models import LicenseVersion
from app.schemas import LicenseCreate,LicenseOut
router=APIRouter()
LICENSE_TYPES={"mp3":"MP3","wav":"WAV","trackout":"Trackout","exclusive":"Exclusive","custom":"Beat under commission"}
D=Decimal
def participant_rows(beat,db):
    # Only explicit BeatProducer / BeatCredit entries are producers.
    # The account that created the CRM record is NOT automatically entitled
    # to producer revenue. If that account sells the license without being
    # listed here, it is treated as the messenger at the license stage.
    rows=[]; seen=set()
    registered=list(db.scalars(select(BeatProducer).where(BeatProducer.beat_id==beat.id).order_by(BeatProducer.id)).all())
    for p in registered:
        u=db.get(User,p.user_id)
        if u and u.id not in seen:
            rows.append((u.id,u.username)); seen.add(u.id)
    for c in db.scalars(select(BeatCredit).where(BeatCredit.beat_id==beat.id).order_by(BeatCredit.id)).all():
        if c.user_id and c.user_id in seen:
            continue
        rows.append((c.user_id,c.display_name))
        if c.user_id:
            seen.add(c.user_id)
    return rows
def split_percent(n,i):
    if n<=0:return D("0")
    if i<n-1: return (D("100")/D(n)).quantize(D("0.01"),rounding=ROUND_DOWN)
    return D("100")-sum((split_percent(n,j) for j in range(n-1)),D("0"))
def _accessible_license_stmt(user_id:int):
    return select(License).where(
        (License.user_id==user_id) |
        (License.id.in_(select(LicenseSplit.license_id).where(LicenseSplit.user_id==user_id)))
    )

@router.get("",response_model=list[LicenseOut])
def list_licenses(db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    return list(db.scalars(_accessible_license_stmt(current_user.id).order_by(License.purchased_at.desc())).all())
@router.post("",response_model=LicenseOut,status_code=201)
def create_license(data:LicenseCreate,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    if data.license_type not in LICENSE_TYPES: raise HTTPException(422,"Invalid license type")
    if data.status not in {"paid","pending","refunded","void"}: raise HTTPException(422,"Invalid payment status")
    currency=str(data.currency or "USD").upper()
    if currency not in {"USD","EUR","CHF"}: raise HTTPException(422,"Unsupported currency")
    if data.price<=0: raise HTTPException(422,"License price must be greater than 0")
    artist=db.get(Artist,data.artist_id)
    if not artist or not db.scalar(select(UserArtist).where(UserArtist.user_id==current_user.id,UserArtist.artist_id==data.artist_id)): raise HTTPException(400,"Artist is not in your list")
    beat=db.get(Beat,data.beat_id) if data.beat_id else None
    if data.beat_id and not beat: raise HTTPException(404,"Beat not found")
    # Any registered producer may record a sale for a beat. Sending history belongs to the
    # seller, but must not block another co-producer from recording the same shared beat.
    producers=participant_rows(beat,db) if beat else []
    producer_ids={p[0] for p in producers if p[0]}
    seller_is_producer=current_user.id in producer_ids
    messenger_pct=D("0") if seller_is_producer or not beat else D("10")
    remaining=D("100")-messenger_pct
    purchased=datetime.now(timezone.utc)
    row=License(user_id=current_user.id,artist_id=data.artist_id,beat_id=data.beat_id,license_type=data.license_type,price=data.price,currency=currency,status=data.status,mailing_share=(data.price*messenger_pct/D("100")).quantize(D("0.01")),mailing_share_percent=messenger_pct,producer_share_percent=(D("100") if len(producers)==1 else D("0")),is_producer=seller_is_producer,is_messenger=(bool(beat) and not seller_is_producer),notes=data.notes,purchased_at=purchased)
    db.add(row); db.flush()
    snap={"license_id":row.id,"artist_id":row.artist_id,"beat_id":row.beat_id,"license_type":row.license_type,"price":str(row.price),"currency":row.currency,"status":row.status,"mailing_share_percent":str(row.mailing_share_percent),"producer_share_percent":str(row.producer_share_percent),"is_producer":row.is_producer,"is_messenger":row.is_messenger,"notes":row.notes}
    db.add(LicenseVersion(license_id=row.id,version_no=1,snapshot_json=json.dumps(snap,ensure_ascii=False)))
    db.add(LicenseEvent(license_id=row.id,event_type="created",new_status=row.status,note="License created"))
    # Immutable split snapshot for this sale. Percentages are always relative to the full sale price.
    producer_splits=[]
    producer_total=(data.price*remaining/D("100")).quantize(D("0.01"))
    allocated=D("0")
    for idx,(uid,label) in enumerate(producers):
        pct=(remaining*split_percent(len(producers),idx)/D("100")).quantize(D("0.01"))
        amount=((data.price*pct/D("100")).quantize(D("0.01")) if idx < len(producers)-1 else (producer_total-allocated).quantize(D("0.01")))
        allocated += amount
        producer_splits.append((uid,label,pct,amount))
        db.add(LicenseSplit(license_id=row.id,user_id=uid,display_name=label,role="producer",percent=pct,amount=amount,currency=currency))
    messenger_amount=row.mailing_share
    if messenger_pct > 0:
        db.add(LicenseSplit(license_id=row.id,user_id=current_user.id,display_name=current_user.username,role="messenger",percent=messenger_pct,amount=messenger_amount,currency=currency))
    # Notify every registered producer about paid sales with their exact immutable split.
    if data.status == "paid":
        for uid,label,pct,amount in producer_splits:
            if not uid: continue
            if messenger_pct > 0:
                message=(f'License for beat "{beat.name}" was sold by messenger {current_user.username} for {data.price} {currency}.\n\n'
                         f'Messenger share - {messenger_pct}% - {messenger_amount} {currency}\n'
                         f'Your share - {pct}% - {amount} {currency}')
            else:
                message=(f'License for beat "{beat.name}" was sold by {current_user.username} for {data.price} {currency}.\n\n'
                         f'Your share - {pct}% - {amount} {currency}')
            db.add(Notification(user_id=uid,type="license_sold",title="LICENSE SOLD",message=message,is_read=False))
    db.commit(); db.refresh(row); return row


@router.get("/{license_id}/history")
def license_history(license_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    row=db.scalar(_accessible_license_stmt(current_user.id).where(License.id==license_id))
    if not row: raise HTTPException(404,"License not found")
    events=list(db.scalars(select(LicenseEvent).where(LicenseEvent.license_id==license_id).order_by(LicenseEvent.created_at.asc(),LicenseEvent.id.asc())).all())
    return [{"id":e.id,"event_type":e.event_type,"old_status":e.old_status,"new_status":e.new_status,"note":e.note,"created_at":e.created_at.isoformat() if e.created_at else None} for e in events]

@router.put("/{license_id}/status",response_model=LicenseOut)
def update_license_status(license_id:int,new_status:str,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    if new_status not in {"paid","pending","refunded","void"}: raise HTTPException(422,"Invalid payment status")
    row=db.scalar(_accessible_license_stmt(current_user.id).where(License.id==license_id))
    if not row: raise HTTPException(404,"License not found")
    old=row.status
    if old!=new_status:
        row.status=new_status
        latest=db.scalar(select(LicenseVersion).where(LicenseVersion.license_id==row.id).order_by(LicenseVersion.version_no.desc()))
        version_no=(latest.version_no+1 if latest else 1)
        snap={"license_id":row.id,"artist_id":row.artist_id,"beat_id":row.beat_id,"license_type":row.license_type,"price":str(row.price),"currency":row.currency,"status":row.status,"mailing_share_percent":str(row.mailing_share_percent),"producer_share_percent":str(row.producer_share_percent),"is_producer":row.is_producer,"is_messenger":row.is_messenger,"notes":row.notes}
        db.add(LicenseVersion(license_id=row.id,version_no=version_no,snapshot_json=json.dumps(snap,ensure_ascii=False)))
        db.add(LicenseEvent(license_id=row.id,event_type="status_changed",old_status=old,new_status=new_status,note=f"Payment status changed from {old} to {new_status}"))
        db.commit(); db.refresh(row)
    return row



@router.get('/{license_id}/splits')
def license_splits(license_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    row=db.scalar(_accessible_license_stmt(current_user.id).where(License.id==license_id))
    if not row: raise HTTPException(404,'License not found')
    rows=list(db.scalars(select(LicenseSplit).where(LicenseSplit.license_id==license_id).order_by(LicenseSplit.id.asc())).all())
    return [{'id':x.id,'user_id':x.user_id,'display_name':x.display_name,'role':x.role,'percent':str(x.percent),'amount':str(x.amount),'currency':x.currency} for x in rows]

@router.get('/{license_id}/versions')
def license_versions(license_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    row=db.scalar(_accessible_license_stmt(current_user.id).where(License.id==license_id))
    if not row: raise HTTPException(404,'License not found')
    versions=list(db.scalars(select(LicenseVersion).where(LicenseVersion.license_id==license_id).order_by(LicenseVersion.version_no.desc())).all())
    return [{'id':v.id,'version_no':v.version_no,'snapshot':json.loads(v.snapshot_json),'created_at':v.created_at.isoformat() if v.created_at else None} for v in versions]
