"""R2.8 interview intelligence tests."""

from app.models import EvidenceItem
from app.services.interview import generate_interview_pack


def test_interview_pack_uses_approved_evidence(client, auth_headers):
    gen = client.app.dependency_overrides.values()
    from app.database import get_db

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    db.add(
        EvidenceItem(
            evidence_id="TEST_EVIDENCE_R28",
            category="leadership",
            statement="Led QE platform modernization with measurable release confidence gains.",
            status="USER_CONFIRMED",
            public_use=True,
        )
    )
    db.commit()

    job = client.post(
        "/api/jobs/ingest",
        headers=auth_headers,
        json={
            "source": "manual",
            "external_id": "interview-r28-job",
            "title": "Director QE",
            "company": "Interview Co",
            "url": "https://jobs.lever.co/interview/abc",
            "description_text": "Interview intelligence test",
        },
    ).json()
    job_id = job["id"]
    pack_res = client.post(f"/api/interviews/jobs/{job_id}/generate", headers=auth_headers)
    assert pack_res.status_code == 200
    pack = pack_res.json()
    assert pack["star_stories"]
    assert "interview_rounds" in pack
    assert "negotiation_prep" in pack
    assert "document_links" in pack
