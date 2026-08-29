from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Artist, BeatSend, License, LicenseSplit, User, UserArtist

router = APIRouter()


def period_start(period: str):
    now = datetime.now(timezone.utc)

    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if period == "last_month":
        first_this = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if first_this.month == 1:
            return first_this.replace(
                year=first_this.year - 1, month=12
            )
        return first_this.replace(month=first_this.month - 1)

    if period == "year":
        return now.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )

    return None


def period_window(period: str):
    now = datetime.now(timezone.utc)
    if period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_end = start
        prev_start = (start.replace(year=start.year-1, month=12) if start.month == 1 else start.replace(month=start.month-1))
        return start, None, prev_start, prev_end
    if period == 'last_month':
        this_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = this_start.replace(year=this_start.year-1, month=12) if this_start.month == 1 else this_start.replace(month=this_start.month-1)
        prev_end = start
        prev_start = start.replace(year=start.year-1, month=12) if start.month == 1 else start.replace(month=start.month-1)
        return start, this_start, prev_start, prev_end
    if period == 'year':
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start = start.replace(year=start.year-1)
        return start, None, prev_start, start
    return None, None, None, None


@router.get("/dashboard")
def dashboard(
    period: str = Query(
        default="all",
        pattern="^(all|month|last_month|year)$",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start = period_start(period)

    # A user can earn from a sale they recorded OR from another user's sale.
    # The immutable LicenseSplit rows are therefore the single source of truth
    # for every account balance.
    own_license_stmt = select(License).where(License.user_id == current_user.id)
    split_license_stmt = (
        select(License)
        .join(LicenseSplit, LicenseSplit.license_id == License.id)
        .where(LicenseSplit.user_id == current_user.id)
    )
    if start is not None:
        own_license_stmt = own_license_stmt.where(License.purchased_at >= start)
        split_license_stmt = split_license_stmt.where(License.purchased_at >= start)

    own_licenses = list(db.scalars(own_license_stmt).all())
    earned_licenses = list(db.scalars(split_license_stmt).all())
    # Distinct union keeps a producer's own sale from being counted twice.
    by_id = {x.id: x for x in own_licenses}
    by_id.update({x.id: x for x in earned_licenses})
    licenses = list(by_id.values())
    paid_licenses = [x for x in licenses if x.status == "paid"]
    pending_licenses = [x for x in licenses if x.status == "pending"]
    refunded_licenses = [x for x in licenses if x.status == "refunded"]

    send_stmt = select(BeatSend).where(BeatSend.user_id == current_user.id)
    if start is not None:
        send_stmt = send_stmt.where(BeatSend.sent_at >= start)
    sends = list(db.scalars(send_stmt).all())

    paid_split_stmt = (
        select(LicenseSplit, License)
        .join(License, License.id == LicenseSplit.license_id)
        .where(LicenseSplit.user_id == current_user.id, License.status == "paid")
    )
    pending_split_stmt = (
        select(LicenseSplit, License)
        .join(License, License.id == LicenseSplit.license_id)
        .where(LicenseSplit.user_id == current_user.id, License.status == "pending")
    )
    if start is not None:
        paid_split_stmt = paid_split_stmt.where(License.purchased_at >= start)
        pending_split_stmt = pending_split_stmt.where(License.purchased_at >= start)

    paid_split_rows = list(db.execute(paid_split_stmt).all())
    pending_split_rows = list(db.execute(pending_split_stmt).all())
    revenue_by_currency = {}
    expected_by_currency = {}
    for split, sale in paid_split_rows:
        currency = sale.currency
        revenue_by_currency[currency] = revenue_by_currency.get(currency, Decimal("0")) + Decimal(str(split.amount))
    for split, sale in pending_split_rows:
        currency = sale.currency
        expected_by_currency[currency] = expected_by_currency.get(currency, Decimal("0")) + Decimal(str(split.amount))

    display_currency = (current_user.currency or "USD").upper()
    revenue = revenue_by_currency.get(display_currency, Decimal("0"))
    expected_revenue = expected_by_currency.get(display_currency, Decimal("0"))
    mailing = sum((Decimal(str(split.amount)) for split, _ in paid_split_rows if split.role == "messenger"), Decimal("0"))
    producer_earnings = sum((Decimal(str(split.amount)) for split, _ in paid_split_rows if split.role == "producer"), Decimal("0"))
    my_role_earnings = sum((Decimal(str(split.amount)) for split, _ in paid_split_rows), Decimal("0"))

    artists_stmt = select(func.count(func.distinct(UserArtist.artist_id))).where(
        UserArtist.user_id == current_user.id
    )
    artists_count = db.scalar(artists_stmt) or 0

    by_type = {}
    revenue_by_format = {}
    for sale in paid_licenses:
        by_type[sale.license_type] = by_type.get(sale.license_type, 0) + 1
        revenue_by_format[sale.license_type] = revenue_by_format.get(sale.license_type, Decimal("0")) + Decimal(str(sale.price))

    recent = sorted(
        paid_licenses,
        key=lambda x: x.purchased_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:10]

    # Same split rows are used for the personal balance. Do not add messenger
    # earnings twice: they are already part of the immutable split total.
    my_earnings = sum((Decimal(str(split.amount)) for split, _ in paid_split_rows), Decimal('0'))
    messenger_earnings = sum((Decimal(str(split.amount)) for split, _ in paid_split_rows if split.role == 'messenger'), Decimal('0'))
    other_producer_earnings = sum((Decimal(str(split.amount)) for split, _ in paid_split_rows if split.role == 'producer'), Decimal('0'))

    recent_sales = [
        {
            "id": x.id,
            "artist_id": x.artist_id,
            "beat_id": x.beat_id,
            "license_type": x.license_type,
            "price": str(x.price),
            "currency": x.currency,
            "status": x.status,
            "is_producer": x.is_producer,
            "is_messenger": x.is_messenger,
            "producer_share_percent": str(x.producer_share_percent),
            "mailing_share_percent": str(x.mailing_share_percent),
            "purchased_at": (
                x.purchased_at.isoformat()
                if x.purchased_at else None
            ),
        }
        for x in recent
    ]

    # Analytics extras: contacted-to-buyer conversion and revenue delta vs the prior period.
    contacted_artists = db.scalar(select(func.count(func.distinct(UserArtist.artist_id))).where(UserArtist.user_id==current_user.id)) or 0
    buyer_stmt = select(func.count(func.distinct(License.artist_id))).where(License.user_id==current_user.id, License.status=='paid')
    if start is not None:
        buyer_stmt = buyer_stmt.where(License.purchased_at >= start)
    buyers_count = db.scalar(buyer_stmt) or 0
    conversion_rate = (Decimal(str(buyers_count))*Decimal('100')/Decimal(str(contacted_artists))) if contacted_artists else Decimal('0')

    _, _, prev_start, prev_end = period_window(period)
    revenue_change_percent = None
    if prev_start is not None:
        prev_stmt = select(License).where(License.user_id==current_user.id, License.status=='paid', License.purchased_at>=prev_start)
        if prev_end is not None:
            prev_stmt = prev_stmt.where(License.purchased_at < prev_end)
        prev_sales = list(db.scalars(prev_stmt).all())
        prev_revenue = sum((Decimal(str(x.price)) for x in prev_sales), Decimal('0'))
        if prev_revenue != 0:
            revenue_change_percent = ((revenue - prev_revenue) / prev_revenue * Decimal('100')).quantize(Decimal('0.01'))
        elif revenue > 0:
            revenue_change_percent = Decimal('100')
        else:
            revenue_change_percent = Decimal('0')

    top_artist_stmt = select(License.artist_id, func.count(License.id), func.sum(License.price)).where(License.user_id==current_user.id, License.status=='paid')
    if start is not None:
        top_artist_stmt = top_artist_stmt.where(License.purchased_at>=start)
    top_artist_rows = db.execute(top_artist_stmt.group_by(License.artist_id).order_by(func.sum(License.price).desc()).limit(5)).all()
    top_artists=[]
    for artist_id, sale_count, artist_revenue in top_artist_rows:
        artist=db.get(Artist, artist_id)
        top_artists.append({'artist_id':artist_id,'name':artist.name if artist else f'Artist #{artist_id}','sales':int(sale_count or 0),'revenue':str(artist_revenue or 0)})

    return {
        "period": period,
        "display_currency": display_currency,
        "revenue": str(revenue),
        "licenses_sold": len(paid_licenses),
        "pending_licenses": len(pending_licenses),
        "refunded_licenses": len(refunded_licenses),
        "expected_revenue": str(expected_revenue),
        "revenue_by_currency": {c: str(v) for c,v in revenue_by_currency.items()},
        "expected_revenue_by_currency": {c: str(v) for c,v in expected_by_currency.items()},
        "producer_earnings": str(producer_earnings),
        "mailing_earnings": str(mailing),
        "my_role_earnings": str(my_role_earnings),
        "my_earnings": str(my_earnings),
        "other_producer_earnings": str(other_producer_earnings),
        "messenger_earnings": str(messenger_earnings),
        "artists": artists_count,
        "beats_sent": len(sends),
        "license_types": by_type,
        "revenue_by_format": {k:str(v) for k,v in revenue_by_format.items()},
        "recent_sales": recent_sales,
        "contacted_artists": contacted_artists,
        "buyers": buyers_count,
        "conversion_rate": str(conversion_rate.quantize(Decimal('0.01'))),
        "revenue_change_percent": (str(revenue_change_percent) if revenue_change_percent is not None else None),
        "top_artists": top_artists,
    }
