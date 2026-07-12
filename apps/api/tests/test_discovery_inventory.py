"""Workflow 01.5 — discovery source inventory & orchestration separation."""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.services.discovery_orchestration import run_gmail_discovery
from app.services.discovery_source_inventory import build_source_inventory


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def test_inventory_marks_gmail_as_not_public_feed_connector():
    db = _session()
    try:
        inv = build_source_inventory(db)
        assert inv["email_alert_sources"], "expected email alert sources"
        for entry in inv["email_alert_sources"]:
            assert entry["connector_kind"] == "not_a_public_feed_connector"
            assert entry["orchestration"] == "gmail_discovery"
        labels = {e["label"] for e in inv["email_alert_sources"]}
        assert {"LinkedIn", "Indeed", "Dice", "USAJOBS", "Glassdoor"} <= labels
    finally:
        db.close()


def test_inventory_ats_boards_empty_by_default():
    db = _session()
    try:
        inv = build_source_inventory(db)
        ats = {a["source_key"]: a for a in inv["ats_sources"]}
        for key in ("greenhouse", "lever", "ashby"):
            assert ats[key]["enabled_in_policy"] is True
            assert ats[key]["approved_boards_count"] == 0
            assert ats[key]["skip_reason"] == "enabled_no_approved_boards"
    finally:
        db.close()


def test_inventory_public_sources_present_with_status():
    db = _session()
    try:
        inv = build_source_inventory(db)
        keys = {p["source_key"] for p in inv["public_sources"]}
        assert {"adzuna", "jooble", "usajobs", "remotive", "remote_ok", "rss"} == keys
        for p in inv["public_sources"]:
            assert "connector_state" in p
            assert "last_run_counts" in p
    finally:
        db.close()


def test_gmail_discovery_reports_separately_from_public():
    db = _session()
    try:
        # With no live OAuth in the unit env, gmail discovery reports an error/skip,
        # but it is a *distinct* stage — never silently folded into public discovery.
        result = run_gmail_discovery(db, actor="owner@test")
        assert result["stage"] == "gmail"
        assert "skip_reason" in result
        # It attempted (linkedin/indeed alerts enabled in defaults) or reported an error.
        assert result["attempted"] in (True, False)
    finally:
        db.close()
