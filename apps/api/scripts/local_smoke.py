"""Local end-to-end smoke proof without Docker."""

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./local_smoke.db")
os.environ.setdefault("APP_SECRET", "local-smoke-secret-32chars-min!")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "local-smoke-token-key-32chars!!")
os.environ.setdefault("OAUTH_FIXTURE_MODE", "true")
os.environ.setdefault("GENERATED_ROOT", str(Path(__file__).resolve().parents[1] / "generated"))

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import EvidenceItem, User  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.setup import mark_setup_complete  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()
if db.query(User).count() == 0:
    db.add(User(email="smoke@test.local", hashed_password=hash_password("SmokeTestPass123!"), is_admin=True))
    for eid, stmt in [
        ("PENNDOT_STACK", "Enterprise development across .NET, Java, Spring REST APIs."),
        ("ASCENSUS_SDET", "Ascensus Sr Principal SDET – Automation Framework Architect."),
        ("PERSISTENT_PROJECT_LEAD", "Persistent Systems Project Lead – QE Platform Architect."),
        ("TEAM_LEADERSHIP", "Leads four direct team members and offshore guidance."),
        ("MULTI_ROLE_DELIVERY", "Project leadership, Scrum facilitation, client communication."),
    ]:
        db.add(EvidenceItem(evidence_id=eid, category="technical", statement=stmt, status="USER_CONFIRMED", public_use=True))
    mark_setup_complete(db)
    db.commit()
db.close()

client = TestClient(app)
login = client.post("/api/auth/login", json={"email": "smoke@test.local", "password": "SmokeTestPass123!"})
assert login.status_code == 200, login.text
headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

steps = []
ingest = client.post("/api/workflows/ingest/fixture", headers=headers)
steps.append(("fixture_ingest", ingest.status_code))
job_id = ingest.json()["details"][0]["job_id"]

public = client.post("/api/workflows/ingest/public", headers=headers)
steps.append(("public_ingest", public.status_code))

packet = client.post(f"/api/applications/jobs/{job_id}/generate?resume_profile=qe_leadership", headers=headers)
steps.append(("packet_generate", packet.status_code))
app_id = packet.json()["id"]

preview = client.get(f"/api/validation/applications/{app_id}/preview", headers=headers)
steps.append(("preview", preview.status_code))

approve = client.post(f"/api/applications/{app_id}/actions", headers=headers, json={"action": "approve"})
steps.append(("approve", approve.status_code))

submit = client.post(f"/api/applications/{app_id}/actions", headers=headers, json={"action": "mark_submitted"})
steps.append(("mark_submitted", submit.status_code))

gmail = client.post("/api/integrations/gmail/sync-fixture", headers=headers)
steps.append(("recruiter_fixture", gmail.status_code))

interview = client.post(f"/api/interviews/jobs/{job_id}/generate", headers=headers)
steps.append(("interview_pack", interview.status_code))

consult = client.post("/api/consulting/leads", headers=headers, json={"company": "Smoke Co", "problem_summary": "flaky CI tests"})
steps.append(("consulting_lead", consult.status_code))

budget = client.get("/api/ai/budget", headers=headers)
steps.append(("ai_budget", budget.status_code))

audit = client.get("/api/audit", headers=headers)
steps.append(("audit_log", audit.status_code))

print("LOCAL SMOKE RESULTS")
for name, code in steps:
    print(f"  {name}: {code}")
failed = [s for s in steps if s[1] >= 400]
if failed:
    sys.exit(1)
print("ALL STEPS PASSED")
