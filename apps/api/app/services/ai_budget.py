from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AIUsageRecord
from app.services.config_loader import budget_policy
from app.config import settings


class BudgetExceededError(Exception):
    pass


def _month_start() -> datetime:
    now = datetime.utcnow()
    return datetime(now.year, now.month, 1)


def current_month_spend(db: Session) -> float:
    total = (
        db.query(AIUsageRecord)
        .filter(AIUsageRecord.created_at >= _month_start())
        .with_entities(AIUsageRecord.cost_usd)
        .all()
    )
    return round(sum(row[0] for row in total), 4)


def enforce_budget(db: Session, estimated_cost: float, operation: str) -> None:
    policy = budget_policy().get("runtime_ai", {})
    hard_cap = float(policy.get("monthly_hard_cap_usd", settings.ai_monthly_hard_cap_usd))
    if not policy.get("stop_on_hard_cap", True):
        return
    spend = current_month_spend(db)
    if spend + estimated_cost > hard_cap:
        raise BudgetExceededError(
            f"AI hard cap reached for {operation}: spend={spend}, cap={hard_cap}"
        )


def record_usage(
    db: Session,
    *,
    operation: str,
    cost_usd: float,
    model: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    job_id: int | None = None,
    usage_kind: str = "estimated",
) -> AIUsageRecord:
    op_label = operation if usage_kind == "actual" else f"{usage_kind}:{operation}"
    record = AIUsageRecord(
        operation=op_label,
        model=model or ("deterministic" if usage_kind == "deterministic" else None),
        cost_usd=cost_usd,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        job_id=job_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def budget_status(db: Session) -> dict:
    policy = budget_policy().get("runtime_ai", {})
    soft_cap = float(policy.get("monthly_soft_cap_usd", settings.ai_monthly_soft_cap_usd))
    hard_cap = float(policy.get("monthly_hard_cap_usd", settings.ai_monthly_hard_cap_usd))
    spend = current_month_spend(db)
    return {
        "monthly_spend_usd": spend,
        "soft_cap_usd": soft_cap,
        "hard_cap_usd": hard_cap,
        "hard_cap_active": policy.get("stop_on_hard_cap", True),
        "percent_of_hard_cap": round((spend / hard_cap) * 100, 2) if hard_cap else 0,
        "alerts_at_percent": policy.get("alerts_at_percent", [50, 75, 90, 100]),
    }
