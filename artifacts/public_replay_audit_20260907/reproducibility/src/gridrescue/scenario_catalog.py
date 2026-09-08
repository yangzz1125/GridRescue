"""Deterministic, replayable scenario catalog for competition experiments.

The catalog is intentionally independent from the V08 official bundles.  It
creates a small 3 disaster x 3 intensity x 4 replicate design (36 rows),
with the same seed and scenario hash reused by every strategy arm.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable
import csv

import numpy as np

from .scenarios import SCENARIOS, DisasterScenario


DISASTER_ORDER = ("暴雨内涝", "台风", "极端高温")
INTENSITY_ORDER = ("low", "medium", "high")
INTENSITY_SCALE = {"low": 0.85, "medium": 1.0, "high": 1.18}


@dataclass(frozen=True)
class ScenarioRecord:
    scenario_id: str
    disaster: str
    intensity: str
    replicate: int
    seed: int
    network_id: str
    care_contract_id: str
    factor_snapshot_id: str
    payload_sha256: str
    parameters: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_disaster_scenario(self) -> DisasterScenario:
        """Convert a catalog row into the existing pipeline input type."""
        payload = self.parameters
        return DisasterScenario(
            name=self.scenario_id,
            disaster_type=self.disaster,
            description=(
                f"Wave10 {self.disaster}/{self.intensity} replicate {self.replicate}; "
                "synthetic stress-test catalog"
            ),
            failed_branch_ids=tuple(int(x) for x in payload["failed_branch_ids"]),
            repair_hours=tuple(int(x) for x in payload["repair_hours"]),
            pv_derating=float(payload["pv_derating"]),
            grid_carbon_multiplier=float(payload["grid_carbon_multiplier"]),
            crew_distance_km=float(payload["crew_distance_km"]),
            ambient_temperature_c=float(payload["ambient_temperature_c"]),
        )


def _canonical_payload(
    disaster: str,
    intensity: str,
    replicate: int,
    seed: int,
    scenario: DisasterScenario,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    scale = INTENSITY_SCALE[intensity]
    # Keep the perturbations bounded and explainable: the catalog is a
    # stress-test design, not a claim about a real disaster distribution.
    failed = tuple(sorted(set(scenario.failed_branch_ids)))
    repair = tuple(max(1, int(round(h * scale + rng.integers(-1, 2)))) for h in scenario.repair_hours)
    payload = {
        "disaster": disaster,
        "intensity": intensity,
        "replicate": replicate,
        "seed": seed,
        "failed_branch_ids": failed,
        "repair_hours": repair,
        "pv_derating": round(float(np.clip(scenario.pv_derating / scale, 0.05, 0.98)), 6),
        "grid_carbon_multiplier": round(float(scenario.grid_carbon_multiplier * (1 + 0.03 * (scale - 1))), 6),
        "crew_distance_km": round(float(scenario.crew_distance_km * scale), 6),
        "ambient_temperature_c": round(float(scenario.ambient_temperature_c + 2 * (scale - 1)), 6),
    }
    return payload


def build_catalog(
    *,
    root_seed: int = 20260822,
    network_id: str = "case33bw",
    care_contract_id: str = "care-v08-e-class-1",
    factor_snapshot_id: str = "factor-registry-v08",
) -> list[ScenarioRecord]:
    if root_seed < 0:
        raise ValueError("root_seed must be non-negative")
    records: list[ScenarioRecord] = []
    for disaster_idx, disaster in enumerate(DISASTER_ORDER):
        base = SCENARIOS[disaster]
        for intensity_idx, intensity in enumerate(INTENSITY_ORDER):
            for replicate in range(1, 5):
                seed = root_seed + disaster_idx * 10000 + intensity_idx * 100 + replicate
                payload = _canonical_payload(disaster, intensity, replicate, seed, base)
                canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                records.append(
                    ScenarioRecord(
                        scenario_id=f"W10-{disaster_idx + 1:02d}-{intensity_idx + 1:02d}-{replicate:02d}",
                        disaster=disaster,
                        intensity=intensity,
                        replicate=replicate,
                        seed=seed,
                        network_id=network_id,
                        care_contract_id=care_contract_id,
                        factor_snapshot_id=factor_snapshot_id,
                        payload_sha256=digest,
                        parameters=payload,
                    )
                )
    return records


def catalog_manifest(records: Iterable[ScenarioRecord], *, root_seed: int = 20260822) -> dict[str, object]:
    rows = list(records)
    if not rows:
        raise ValueError("catalog cannot be empty")
    catalog_text = "\n".join(
        json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in rows
    )
    return {
        "schema_version": "gridrescue-wave10-scenario-catalog-1.0",
        "freeze_date": "2026-08-22",
        "generated_at": "2026-08-23",
        "root_seed": root_seed,
        "count": len(rows),
        "strata": {"disaster": len(DISASTER_ORDER), "intensity": len(INTENSITY_ORDER), "replicates": 4},
        "catalog_sha256": hashlib.sha256(catalog_text.encode("utf-8")).hexdigest(),
        "data_class": "E",
        "claim_boundary": "synthetic stress-test catalog; not an observed disaster distribution",
    }


def write_catalog(path: str | Path, *, root_seed: int = 20260822) -> tuple[Path, Path]:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    records = build_catalog(root_seed=root_seed)
    jsonl = output / "scenario_catalog.jsonl"
    jsonl.write_text(
        "".join(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )
    manifest_path = output / "catalog_manifest.json"
    manifest_path.write_text(json.dumps(catalog_manifest(records, root_seed=root_seed), ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = output / "scenario_catalog.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["scenario_id", "disaster", "intensity", "replicate", "seed", "network_id", "care_contract_id", "factor_snapshot_id", "payload_sha256"],
        )
        writer.writeheader()
        for row in records:
            writer.writerow({key: getattr(row, key) for key in writer.fieldnames})
    return jsonl, manifest_path
