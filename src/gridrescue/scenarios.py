from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .carbon import DEFAULT_EMISSION_FACTORS


@dataclass(frozen=True)
class DisasterScenario:
    name: str
    description: str
    failed_branch_ids: tuple[int, ...]
    repair_hours: tuple[int, ...]
    pv_derating: float
    grid_carbon_multiplier: float
    crew_distance_km: float
    ambient_temperature_c: float

    def __post_init__(self) -> None:
        if len(self.failed_branch_ids) != len(self.repair_hours):
            raise ValueError("failed branches and repair durations must align")
        if not 0 <= self.pv_derating <= 1:
            raise ValueError("pv_derating must be in [0, 1]")


SCENARIOS: dict[str, DisasterScenario] = {
    "暴雨内涝": DisasterScenario(
        name="暴雨内涝",
        description="低洼区域电缆与开关站受淹，多点故障且光伏出力降低。",
        failed_branch_ids=(6, 13, 27),
        repair_hours=(7, 10, 6),
        pv_derating=0.38,
        grid_carbon_multiplier=1.08,
        crew_distance_km=46.0,
        ambient_temperature_c=25.0,
    ),
    "台风": DisasterScenario(
        name="台风",
        description="架空线路风偏、倒杆造成分散故障，抢修通行距离增加。",
        failed_branch_ids=(2, 18, 24, 30),
        repair_hours=(5, 9, 8, 11),
        pv_derating=0.22,
        grid_carbon_multiplier=1.12,
        crew_distance_km=72.0,
        ambient_temperature_c=27.0,
    ),
    "极端高温": DisasterScenario(
        name="极端高温",
        description="空调负荷上升叠加线路热稳定降额，引发局部过载故障。",
        failed_branch_ids=(8, 21),
        repair_hours=(4, 7),
        pv_derating=0.82,
        grid_carbon_multiplier=1.18,
        crew_distance_km=28.0,
        ambient_temperature_c=43.0,
    ),
}


def get_scenario(name: str) -> DisasterScenario:
    try:
        return SCENARIOS[name]
    except KeyError as exc:
        raise KeyError(f"unknown scenario {name!r}; choose from {list(SCENARIOS)}") from exc


def hourly_profiles(scenario: DisasterScenario, seed: int = 2026) -> pd.DataFrame:
    """Return a deterministic 24-hour restoration environment."""

    rng = np.random.default_rng(seed + sum(scenario.failed_branch_ids))
    hour = np.arange(24)
    load_multiplier = 0.78 + 0.14 * np.sin(2 * np.pi * (hour - 8) / 24)
    load_multiplier += 0.23 * np.exp(-0.5 * ((hour - 19) / 2.7) ** 2)
    if scenario.name == "极端高温":
        load_multiplier += 0.20 * np.exp(-0.5 * ((hour - 15) / 4.0) ** 2)
    load_multiplier += rng.normal(0, 0.012, 24)

    daylight = np.clip(np.sin(np.pi * (hour - 6) / 13), 0, None)
    pv_multiplier = daylight * scenario.pv_derating
    grid_carbon = DEFAULT_EMISSION_FACTORS.grid_base_kg_per_kwh * scenario.grid_carbon_multiplier * (
        1 + 0.14 * np.exp(-0.5 * ((hour - 19) / 2.5) ** 2)
    )
    return pd.DataFrame(
        {
            "hour": hour,
            "load_multiplier": np.clip(load_multiplier, 0.55, 1.35),
            "pv_multiplier": pv_multiplier,
            "grid_carbon_kg_per_kwh": grid_carbon,
        }
    ).set_index("hour").round(5)


def sample_fault_scenarios(n: int = 30, seed: int = 20260822) -> list[DisasterScenario]:
    """Generate deterministic multi-fault scenarios for robustness tests."""

    if n < 1:
        raise ValueError("n must be positive")
    rng = np.random.default_rng(seed)
    choices = np.arange(1, 33)
    samples: list[DisasterScenario] = []
    for idx in range(n):
        count = int(rng.integers(2, 6))
        failed = tuple(sorted(int(x) for x in rng.choice(choices, count, replace=False)))
        repair = tuple(int(x) for x in rng.integers(3, 13, count))
        samples.append(
            DisasterScenario(
                name=f"蒙特卡洛-{idx + 1:02d}",
                description="用于恢复算法稳定性和敏感性验证的合成多故障场景。",
                failed_branch_ids=failed,
                repair_hours=repair,
                pv_derating=float(rng.uniform(0.20, 0.90)),
                grid_carbon_multiplier=float(rng.uniform(0.95, 1.22)),
                crew_distance_km=float(rng.uniform(15, 95)),
                ambient_temperature_c=float(rng.uniform(20, 44)),
            )
        )
    return samples
