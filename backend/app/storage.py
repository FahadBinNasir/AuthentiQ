import os
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    organization: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(String(40), default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SessionToken(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(String(40), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(120), index=True)
    candidate_name: Mapped[str] = mapped_column(String(160))
    candidate_email: Mapped[str] = mapped_column(String(320))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
    monitoring: Mapped[dict[str, Any]] = mapped_column(JSON)
    invitation_token: Mapped[str] = mapped_column(String(160), unique=True)
    room_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class IntegrityEvent(Base):
    __tablename__ = "integrity_events"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    type: Mapped[str] = mapped_column(String(80))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(30), default="informational")
    # ``metadata`` is reserved by SQLAlchemy's declarative API. Keep the
    # database column name but use a safe Python attribute name.
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./authentiq.local.db")


engine = create_engine(database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def db_session() -> Session:
    return SessionLocal()
