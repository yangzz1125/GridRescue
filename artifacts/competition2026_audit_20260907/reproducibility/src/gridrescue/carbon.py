from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EmissionFactors:
    grid_base_kg_per_kwh: float = 0.5366
    diesel_kg_per_kwh: float = 0.72
    crew_vehicle_kg_per_km: float = 0.23
    curtailed_renewable_opportunity_kg_per_kwh: float = 0.5366


DEFAULT_EMISSION_FACTORS = EmissionFactors()


@dataclass(frozen=True)
class CarbonBreakdown:
    grid_kg: float
    diesel_kg: float
    crew_kg: float
    total_operational_kg: float
    curtailed_renewable_kwh: float
    avoided_grid_equivalent_kg: float


def calculate_carbon(
    dispatch: pd.DataFrame,
    crew_distance_km: float,
    factors: EmissionFactors = DEFAULT_EMISSION_FACTORS,
) -> CarbonBreakdown:
    required = {
        "grid_import_kw",
        "diesel_generation_kw",
        "renewable_curtailment_kw",
        "grid_carbon_kg_per_kwh",
    }
    missing = required.difference(dispatch.columns)
    if missing:
        raise ValueError(f"dispatch frame missing carbon columns: {sorted(missing)}")
    grid_kg = float((dispatch["grid_import_kw"] * dispatch["grid_carbon_kg_per_kwh"]).sum())
    diesel_kg = float(dispatch["diesel_generation_kw"].sum() * factors.diesel_kg_per_kwh)
    crew_kg = float(crew_distance_km * factors.crew_vehicle_kg_per_km)
    curtailed = float(dispatch["renewable_curtailment_kw"].sum())
    return CarbonBreakdown(
        grid_kg=grid_kg,
        diesel_kg=diesel_kg,
        crew_kg=crew_kg,
        total_operational_kg=grid_kg + diesel_kg + crew_kg,
        curtailed_renewable_kwh=curtailed,
        avoided_grid_equivalent_kg=curtailed * factors.curtailed_renewable_opportunity_kg_per_kwh,
    )
