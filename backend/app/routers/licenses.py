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


@router.get("/messenger-check")
def messenger_check(username: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Resolve a registered Messenger account before a sale is created."""
    raw = (username or "").strip()
    if not raw:
        raise HTTPException(422, "Messenger username is required")
    user = resolve_user(db, raw)
    if not user:
        return {"found": False, "username": raw, "user_id": None}
    return {"found": True, "username": user.username, "user_id": user.id}

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
    if data.messenger_username:
        raw_messenger = str(data.messenger_username).strip()
        if not beat:
            raise HTTPException(422, "Messenger can only be selected for a license linked to a beat")
        if raw_messenger:
            messenger_user = resolve_user(db, raw_messenger)
            if not messenger_user:
                raise HTTPException(422, f'Messenger account "{raw_messenger}" was not found. The license was not created.')
            messenger_id = messenger_user.id
            messenger_name = messenger_user.username
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
    # Immutable split snapshot for this sale. Registered and external producer credits
    # both participate in financial distribution; the snapshot is the source of truth.
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

    # Financial invariant: the immutable snapshot must always balance exactly.
    total_percent = sum((item['share_percent'] for item in calculated), Decimal('0.00'))
    total_amount = sum((item['amount'] for item in calculated), Decimal('0.00'))
    if total_percent != Decimal('100.00') or total_amount != Decimal(str(data.price)):
        db.rollback()
        raise HTTPException(500, 'Financial split invariant failed; sale was not saved')

    # Paid-sale notifications are generated from the immutable split snapshot.
    if data.status == "paid":
        for uid, label, pct, amount in producer_splits:
            if not uid:
                continue
            message = (
                f'License #{row.id} for beat "{beat.name}" was recorded by {current_user.username}.\n\n'
                + (
                    f'Messenger: {messenger_name} — {messenger_pct}% — {messenger_amount} {currency}\n'
                    if messenger_split else ""
                )
                + f'Your producer share: {pct}% — {amount} {currency}'
            )
            db.add(Notification(
                user_id=uid, type="license_sold", title="LICENSE SOLD",
                message=message, is_read=False,
            ))

        # Messenger gets its own notification. This is intentionally outside
        # the producer loop so it is sent exactly once.
        if messenger_split and messenger_split["user_id"]:
            db.add(Notification(
                user_id=messenger_split["user_id"],
                type="license_sold_messenger",
                title="LICENSE SOLD — MESSENGER SHARE",
                message=(
                    f'License #{row.id} for beat "{beat.name}" was sold for {data.price} {currency}.\n\n'
                    f'Your messenger share: {messenger_pct}% — {messenger_amount} {currency}'
                ),
                is_read=False,
            ))

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
            # Idempotent notifications are reconstructed only from the immutable
            # LicenseSplit snapshot. No split is recalculated here.
            beat = db.get(Beat, row.beat_id) if row.beat_id else None
            if beat:
                split_rows = list(db.scalars(select(LicenseSplit).where(
                    LicenseSplit.license_id == row.id,
                    LicenseSplit.role == "producer",
                )).all())
                messenger = db.scalar(select(LicenseSplit).where(
                    LicenseSplit.license_id == row.id,
                    LicenseSplit.role == "messenger",
                ))

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
                    message = (
                        f'License #{row.id} for beat "{beat.name}" was recorded by {current_user.username}.\n\n'
                        + (
                            f'Messenger: {messenger.display_name} — {messenger.percent}% — {messenger.amount} {row.currency}\n'
                            if messenger else ""
                        )
                        + f'Your producer share: {split.percent}% — {split.amount} {row.currency}'
                    )
                    db.add(Notification(
                        user_id=split.user_id, type="license_sold",
                        title="LICENSE SOLD", message=message, is_read=False,
                    ))

                if messenger and messenger.user_id:
                    already_messenger = db.scalar(select(Notification.id).where(
                        Notification.user_id == messenger.user_id,
                        Notification.type == "license_sold_messenger",
                        Notification.message.like(f"License #{row.id} %"),
                    ))
                    if not already_messenger:
                        db.add(Notification(
                            user_id=messenger.user_id,
                            type="license_sold_messenger",
                            title="LICENSE SOLD — MESSENGER SHARE",
                            message=(
                                f'License #{row.id} for beat "{beat.name}" was sold for {row.price} {row.currency}.\n\n'
                                f'Your messenger share: {messenger.percent}% — {messenger.amount} {row.currency}'
                            ),
                            is_read=False,
                        ))

        db.add(LicenseEvent(license_id=row.id,event_type="status_changed",old_status=old,new_status=new_status,note=f"Payment status changed from {old} to {new_status}"))
        db.commit(); db.refresh(row)
    return row



@router.get('/{license_id}/splits')
def license_splits(license_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    row=db.scalar(_accessible_license_stmt(current_user.id).where(License.id==license_id))
    if not row: raise HTTPException(404,'License not found')
    rows=list(db.scalars(select(LicenseSplit).where(LicenseSplit.license_id==license_id).order_by(LicenseSplit.id.asc())).all())
    return [{'id':x.id,'user_id':x.user_id,'display_name':x.display_name,'role':x.role,'percent':str(x.percent),'amount':str(x.amount),'currency':x.currency} for x in rows]

@router.get('/{license_id}/financial-summary')
def license_financial_summary(license_id:int, db:Session=Depends(get_db), current_user:User=Depends(get_current_user)):
    """Return gross sale and the immutable amount actually earned by this account.

    License.price is gross revenue and must never be treated as the caller's income.
    LicenseSplit is the only source of personal earnings.
    """
    row=db.scalar(_accessible_license_stmt(current_user.id).where(License.id==license_id))
    if not row:
        raise HTTPException(404, 'License not found')
    rows=list(db.scalars(select(LicenseSplit).where(LicenseSplit.license_id==license_id).order_by(LicenseSplit.id.asc())).all())
    personal=sum((Decimal(str(x.amount)) for x in rows if x.user_id==current_user.id), Decimal('0.00'))
    total_amount=sum((Decimal(str(x.amount)) for x in rows), Decimal('0.00'))
    total_percent=sum((Decimal(str(x.percent)) for x in rows), Decimal('0.00'))
    return {
        'license_id': row.id,
        'gross_price': str(row.price),
        'currency': row.currency,
        'status': row.status,
        'personal_earnings': str(personal),
        'personal_percent': str(sum((Decimal(str(x.percent)) for x in rows if x.user_id==current_user.id), Decimal('0.00'))),
        'total_split_amount': str(total_amount),
        'total_split_percent': str(total_percent),
        'balanced': total_amount == Decimal(str(row.price)) and total_percent == Decimal('100.00'),
        'splits': [
            {'id':x.id,'user_id':x.user_id,'display_name':x.display_name,'role':x.role,'percent':str(x.percent),'amount':str(x.amount),'currency':x.currency}
            for x in rows
        ],
    }

@router.get('/{license_id}/versions')
def license_versions(license_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    row=db.scalar(_accessible_license_stmt(current_user.id).where(License.id==license_id))
    if not row: raise HTTPException(404,'License not found')
    versions=list(db.scalars(select(LicenseVersion).where(LicenseVersion.license_id==license_id).order_by(LicenseVersion.version_no.desc())).all())
    return [{'id':v.id,'version_no':v.version_no,'snapshot':json.loads(v.snapshot_json),'created_at':v.created_at.isoformat() if v.created_at else None} for v in versions]
