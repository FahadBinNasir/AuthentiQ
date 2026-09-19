from datetime import datetime, timezone
from enum import Enum
from secrets import token_urlsafe
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="AuthentiQ API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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

interviews: dict[str, dict[str, Any]] = {}
events: dict[str, list[dict[str, Any]]] = {}

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "authentiq-api"}

@app.post("/api/v1/interviews", status_code=201)
def create_interview(payload: InterviewCreate, x_organization_id: str = Header(default="demo-organization")) -> dict[str, Any]:
    interview_id = f"int_{uuid4().hex[:10]}"
    record = {"id": interview_id, "organization_id": x_organization_id, "status": InterviewStatus.scheduled, "created_at": now(), "invitation_token": token_urlsafe(32), "room_name": f"room_{interview_id}", **payload.model_dump(mode="json")}
    interviews[interview_id] = record
    events[interview_id] = []
    return record

@app.get("/api/v1/interviews")
def list_interviews(x_organization_id: str = Header(default="demo-organization")) -> list[dict[str, Any]]:
    return [item for item in interviews.values() if item["organization_id"] == x_organization_id]

@app.get("/api/v1/interviews/{interview_id}")
def get_interview(interview_id: str) -> dict[str, Any]:
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")
    return {**interviews[interview_id], "events": events[interview_id]}

@app.post("/api/v1/interviews/{interview_id}/events", status_code=201)
def add_event(interview_id: str, payload: IntegrityEventCreate) -> dict[str, Any]:
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")
    event = {"id": f"evt_{uuid4().hex[:10]}", "interview_id": interview_id, "created_at": now(), **payload.model_dump(mode="json")}
    events[interview_id].append(event)
    return event
