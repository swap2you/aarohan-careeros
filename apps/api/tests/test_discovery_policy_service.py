"""Workflow 01.5 — versioned discovery policy: merge, validation, versioning, presets, preview.

Covers effective-policy merge, override validation, version create/activate/restore,
cache invalidation, the strict/balanced/broad presets, and that Broad is never unfiltered
(foreign-only and default reject/domain patterns are always preserved).
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job, WorkflowState
from app.services import discovery_policy_service as pol
from app.services.discovery_policy import (
    clear_discovery_policy_cache,
    discovery_policy_defaults,
    job_discovery_policy,
    set_active_override,
)


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def teardown_function(_):
    # Always restore the global effective policy to file defaults between tests.
    set_active_override(None)
    clear_discovery_policy_cache()


# ---- merge / effective ---------------------------------------------------------------
def test_effective_equals_defaults_with_no_override():
    set_active_override(None)
    assert job_discovery_policy() == discovery_policy_defaults()


def test_effective_merge_changes_freshness_and_preserves_safety():
    eff = pol.effective_from_overrides({"freshness_days": 3})
    assert eff["freshness"]["recent_hours"] == 72
    # foreign-only reject is never removed
    assert eff["geography"]["foreign_only"] == "reject"
    # default reject patterns preserved
    defaults = discovery_policy_defaults()
    for pattern in defaults["role_reject_patterns"]:
        assert pattern in eff["role_reject_patterns"]


def test_title_exclude_only_adds_never_removes():
    eff = pol.effective_from_overrides({"title_exclude": ["blockchain evangelist"]})
    assert "blockchain evangelist" in eff["role_reject_patterns"]
    for pattern in discovery_policy_defaults()["role_reject_patterns"]:
        assert pattern in eff["role_reject_patterns"]


def test_domain_exclude_only_adds():
    eff = pol.effective_from_overrides({"domain_exclude": ["oilfield services"]})
    assert "oilfield services" in eff["domain_reject_patterns"]
    for pattern in discovery_policy_defaults()["domain_reject_patterns"]:
        assert pattern in eff["domain_reject_patterns"]


def test_provider_disable_merges_into_sources():
    eff = pol.effective_from_overrides({"providers": {"jooble": False}})
    assert eff["sources"]["jooble"]["enabled"] is False
    # provider_id preserved by deep-merge
    assert eff["sources"]["jooble"]["provider_id"] == "jooble"


# ---- validation ----------------------------------------------------------------------
def test_validate_rejects_unknown_key():
    with pytest.raises(pol.PolicyValidationError):
        pol.validate_overrides({"delete_everything": True})


def test_validate_rejects_bad_freshness_days():
    with pytest.raises(pol.PolicyValidationError):
        pol.validate_overrides({"freshness_days": 5})


def test_validate_rejects_bad_geo_action():
    with pytest.raises(pol.PolicyValidationError):
        pol.validate_overrides({"remote_us": "maybe"})


def test_validate_rejects_unknown_provider():
    with pytest.raises(pol.PolicyValidationError):
        pol.validate_overrides({"providers": {"monster": True}})


# ---- versioning / cache --------------------------------------------------------------
def test_version_create_activate_and_effective_cache_invalidation():
    db = _session()
    try:
        assert pol.get_active_version(db) is None
        draft = pol.create_draft(db, {"freshness_days": 3}, preset="strict", created_by="owner@test")
        assert draft.status == "draft"
        assert draft.version == 1
        # Not active yet -> effective still defaults
        assert job_discovery_policy()["freshness"]["recent_hours"] == discovery_policy_defaults()["freshness"]["recent_hours"]
        activated = pol.activate_version(db, draft.id, activated_by="owner@test")
        assert activated.status == "active"
        # Effective cache invalidated on activation
        assert job_discovery_policy()["freshness"]["recent_hours"] == 72
        assert pol.get_active_version(db).id == draft.id
    finally:
        set_active_override(None)
        clear_discovery_policy_cache()
        db.close()


def test_second_activation_archives_previous_single_active():
    db = _session()
    try:
        v1 = pol.create_draft(db, {"freshness_days": 3}, created_by="o")
        pol.activate_version(db, v1.id)
        v2 = pol.create_draft(db, {"freshness_days": 14}, created_by="o")
        pol.activate_version(db, v2.id)
        actives = [v for v in pol.list_versions(db) if v.status == "active"]
        assert len(actives) == 1
        assert actives[0].id == v2.id
        assert job_discovery_policy()["freshness"]["recent_hours"] == 336
    finally:
        set_active_override(None)
        clear_discovery_policy_cache()
        db.close()


def test_restore_defaults_activates_empty_override():
    db = _session()
    try:
        v1 = pol.create_draft(db, {"freshness_days": 3}, created_by="o")
        pol.activate_version(db, v1.id)
        assert job_discovery_policy()["freshness"]["recent_hours"] == 72
        pol.restore_defaults(db, actor="o")
        assert job_discovery_policy()["freshness"]["recent_hours"] == discovery_policy_defaults()["freshness"]["recent_hours"]
    finally:
        set_active_override(None)
        clear_discovery_policy_cache()
        db.close()


# ---- presets -------------------------------------------------------------------------
def test_presets_exist():
    assert set(pol.preset_names()) == {"strict", "balanced", "broad"}
    assert pol.preset_overrides("balanced") == {}


def test_strict_preset_is_narrower_than_broad():
    strict = pol.effective_from_overrides(pol.preset_overrides("strict"))
    broad = pol.effective_from_overrides(pol.preset_overrides("broad"))
    assert strict["freshness"]["recent_hours"] < broad["freshness"]["recent_hours"]
    # strict drops secondary families; broad keeps them
    strict_ids = {p["id"] for p in strict["role_profiles"]}
    broad_ids = {p["id"] for p in broad["role_profiles"]}
    assert broad_ids >= strict_ids


def test_broad_preset_is_not_unfiltered():
    broad = pol.effective_from_overrides(pol.preset_overrides("broad"))
    # Foreign-only stays rejected; reject/domain patterns preserved even in Broad.
    assert broad["geography"]["foreign_only"] == "reject"
    assert broad["geography"]["relocation_required"] == "reject"
    for pattern in discovery_policy_defaults()["domain_reject_patterns"]:
        assert pattern in broad["domain_reject_patterns"]


# ---- preview -------------------------------------------------------------------------
def _add_job(db, **kwargs):
    defaults = {
        "source": "jooble",
        "external_id": "p-1",
        "title": "Senior Manager, Quality Engineering",
        "company": "Acme",
        "location": "Remote, United States",
        "url": "https://example.com/jobs/1",
        "description_html": "",
        "description_text": "US remote software quality engineering leadership, CI/CD, automation.",
        "dedupe_key": "p-1",
        "data_provenance": "live",
        "discovered_at": datetime.utcnow(),
        "provider_posted_at": datetime.utcnow(),
        "effective_freshness_at": datetime.utcnow(),
        "eligible_for_owner": True,
        "ingest_decision": "ACCEPT",
        "state": WorkflowState.NORMALIZED.value,
    }
    defaults.update(kwargs)
    job = Job(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_preview_returns_counts_and_delta_without_persisting_override():
    db = _session()
    try:
        _add_job(db, external_id="a", dedupe_key="a")
        _add_job(db, external_id="b", dedupe_key="b", title="Warehouse Manager", description_text="forklift shift lead")
        now = datetime.utcnow()
        result = pol.preview_policy(db, {"freshness_days": 3}, now=now)
        assert result["sample_size"] == 2
        assert set(result["counts"]) == {"would_accept", "would_owner_review", "would_quarantine", "would_reject"}
        assert "delta" in result and "before_counts" in result
        # Preview must not leave a global override active
        assert job_discovery_policy() == discovery_policy_defaults()
    finally:
        set_active_override(None)
        clear_discovery_policy_cache()
        db.close()
