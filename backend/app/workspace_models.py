from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def utcnow(): return datetime.now(timezone.utc)

class WorkspaceFavorite(Base):
    __tablename__ = 'workspace_favorites'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint('user_id','entity_type','entity_id', name='uq_workspace_favorite'),)

class WorkspaceFollowUp(Base):
    __tablename__ = 'workspace_followups'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    artist_id: Mapped[int] = mapped_column(ForeignKey('artists.id', ondelete='CASCADE'))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(String(160), default='Follow up')
    notes: Mapped[str | None] = mapped_column(Text)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class WorkspaceGoal(Base):
    __tablename__ = 'workspace_goals'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(String(160))
    target: Mapped[Decimal] = mapped_column(Numeric(12,2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default='USD', nullable=False)
    current: Mapped[Decimal] = mapped_column(Numeric(12,2), default=0)
    period: Mapped[str] = mapped_column(String(30), default='month')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class WorkspaceTag(Base):
    __tablename__ = 'workspace_tags'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    beat_id: Mapped[int] = mapped_column(ForeignKey('beats.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(60))
    __table_args__ = (UniqueConstraint('user_id','beat_id','name', name='uq_workspace_tag'),)


class AdminAuditLog(Base):
    __tablename__ = 'admin_audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    action: Mapped[str] = mapped_column(String(80))
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class LicenseVersion(Base):
    __tablename__ = 'license_versions'
    id: Mapped[int] = mapped_column(primary_key=True)
    license_id: Mapped[int] = mapped_column(ForeignKey('licenses.id', ondelete='CASCADE'))
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    snapshot_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
