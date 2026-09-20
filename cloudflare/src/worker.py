from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from workers import asgi, DurableObject, Response

app = FastAPI(title="AuthentiQ Cloudflare API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def env(request: Request):
    return request.scope["env"]


@app.get("/health")
async def health():
    return {"status": "ok", "service": "authentiq-cloudflare-api"}


@app.get("/health/ready")
async def readiness(request: Request):
    result = await env(request).DB.prepare("SELECT 1 AS ok").first()
    return {"status": "ready", "database": result["ok"] == 1, "checked_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/status")
async def api_status(request: Request):
    result = await env(request).DB.prepare("SELECT COUNT(*) AS organizations FROM organizations").first()
    return {"service": "authentiq", "database": "d1", "organizations": result["organizations"]}


class InterviewRoom(DurableObject):
    """Reserved for signaling and room presence; media remains peer-to-peer WebRTC."""

    async def fetch(self, request):
        return Response.json({"status": "room-online"})


Default = asgi.entrypoint(app)
