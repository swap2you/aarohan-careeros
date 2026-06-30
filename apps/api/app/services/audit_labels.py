"""Human-readable audit event labels."""

AUDIT_EVENT_LABELS: dict[str, str] = {
    "job.ingested": "Job ingested",
    "job.deduplicated": "Duplicate job skipped",
    "job.scored": "Job scored",
    "packet.generated": "Application packet generated",
    "packet.approved": "Packet approved",
    "packet.rejected": "Packet rejected",
    "application.submitted": "Application marked submitted",
    "workflow.ingest_fixture": "Fixture jobs imported",
    "workflow.ingest_public": "Public feed jobs imported",
    "connector.run": "Job connector run",
    "oauth.connected": "Google account connected",
    "oauth.disconnected": "Google account disconnected",
    "gmail.sync": "Gmail sync completed",
    "gmail.quarantined": "Gmail message quarantined",
    "duplicate.override": "Duplicate risk overridden",
    "validation.run": "Validation run",
    "tts.generated": "Text-to-speech generated",
    "ask.query": "Ask Aarohan query",
    "interview.pack_generated": "Interview pack generated",
}


def audit_event_label(event_type: str) -> str:
    return AUDIT_EVENT_LABELS.get(event_type, event_type.replace(".", " ").replace("_", " ").title())
