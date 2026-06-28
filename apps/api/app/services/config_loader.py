from pathlib import Path

import yaml

from app.config import settings


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def load_yaml(relative_path: str) -> dict:
    path = _repo_root() / relative_path
    if not path.exists():
        path = Path(settings.config_root) / Path(relative_path).name
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def scoring_rubric() -> dict:
    return load_yaml("config/scoring-rubric.yml")


def source_policy() -> dict:
    return load_yaml("config/source-policy.yml")


def workflow_states() -> list[str]:
    data = load_yaml("config/workflow-states.yml")
    return data.get("states", [])


def budget_policy() -> dict:
    return load_yaml("config/budget-policy.yml")


def candidate_profile() -> dict:
    return load_yaml("config/candidate-profile.yml")
