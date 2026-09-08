from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from .carbon import CarbonBreakdown


@dataclass(frozen=True)
class RecoveryMetrics:
    eens_kwh: float
    critical_eens_kwh: float
    critical_recovery_pct: float
    restoration_time_h: int
    peak_unserved_kw: float
    diesel_energy_kwh: float
    renewable_consumed_kwh: float
    renewable_curtailment_kwh: float
    switch_operations: int
    total_carbon_kg: float
    first_full_supply_time_h: int = 24
    restoration_completed: bool = False


def calculate_metrics(
    dispatch: pd.DataFrame,
    carbon: CarbonBreakdown,
    switch_operations: int,
) -> RecoveryMetrics:
    if dispatch.empty or list(dispatch.index) != list(range(len(dispatch))):
        raise ValueError("metrics require non-empty consecutive hourly rows starting at 0")
    critical_total = float(dispatch["critical_load_kw"].sum())
    critical_served = float(dispatch["served_critical_kw"].sum())
    total_unserved = dispatch["unserved_critical_kw"] + dispatch["unserved_normal_kw"]
    fully_restored = total_unserved <= 1e-3
    first_full_supply = int(fully_restored.idxmax()) if fully_restored.any() else len(dispatch)
    # A temporary zero-shortfall hour is not recovery if an outage returns later.
    sustained = fully_restored.iloc[::-1].cummin().iloc[::-1]
    restoration_time = int(sustained.idxmax()) if sustained.any() else len(dispatch)
    renewable_consumed = dispatch["pv_available_kw"] - dispatch["renewable_curtailment_kw"]
    return RecoveryMetrics(
        eens_kwh=float(total_unserved.sum()),
        critical_eens_kwh=float(dispatch["unserved_critical_kw"].sum()),
        critical_recovery_pct=float(100 * critical_served / critical_total if critical_total else 100),
        restoration_time_h=restoration_time,
        peak_unserved_kw=float(total_unserved.max()),
        diesel_energy_kwh=float(dispatch["diesel_generation_kw"].sum()),
        renewable_consumed_kwh=float(renewable_consumed.sum()),
        renewable_curtailment_kwh=float(dispatch["renewable_curtailment_kw"].sum()),
        switch_operations=int(switch_operations),
        total_carbon_kg=float(carbon.total_operational_kg),
        first_full_supply_time_h=first_full_supply,
        restoration_completed=bool(sustained.any()),
    )


def comparison_table(results: dict[str, RecoveryMetrics]) -> pd.DataFrame:
    rows = []
    for strategy, metrics in results.items():
        row = {"strategy": strategy, **asdict(metrics)}
        rows.append(row)
    return pd.DataFrame(rows).round(4)

