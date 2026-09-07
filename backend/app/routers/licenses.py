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
from app.license_logic import calculate_splits
from app.routers.beats import resolve_user, canonical
router=APIRouter()
LICENSE_TYPES={"mp3":"MP3","wav":"WAV","trackout":"Trackout","exclusive":"Exclusive","custom":"Beat under commission"}
D=Decimal
def participant_rows(beat, db):
    rows = []
    seen_user_ids = set()
    seen_external_names = set()

    registered = list(
        db.scalars(
            select(BeatProducer)
            .where(BeatProducer.beat_id == beat.id)
            .order_by(BeatProducer.id)
        ).all()
    )

    for producer in registered:
        user = db.get(User, producer.user_id)

        if not user or user.id in seen_user_ids:
            continue

        rows.append({
            "user_id": user.id,
            "display_name": user.username,
            "share_percent": producer.share_percent,
        })

        seen_user_ids.add(user.id)

    credits = list(
        db.scalars(
            select(BeatCredit)
            .where(BeatCredit.beat_id == beat.id)
            .order_by(BeatCredit.id)
        ).all()
    )

    for credit in credits:
        if credit.user_id and credit.user_id in seen_user_ids:
            continue

        display_name = (
            credit.display_name or "External Producer"
        ).strip()

        if credit.user_id is None:
            key = display_name.lower()

            if key in seen_external_names:
                continue

            seen_external_names.add(key)

        rows.append({
            "user_id": credit.user_id,
            "display_name": display_name,
            "share_percent": credit.share_percent,
        })

        if credit.user_id:
            seen_user_ids.add(credit.user_id)

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
    producer_ids = {
        producer["user_id"]
        for producer in producers
        if producer["user_id"] is not None
    }
    seller_is_producer = current_user.id in producer_ids

    # Messenger is chosen for this sale only. It is deliberately not stored on
    # the beat, because the same beat may be sold by different people.
    messenger = None
    messenger_name = None
    messenger_id = None
    if beat and data.messenger_username:
        raw_messenger = str(data.messenger_username).strip()
        if raw_messenger:
            messenger_user = resolve_user(db, raw_messenger)
            messenger_id = messenger_user.id if messenger_user else None
            messenger_name = messenger_user.username if messenger_user else canonical(raw_messenger)
            messenger = {"user_id": messenger_id, "display_name": messenger_name}

    purchased=datetime.now(timezone.utc)
    row=License(
        user_id=current_user.id,
        artist_id=data.artist_id,
        beat_id=data.beat_id,
        messenger_id=messenger_id,
        messenger_name=messenger_name,
        license_type=data.license_type,
        price=data.price,
        currency=currency,
        status=data.status,
        mailing_share=D("0"),
        mailing_share_percent=D("0"),
        producer_share_percent=D("0"),
        is_producer=seller_is_producer,
        is_messenger=bool(messenger),
        notes=data.notes,
        purchased_at=purchased,
    )
    db.add(row); db.flush()
    db.add(LicenseEvent(license_id=row.id,event_type="created",new_status=row.status,note="License created"))
    # Immutable split snapshot for this sale. Only registered producer credits
    # participate in financial distribution. External BeatCredit rows remain display-only.
    split_inputs = producers

    if not split_inputs:
        db.rollback()

        raise HTTPException(
            400,
            "This beat has no producer credits"
        )
    calculated = calculate_splits(data.price, split_inputs, current_user.id, messenger=messenger)
    producer_splits = []
    for item in calculated:
        db.add(LicenseSplit(
            license_id=row.id,
            user_id=item["user_id"],
            display_name=item["display_name"],
            role=item["role"],
            percent=item["share_percent"],
            amount=item["amount"],
            currency=currency,
        ))
        if item["role"] == "producer":
            producer_splits.append((item["user_id"], item["display_name"], item["share_percent"], item["amount"]))

    messenger_split = next((item for item in calculated if item["role"] == "messenger"), None)
    messenger_amount = messenger_split["amount"] if messenger_split else Decimal("0.00")
    messenger_pct = messenger_split["share_percent"] if messenger_split else Decimal("0.00")
    producer_total_pct = sum((item["share_percent"] for item in calculated if item["role"] == "producer"), Decimal("0.00"))

    # Keep the summary fields synchronized with the immutable split snapshot.
    row.mailing_share = messenger_amount
    row.mailing_share_percent = messenger_pct
    row.producer_share_percent = producer_total_pct

    snap={"license_id":row.id,"artist_id":row.artist_id,"beat_id":row.beat_id,"license_type":row.license_type,"price":str(row.price),"currency":row.currency,"status":row.status,"mailing_share_percent":str(row.mailing_share_percent),"producer_share_percent":str(row.producer_share_percent),"messenger_id":row.messenger_id,"messenger_name":row.messenger_name,"is_producer":row.is_producer,"is_messenger":row.is_messenger,"notes":row.notes}
    db.add(LicenseVersion(license_id=row.id,version_no=1,snapshot_json=json.dumps(snap,ensure_ascii=False)))

    # Notify every registered producer about paid sales with their exact immutable split.
    if data.status == "paid":
        for uid,label,pct,amount in producer_splits:
            if not uid: continue
            if messenger_pct > 0:
                message=(f'License #{row.id} for beat "{beat.name}" was sold by messenger {current_user.username} for {data.price} {currency}.\n\n'
                         f'Messenger share - {messenger_pct}% - {messenger_amount} {currency}\n'
                         f'Your share - {pct}% - {amount} {currency}')
            else:
                message=(f'License #{row.id} for beat "{beat.name}" was sold by {current_user.username} for {data.price} {currency}.\n\n'
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
        # A pending sale already has its immutable split snapshot from creation.
        # Legacy/imported licenses without splits are intentionally not auto-reconstructed.
        if new_status == "paid":
            existing_splits = list(db.scalars(select(LicenseSplit).where(LicenseSplit.license_id == row.id)).all())
            if not existing_splits:
                raise HTTPException(409, "Cannot mark this license as paid because its split snapshot is missing. Create a new sale or restore the historical split manually.")

        row.status=new_status
        latest=db.scalar(select(LicenseVersion).where(LicenseVersion.license_id==row.id).order_by(LicenseVersion.version_no.desc()))
        version_no=(latest.version_no+1 if latest else 1)
        snap={"license_id":row.id,"artist_id":row.artist_id,"beat_id":row.beat_id,"license_type":row.license_type,"price":str(row.price),"currency":row.currency,"status":row.status,"mailing_share_percent":str(row.mailing_share_percent),"producer_share_percent":str(row.producer_share_percent),"is_producer":row.is_producer,"is_messenger":row.is_messenger,"notes":row.notes}
        db.add(LicenseVersion(license_id=row.id,version_no=version_no,snapshot_json=json.dumps(snap,ensure_ascii=False)))

        if new_status == "paid":
            # Idempotent notification: the license id is part of the message so a
            # repeated pending->paid request cannot spam collaborators.
            beat = db.get(Beat, row.beat_id) if row.beat_id else None
            if beat:
                split_rows = list(db.scalars(select(LicenseSplit).where(LicenseSplit.license_id == row.id, LicenseSplit.role == "producer")).all())
                messenger = db.scalar(select(LicenseSplit).where(LicenseSplit.license_id == row.id, LicenseSplit.role == "messenger"))
                for split in split_rows:
                    if not split.user_id:
                        continue
                    already = db.scalar(select(Notification.id).where(
                        Notification.user_id == split.user_id,
                        Notification.type == "license_sold",
                        Notification.message.like(f"License #{row.id} %"),
                    ))
                    if already:
                        continue
                    if messenger:
                        message=(f'License #{row.id} for beat "{beat.name}" was sold by messenger {current_user.username} for {row.price} {row.currency}.\n\n'
                                 f'Messenger share - {messenger.percent}% - {messenger.amount} {row.currency}\n'
                                 f'Your share - {split.percent}% - {split.amount} {row.currency}')
                    else:
                        message=(f'License #{row.id} for beat "{beat.name}" was sold by {current_user.username} for {row.price} {row.currency}.\n\n'
                                 f'Your share - {split.percent}% - {split.amount} {row.currency}')
                    db.add(Notification(user_id=split.user_id,type="license_sold",title="LICENSE SOLD",message=message,is_read=False))

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
