from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
import os
import smtplib
from email.message import EmailMessage
from secrets import randbelow, token_urlsafe
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .storage import IntegrityEvent, Interview, Organization, SessionToken, User, db_session, init_db

app = FastAPI(title="AuthentiQ API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
init_db()

class InterviewStatus(str, Enum):
    scheduled = "scheduled"
    live = "live"
    completed = "completed"

class MonitoringPolicy(BaseModel):
    identity_verification: bool = True
    continuous_face_presence: bool = True
    liveness_challenges: bool = True
    gaze_analysis: bool = True
    browser_activity: bool = True
    screen_sharing: bool = True
    deepfake_analysis: bool = True
    audio_analysis: bool = True

class InterviewCreate(BaseModel):
    candidate_name: str = Field(min_length=2)
    candidate_email: str
    candidate_reference: str | None = None
    title: str = Field(min_length=2)
    description: str | None = None
    scheduled_at: datetime
    duration_minutes: int = Field(default=45, ge=15, le=240)
    monitoring: MonitoringPolicy = MonitoringPolicy()

class IntegrityEventCreate(BaseModel):
    type: str
    timestamp: datetime
    confidence: float | None = Field(default=None, ge=0, le=1)
    severity: str = "informational"
    metadata: dict[str, Any] = {}

class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    organization: str = Field(min_length=2, max_length=160)
    email: str
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(BaseModel):
    email: str
    password: str

class OTPRequest(BaseModel):
    email: str
    otp: str = Field(min_length=6, max_length=6)

class SessionResponse(BaseModel):
    session_token: str
    user_id: str
    organization_id: str

interviews: dict[str, dict[str, Any]] = {}
events: dict[str, list[dict[str, Any]]] = {}
users: dict[str, dict[str, Any]] = {}
pending_otps: dict[str, dict[str, Any]] = {}
rate_limits: dict[str, list[datetime]] = {}

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def normalize_email(email: str) -> str:
    return email.strip().lower()

def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or token_urlsafe(16)
    digest = pbkdf2_hmac("sha256", password.encode(), salt.encode(), 220_000).hex()
    return f"{salt}${digest}"

def password_matches(password: str, stored: str) -> bool:
    salt, expected = stored.split("$", 1)
    actual = pbkdf2_hmac("sha256", password.encode(), salt.encode(), 220_000).hex()
    return compare_digest(actual, expected)

def enforce_rate_limit(key: str, limit: int = 5, window_minutes: int = 15) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    recent = [stamp for stamp in rate_limits.get(key, []) if stamp > cutoff]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")
    recent.append(datetime.now(timezone.utc))
    rate_limits[key] = recent

def send_otp(email: str, code: str, purpose: str) -> None:
    host = os.getenv("SMTP_HOST")
    username = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    if not all([host, username, password]):
        if os.getenv("APP_ENV", "development") == "development":
            print(f"[AuthentiQ development OTP] {purpose} for {email}: {code}")
            return
        raise HTTPException(status_code=503, detail="Email service is not configured.")
    message = EmailMessage()
    message["Subject"] = f"Your AuthentiQ {purpose} code"
    message["From"] = os.getenv("SMTP_FROM", username)
    message["To"] = email
    message.set_content(f"Your AuthentiQ verification code is {code}. It expires in 10 minutes.")
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(message)

def issue_otp(email: str, purpose: str) -> None:
    code = f"{randbelow(1_000_000):06d}"
    pending_otps[email] = {"hash": password_hash(code), "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10), "purpose": purpose, "attempts": 0}
    send_otp(email, code, purpose)

def token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()

def create_session(user_id: str, organization_id: str) -> str:
    raw = token_urlsafe(48)
    with db_session() as db:
        db.add(SessionToken(token_hash=token_digest(raw), user_id=user_id, organization_id=organization_id, expires_at=datetime.now(timezone.utc) + timedelta(days=7)))
        db.commit()
    return raw

def current_session(authorization: str | None = Header(default=None)) -> dict[str, str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    with db_session() as db:
        session = db.get(SessionToken, token_digest(authorization.split(" ", 1)[1]))
        if not session or session.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
        return {"user_id": session.user_id, "organization_id": session.organization_id}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "authentiq-api"}

@app.post("/api/v1/auth/signup/request-otp")
def signup_request_otp(payload: SignupRequest, request: Request) -> dict[str, str]:
    email = normalize_email(payload.email)
    enforce_rate_limit(f"signup:{request.client.host if request.client else 'unknown'}:{email}")
    with db_session() as db:
        existing = db.query(User).filter(User.email == email).first()
    if existing or email in users:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    record = {"id": f"usr_{uuid4().hex[:10]}", "name": payload.name, "organization": payload.organization, "email": email, "password_hash": password_hash(payload.password), "verified": False, "created_at": now()}
    users[email] = record
    with db_session() as db:
        organization = Organization(id=f"org_{uuid4().hex[:10]}", name=payload.organization)
        db.add(organization)
        db.add(User(**{**record, "organization": organization.id, "created_at": datetime.now(timezone.utc)}))
        db.commit()
    issue_otp(email, "signup")
    return {"status": "otp_sent", "message": "A verification code has been sent to your email."}

@app.post("/api/v1/auth/signup/verify")
def signup_verify(payload: OTPRequest) -> dict[str, str]:
    email, record = normalize_email(payload.email), pending_otps.get(normalize_email(payload.email))
    user = users.get(email)
    if not user:
        with db_session() as db:
            stored = db.query(User).filter(User.email == email).first()
            if stored:
                user = {"id": stored.id, "name": stored.name, "organization": stored.organization, "email": stored.email, "password_hash": stored.password_hash, "verified": stored.verified}
                users[email] = user
    if not record or not user or record["purpose"] != "signup" or record["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This verification code is invalid or expired.")
    record["attempts"] += 1
    if record["attempts"] > 5 or not password_matches(payload.otp, record["hash"]):
        raise HTTPException(status_code=400, detail="This verification code is invalid.")
    user["verified"] = True
    with db_session() as db:
        stored = db.get(User, user["id"])
        if stored:
            stored.verified = True
            db.commit()
    pending_otps.pop(email, None)
    return {"status": "verified", "message": "Your AuthentiQ account is verified."}

@app.post("/api/v1/auth/login/request-otp")
def login_request_otp(payload: LoginRequest, request: Request) -> dict[str, str]:
    email = normalize_email(payload.email)
    enforce_rate_limit(f"login:{request.client.host if request.client else 'unknown'}:{email}")
    user = users.get(email)
    if not user:
        with db_session() as db:
            stored = db.query(User).filter(User.email == email).first()
            if stored:
                user = {"id": stored.id, "name": stored.name, "organization": stored.organization, "email": stored.email, "password_hash": stored.password_hash, "verified": stored.verified}
                users[email] = user
    if not user or not password_matches(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user["verified"]:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")
    issue_otp(email, "login")
    return {"status": "otp_sent", "message": "A login code has been sent to your email."}

@app.post("/api/v1/auth/login/verify")
def login_verify(payload: OTPRequest) -> dict[str, str]:
    email, record = normalize_email(payload.email), pending_otps.get(normalize_email(payload.email))
    if not record or record["purpose"] != "login" or record["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This login code is invalid or expired.")
    record["attempts"] += 1
    if record["attempts"] > 5 or not password_matches(payload.otp, record["hash"]):
        raise HTTPException(status_code=400, detail="This login code is invalid.")
    pending_otps.pop(email, None)
    with db_session() as db:
        stored = db.query(User).filter(User.email == email).first()
        if not stored:
            raise HTTPException(status_code=401, detail="Account not found.")
        session = create_session(stored.id, stored.organization)
    return {"status": "authenticated", "session_token": session, "message": "Login successful."}

@app.post("/api/v1/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
    if authorization and authorization.lower().startswith("bearer "):
        with db_session() as db:
            session = db.get(SessionToken, token_digest(authorization.split(" ", 1)[1]))
            if session:
                db.delete(session)
                db.commit()
    return {"status": "logged_out"}

@app.post("/api/v1/interviews", status_code=201)
def create_interview(payload: InterviewCreate, session: dict[str, str] = Depends(current_session)) -> dict[str, Any]:
    x_organization_id = session["organization_id"]
    interview_id = f"int_{uuid4().hex[:10]}"
    record = {"id": interview_id, "organization_id": x_organization_id, "status": InterviewStatus.scheduled, "created_at": now(), "invitation_token": token_urlsafe(32), "room_name": f"room_{interview_id}", **payload.model_dump(mode="json")}
    with db_session() as db:
        db.add(Interview(id=interview_id, organization_id=x_organization_id, candidate_name=payload.candidate_name, candidate_email=payload.candidate_email, title=payload.title, description=payload.description, scheduled_at=payload.scheduled_at, duration_minutes=payload.duration_minutes, status=InterviewStatus.scheduled.value, monitoring=payload.monitoring.model_dump(), invitation_token=record["invitation_token"], room_name=record["room_name"]))
        db.commit()
    interviews[interview_id] = record
    events[interview_id] = []
    return record

@app.get("/api/v1/interviews")
def list_interviews(session: dict[str, str] = Depends(current_session)) -> list[dict[str, Any]]:
    x_organization_id = session["organization_id"]
    with db_session() as db:
        rows = db.query(Interview).filter(Interview.organization_id == x_organization_id).order_by(Interview.scheduled_at).all()
        return [{"id": row.id, "organization_id": row.organization_id, "candidate_name": row.candidate_name, "candidate_email": row.candidate_email, "title": row.title, "description": row.description, "scheduled_at": row.scheduled_at.isoformat(), "duration_minutes": row.duration_minutes, "status": row.status, "monitoring": row.monitoring, "invitation_token": row.invitation_token, "room_name": row.room_name, "created_at": row.created_at.isoformat()} for row in rows]

@app.get("/api/v1/interviews/{interview_id}")
def get_interview(interview_id: str, session: dict[str, str] = Depends(current_session)) -> dict[str, Any]:
    with db_session() as db:
        row = db.get(Interview, interview_id)
        if not row or row.organization_id != session["organization_id"]:
            raise HTTPException(status_code=404, detail="Interview not found")
        event_rows = db.query(IntegrityEvent).filter(IntegrityEvent.interview_id == interview_id).order_by(IntegrityEvent.timestamp).all()
        return {"id": row.id, "organization_id": row.organization_id, "candidate_name": row.candidate_name, "candidate_email": row.candidate_email, "title": row.title, "description": row.description, "scheduled_at": row.scheduled_at.isoformat(), "duration_minutes": row.duration_minutes, "status": row.status, "monitoring": row.monitoring, "invitation_token": row.invitation_token, "room_name": row.room_name, "events": [{"id": e.id, "interview_id": e.interview_id, "type": e.type, "timestamp": e.timestamp.isoformat(), "confidence": e.confidence, "severity": e.severity, "metadata": e.event_metadata, "created_at": e.created_at.isoformat()} for e in event_rows]}

@app.post("/api/v1/interviews/{interview_id}/events", status_code=201)
def add_event(interview_id: str, payload: IntegrityEventCreate, session: dict[str, str] = Depends(current_session)) -> dict[str, Any]:
    with db_session() as db:
        interview = db.get(Interview, interview_id)
        if not interview or interview.organization_id != session["organization_id"]:
            raise HTTPException(status_code=404, detail="Interview not found")
    event = {"id": f"evt_{uuid4().hex[:10]}", "interview_id": interview_id, "created_at": now(), **payload.model_dump(mode="json")}
    with db_session() as db:
        db.add(IntegrityEvent(id=event["id"], interview_id=interview_id, type=payload.type, timestamp=payload.timestamp, confidence=payload.confidence, severity=payload.severity, event_metadata=payload.metadata))
        db.commit()
    return event
