from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Artist, Beat, BeatSend, License, User, UserArtist
from app.schemas import (
    ArtistCreate,
    ArtistOut,
    ArtistAddContact,
    ArtistContactOut,
)

router = APIRouter()


@router.get("/mine", response_model=list[ArtistOut])
def my_artists(
    search: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Artist)
        .join(UserArtist, UserArtist.artist_id == Artist.id)
        .where(UserArtist.user_id == current_user.id, UserArtist.status != 'archived')
    )

    if search.strip():
        term = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Artist.name.ilike(term),
                Artist.normalized_name.ilike(term),
            )
        )

    artists = db.scalars(stmt.order_by(Artist.name.asc()).offset(offset).limit(limit)).unique().all()
    result=[]
    for artist in artists:
        contact=db.scalar(select(UserArtist).where(UserArtist.user_id==current_user.id,UserArtist.artist_id==artist.id))
        from sqlalchemy import func
        beats_count=db.scalar(select(func.count(BeatSend.id)).where(BeatSend.user_id==current_user.id,BeatSend.artist_id==artist.id)) or 0
        licenses_count=db.scalar(select(func.count(License.id)).where(License.user_id==current_user.id,License.artist_id==artist.id)) or 0
        result.append({"id":artist.id,"name":artist.name,"normalized_name":artist.normalized_name,"platform":contact.platform if contact else None,"artist_username":contact.artist_username if contact else None,"message_status":contact.message_status if contact else None,"cash_ready":contact.cash_ready if contact else False,"beats_sent_count":beats_count,"licenses_count":licenses_count})
    return result


@router.get("/global", response_model=list[ArtistOut])
def global_artists(
    search: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Artist)

    if search.strip():
        term = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Artist.name.ilike(term),
                Artist.normalized_name.ilike(term),
            )
        )

    return db.scalars(
        stmt.order_by(Artist.name.asc()).offset(offset).limit(limit)
    ).all()


@router.delete("/{artist_id}")
def delete_artist(
    artist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artist = db.get(Artist, artist_id)
    if artist is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    contact = db.scalar(select(UserArtist).where(
        UserArtist.user_id == current_user.id,
        UserArtist.artist_id == artist_id,
    ))
    if contact is None:
        raise HTTPException(status_code=404, detail="Artist is not in your list")
    contact.status = 'archived'
    db.commit()
    return {"status":"archived", "artist_id":artist_id}


@router.get("/{artist_id}/details")
def get_artist_details(
    artist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artist = db.get(Artist, artist_id)

    if artist is None:
        raise HTTPException(
            status_code=404,
            detail="Artist not found",
        )

    contact = db.scalar(
        select(UserArtist).where(
            UserArtist.user_id == current_user.id,
            UserArtist.artist_id == artist_id,
        )
    )

    sends = []

    rows = db.execute(
        select(BeatSend, Beat)
        .join(Beat, Beat.id == BeatSend.beat_id)
        .where(
            BeatSend.user_id == current_user.id,
            BeatSend.artist_id == artist_id,
        )
        .order_by(BeatSend.sent_at.desc())
    ).all()

    for send, beat in rows:
        sends.append(
            {
                "id": beat.id,
                "name": beat.name,
                "price": str(beat.price),
                "sent_at": (
                    send.sent_at.isoformat()
                    if send.sent_at
                    else None
                ),
                "status": send.status or "sent",
            }
        )

    return {
        "id": artist.id,
        "name": artist.name,
        "artist_username": (
            contact.artist_username if contact else None
        ),
        "platform": contact.platform if contact else None,
        "message_status": (
            contact.message_status if contact else None
        ),
        "cash_ready": (
            contact.cash_ready if contact else False
        ),
        "notes": contact.notes if contact else None,
        "beats": sends,
    }


@router.post("", response_model=ArtistOut)
def create_artist(
    payload: ArtistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized = payload.name.strip().lower()

    if not normalized:
        raise HTTPException(
            status_code=422,
            detail="Artist name cannot be empty",
        )

    artist = db.scalar(
        select(Artist).where(
            Artist.normalized_name == normalized
        )
    )

    if artist is None:
        artist = Artist(
            name=payload.name.strip(),
            normalized_name=normalized,
            created_by=current_user.id,
        )
        db.add(artist)
        db.flush()

    existing = db.scalar(
        select(UserArtist).where(
            UserArtist.user_id == current_user.id,
            UserArtist.artist_id == artist.id,
        )
    )

    if existing is None:
        db.add(
            UserArtist(
                user_id=current_user.id,
                artist_id=artist.id,
                platform=payload.platform,
                artist_username=payload.artist_username,
                message_status=payload.message_status,
                cash_ready=payload.cash_ready,
                notes=payload.notes,
            )
        )
    else:
        existing.platform = payload.platform
        existing.artist_username = payload.artist_username
        existing.message_status = payload.message_status
        existing.cash_ready = payload.cash_ready
        existing.notes = payload.notes
        existing.status = "new"

    db.commit()
    db.refresh(artist)

    contact = db.scalar(select(UserArtist).where(UserArtist.user_id == current_user.id, UserArtist.artist_id == artist.id))
    from sqlalchemy import func
    beats_count = db.scalar(select(func.count(BeatSend.id)).where(BeatSend.user_id == current_user.id, BeatSend.artist_id == artist.id)) or 0
    licenses_count = db.scalar(select(func.count(License.id)).where(License.user_id == current_user.id, License.artist_id == artist.id)) or 0
    return {
        "id": artist.id,
        "name": artist.name,
        "normalized_name": artist.normalized_name,
        "platform": contact.platform if contact else None,
        "artist_username": contact.artist_username if contact else None,
        "message_status": contact.message_status if contact else None,
        "cash_ready": contact.cash_ready if contact else False,
        "beats_sent_count": beats_count,
        "licenses_count": licenses_count,
    }


@router.put(
    "/{artist_id}/contact",
    response_model=ArtistContactOut,
)
def update_artist_contact(
    artist_id: int,
    payload: ArtistAddContact,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artist = db.get(Artist, artist_id)

    if artist is None:
        raise HTTPException(
            status_code=404,
            detail="Artist not found",
        )

    contact = db.scalar(
        select(UserArtist).where(
            UserArtist.user_id == current_user.id,
            UserArtist.artist_id == artist_id,
        )
    )

    if contact is None:
        raise HTTPException(
            status_code=404,
            detail="Artist contact not found",
        )

    contact.platform = payload.platform
    contact.artist_username = payload.artist_username
    contact.message_status = payload.message_status
    contact.cash_ready = payload.cash_ready
    contact.notes = payload.notes

    db.commit()
    db.refresh(contact)

    return contact


@router.post(
    "/{artist_id}/contact",
    response_model=ArtistContactOut,
)
def add_artist_contact(
    artist_id: int,
    payload: ArtistAddContact,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artist = db.get(Artist, artist_id)

    if artist is None:
        raise HTTPException(
            status_code=404,
            detail="Artist not found",
        )

    contact = db.scalar(
        select(UserArtist).where(
            UserArtist.user_id == current_user.id,
            UserArtist.artist_id == artist_id,
        )
    )

    if contact is None:
        contact = UserArtist(
            user_id=current_user.id,
            artist_id=artist_id,
            platform=payload.platform,
            artist_username=payload.artist_username,
            message_status=payload.message_status,
            cash_ready=payload.cash_ready,
            notes=payload.notes,
        )
        db.add(contact)
        db.flush()
    else:
        contact.platform = payload.platform
        contact.artist_username = payload.artist_username
        contact.message_status = payload.message_status
        contact.cash_ready = payload.cash_ready
        contact.notes = payload.notes
        contact.status = "new"

    for beat_id in payload.beat_ids:
        beat = db.get(Beat, beat_id)

        if beat is None:
            continue

        existing_send = db.scalar(
            select(BeatSend).where(
                BeatSend.user_id == current_user.id,
                BeatSend.artist_id == artist_id,
                BeatSend.beat_id == beat_id,
            )
        )

        if existing_send is None:
            db.add(
                BeatSend(
                    user_id=current_user.id,
                    artist_id=artist_id,
                    beat_id=beat_id,
                    status="sent",
                )
            )

    db.commit()
    db.refresh(contact)

    return contact
