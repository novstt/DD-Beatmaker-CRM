from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    theme: Mapped[str] = mapped_column(String(10), default="dark", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    artist_links = relationship(
        "UserArtist", back_populates="user", cascade="all, delete-orphan"
    )
    beats = relationship(
        "Beat",
        back_populates="user",
        foreign_keys="Beat.user_id",
        cascade="all, delete-orphan",
    )
    licenses = relationship(
        "License", back_populates="user", cascade="all, delete-orphan"
    )
    beat_producer_links = relationship(
        "BeatProducer", back_populates="user", cascade="all, delete-orphan"
    )
    beat_sends = relationship(
        "BeatSend", back_populates="user", cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    normalized_name: Mapped[str] = mapped_column(String(150), index=True)

    instagram: Mapped[str | None] = mapped_column(String(255))
    tiktok: Mapped[str | None] = mapped_column(String(255))
    soundcloud: Mapped[str | None] = mapped_column(String(255))

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    user_links = relationship(
        "UserArtist", back_populates="artist", cascade="all, delete-orphan"
    )
    beat_sends = relationship(
        "BeatSend", back_populates="artist", cascade="all, delete-orphan"
    )
    licenses = relationship("License", back_populates="artist")


class UserArtist(Base):
    __tablename__ = "user_artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE")
    )

    status: Mapped[str] = mapped_column(String(40), default="new")
    platform: Mapped[str | None] = mapped_column(String(40))
    artist_username: Mapped[str | None] = mapped_column(String(255))
    message_status: Mapped[str] = mapped_column(
        String(40), default="unread"
    )
    cash_ready: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    user = relationship("User", back_populates="artist_links")
    artist = relationship("Artist", back_populates="user_links")

    beat_sends = relationship(
        "BeatSend",
        back_populates="artist_contact",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "artist_id", name="uq_user_artist"),
    )


class Beat(Base):
    __tablename__ = "beats"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    # User who sent/mails the beat when it belongs to another producer.
    messenger_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(150), index=True)
    bpm: Mapped[int | None] = mapped_column(Integer)
    musical_key: Mapped[str | None] = mapped_column(String(30))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="available")
    google_drive_link: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    user = relationship(
        "User",
        back_populates="beats",
        foreign_keys=[user_id],
    )
    messenger = relationship(
        "User",
        foreign_keys=[messenger_id],
    )
    producers = relationship(
        "BeatProducer", back_populates="beat", cascade="all, delete-orphan"
    )
    credits = relationship(
        "BeatCredit", back_populates="beat", cascade="all, delete-orphan"
    )
    sends = relationship(
        "BeatSend", back_populates="beat", cascade="all, delete-orphan"
    )
    licenses = relationship("License", back_populates="beat")


class BeatProducer(Base):
    __tablename__ = "beat_producers"

    id: Mapped[int] = mapped_column(primary_key=True)
    beat_id: Mapped[int] = mapped_column(
        ForeignKey("beats.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    share_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=50
    )

    beat = relationship("Beat", back_populates="producers")
    user = relationship("User", back_populates="beat_producer_links")

    __table_args__ = (
        UniqueConstraint("beat_id", "user_id", name="uq_beat_producer"),
    )


class BeatCredit(Base):
    __tablename__ = "beat_credits"

    id: Mapped[int] = mapped_column(primary_key=True)
    beat_id: Mapped[int] = mapped_column(ForeignKey("beats.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(150))
    handle: Mapped[str | None] = mapped_column(String(150), nullable=True)
    share_percent: Mapped[Decimal] = mapped_column(Numeric(5,2), default=0)

    beat = relationship("Beat", back_populates="credits")
    user = relationship("User")

class BeatSend(Base):
    __tablename__ = "beat_sends"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE")
    )
    artist_contact_id: Mapped[int] = mapped_column(
        ForeignKey("user_artists.id", ondelete="CASCADE")
    )
    beat_id: Mapped[int] = mapped_column(
        ForeignKey("beats.id", ondelete="CASCADE")
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    status: Mapped[str] = mapped_column(String(30), default="sent")
    notes: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="beat_sends")
    artist = relationship("Artist", back_populates="beat_sends")
    artist_contact = relationship(
        "UserArtist", back_populates="beat_sends"
    )
    beat = relationship("Beat", back_populates="sends")


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE")
    )
    beat_id: Mapped[int | None] = mapped_column(
        ForeignKey("beats.id", ondelete="SET NULL"),
        nullable=True,
    )

    license_type: Mapped[str] = mapped_column(String(50))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    status: Mapped[str] = mapped_column(String(30), default="paid")
    mailing_share: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    mailing_share_percent: Mapped[Decimal] = mapped_column(Numeric(5,2), default=0)
    producer_share_percent: Mapped[Decimal] = mapped_column(Numeric(5,2), default=0)
    is_producer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_messenger: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="licenses")
    artist = relationship("Artist", back_populates="licenses")
    beat = relationship("Beat", back_populates="licenses")


class LicenseEvent(Base):
    __tablename__ = "license_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(40))
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    license = relationship("License")


class LicenseSplit(Base):
    __tablename__ = "license_splits"
    id: Mapped[int] = mapped_column(primary_key=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(30))
    percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    license = relationship("License")
    user = relationship("User")

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    user = relationship("User", back_populates="notifications")
