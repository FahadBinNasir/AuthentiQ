# AuthentiQ API

The first API slice keeps storage replaceable. It exposes the contract for interviews, secure invitations, monitoring policies, and integrity events while PostgreSQL and authentication are added next.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

OpenAPI is available at `http://localhost:8000/docs`.
