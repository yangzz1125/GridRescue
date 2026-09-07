"""Canonical competition facts used by reports and UI.

The V08 freeze remains immutable; this module only exposes a small, typed
read-only view so presentation layers do not duplicate numbers or claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class CompetitionFacts:
    project: str = "GridRescue 碳韧智网"
    release: str = "V08"
    freeze_date: str = "2026-08-22"
    generated_at: str = "2026-08-23"
    tests_passed: int = 46
    tests_duration_s: float = 160.6
    mrv_bundle_count: int = 3
    mrv_checked_files: int = 17
    gas_basis: str = "CO2"
    unit: str = "kgCO2"
    factor_class: str = "E"
    time_step_h: float = 1.0
    same_service_pass: bool = False
    claim_status: str = "controlled_service_budget_inventory_difference"

    @property
    def claim_label(self) -> str:
        return "受控服务预算下的运行碳清单差异"

    @property
    def frozen_label(self) -> str:
        return f"FROZEN EVIDENCE · {self.release} · {self.freeze_date}"


FACTS = CompetitionFacts()


def validate_text(text: str, facts: CompetitionFacts = FACTS) -> list[str]:
    """Return forbidden or inconsistent claim fragments in a document."""
    errors: list[str] = []
    if "kgCO2e" in text or "CO₂e" in text:
        errors.append("use kgCO2, not kgCO2e/CO₂e")
    if facts.same_service_pass is False and re.search(r"严格同服务.*(减排|降碳)|同服务.*严格.*(减排|降碳)", text):
        errors.append("same_service_pass=false forbids strict same-service reduction wording")
    return errors


def facts_path(project_root: str | Path) -> Path:
    return Path(project_root) / "docs" / "competition_factsheet.yaml"
