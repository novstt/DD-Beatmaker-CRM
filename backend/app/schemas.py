from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =========================
# AUTH
# =========================

class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_admin: bool
    is_active: bool
    theme: str
    currency: str
    created_at: datetime
    last_login: datetime | None = None


class UserSettingsUpdate(BaseModel):
    theme: str | None = None
    currency: str | None = None


# =========================
# ARTISTS
# =========================

class ArtistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    platform: str | None = None
    artist_username: str | None = None
    message_status: str = "unread"
    cash_ready: bool = False
    notes: str | None = None


class ArtistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    normalized_name: str
    platform: str | None = None
    artist_username: str | None = None
    message_status: str | None = None
    cash_ready: bool = False
    beats_sent_count: int = 0
    licenses_count: int = 0


class ArtistAddContact(BaseModel):
    platform: str
    artist_username: str
    message_status: str = "unread"
    beat_ids: list[int] = Field(default_factory=list)
    cash_ready: bool = False
    notes: str | None = None


class ArtistContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    artist_id: int
    platform: str | None
    artist_username: str | None
    message_status: str
    cash_ready: bool
    notes: str | None


# =========================
# BEATS
# =========================

class BeatCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    bpm: int | None = None
    musical_key: str | None = None
    status: str = "available"
    producer_username: str | None = None
    co_producer_usernames: list[str] = Field(default_factory=list)


class BeatUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    bpm: int | None = None
    musical_key: str | None = None
    status: str = "available"
    producer_username: str | None = None
    co_producer_usernames: list[str] = Field(default_factory=list)


class BeatProducerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int | None = None
    username: str | None = None
    display_name: str | None = None
    share_percent: Decimal


class BeatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    bpm: int | None
    musical_key: str | None
    status: str
    google_drive_link: str | None
    created_at: datetime
    producer_username: str | None = None
    messenger_id: int | None = None
    messenger_username: str | None = None
    producers: list[BeatProducerOut] = Field(default_factory=list)


class BeatSendCreate(BaseModel):
    artist_id: int
    beat_id: int


# =========================
# LICENSES
# =========================

class LicenseCreate(BaseModel):
    artist_id: int
    beat_id: int | None = None
    license_type: str
    price: Decimal
    currency: str = "USD"
    status: str = "paid"
    notes: str | None = None


class LicenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    artist_id: int
    beat_id: int | None
    license_type: str
    price: Decimal
    currency: str = "USD"
    purchased_at: datetime
    status: str
    mailing_share: Decimal
    mailing_share_percent: Decimal = Decimal("0")
    producer_share_percent: Decimal = Decimal("0")
    is_producer: bool = False
    is_messenger: bool = False
    notes: str | None


# =========================
# STATS
# =========================

class DashboardStats(BaseModel):
    total_artists: int
    my_artists: int
    total_beats: int
    licenses_sold: int
    revenue: Decimal
    expected_revenue: Decimal


# Backwards-compatible name used by some versions
class DashboardOut(DashboardStats):
    pass


# =========================
# ADMIN
# =========================

class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_admin: bool
    is_active: bool
    theme: str
    created_at: datetime
    last_login: datetime | None = None


# =========================
# NOTIFICATIONS
# =========================

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
