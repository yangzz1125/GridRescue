from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class EmissionFactors:
    grid_base_kg_per_kwh: float = 0.5366
    diesel_kg_per_kwh: float = 0.72
    crew_vehicle_kg_per_km: float = 0.23
    curtailed_renewable_opportunity_kg_per_kwh: float = 0.5366
    # Provenance is optional so existing positional construction and the
    # frozen synthetic-demo defaults remain backward compatible.
    grid_factor_id: str | None = None
    grid_geography: str | None = None
    grid_year: int | None = None
    grid_source_class: str | None = None
    grid_source_id: str | None = None

    @classmethod
    def from_registry(
        cls,
        registry: str | Path | pd.DataFrame,
        *,
        geography: str = "湖北省",
        year: int = 2023,
        factor_id: str | None = None,
        diesel_kg_per_kwh: float | None = None,
        crew_vehicle_kg_per_km: float | None = None,
    ) -> "EmissionFactors":
        """Load an official grid factor while preserving demo defaults.

        ``registry`` may be a CSV path or an already loaded DataFrame.  The
        registry intentionally keeps the historical synthetic rows used by
        frozen bundles; this method selects an official ``grid_import_*`` row
        explicitly by geography/year (or ``factor_id``), so old callers that
        use :data:`DEFAULT_EMISSION_FACTORS` produce identical results.
        """
        frame = _read_factor_registry(registry)
        required = {"factor_id", "activity", "value", "unit", "geography", "year"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"factor registry missing columns: {sorted(missing)}")
        candidates = frame[frame["activity"].astype(str).str.startswith("grid_import")].copy()
        if factor_id is not None:
            candidates = candidates[candidates["factor_id"].astype(str) == factor_id]
        else:
            candidates = candidates[
                (candidates["geography"].map(_geography_matches).map(lambda ok: ok(geography)))
                & (pd.to_numeric(candidates["year"], errors="coerce") == int(year))
            ]
        if len(candidates) != 1:
            ids = candidates.get("factor_id", pd.Series(dtype=str)).astype(str).tolist()
            raise ValueError(
                f"expected exactly one grid factor for geography={geography!r}, year={year}, "
                f"factor_id={factor_id!r}; candidates={ids}"
            )
        row = candidates.iloc[0]
        unit = str(row.get("unit", ""))
        if unit not in {"kgCO2/kWh", "kgCO2e/kWh", "tCO2/MWh", "tCO2e/MWh"}:
            raise ValueError(f"unsupported grid factor unit: {unit!r}")
        value = float(row["value"])
        # tCO2/MWh and kgCO2/kWh are numerically identical.
        if unit.startswith("tCO2"):
            value = value
        return cls(
            grid_base_kg_per_kwh=value,
            diesel_kg_per_kwh=cls().diesel_kg_per_kwh if diesel_kg_per_kwh is None else float(diesel_kg_per_kwh),
            crew_vehicle_kg_per_km=cls().crew_vehicle_kg_per_km
            if crew_vehicle_kg_per_km is None
            else float(crew_vehicle_kg_per_km),
            curtailed_renewable_opportunity_kg_per_kwh=value,
            grid_factor_id=str(row.get("factor_id", "")),
            grid_geography=str(row.get("geography", "")),
            grid_year=int(row.get("year")),
            grid_source_class=str(row.get("source_class", "")),
            grid_source_id=str(row.get("source_id", "")),
        )


def _read_factor_registry(registry: str | Path | pd.DataFrame) -> pd.DataFrame:
    if isinstance(registry, pd.DataFrame):
        return registry.copy()
    return pd.read_csv(Path(registry), keep_default_na=False)


def _geography_matches(value: Any):
    normalized = str(value).strip().lower()
    aliases = {
        "全国": {"全国", "中国", "national", "china", "china-national"},
        "华中": {"华中", "华中区域", "central china", "central-china"},
        "湖北": {"湖北", "湖北省", "hubei", "hubei province"},
    }
    for names in aliases.values():
        if normalized in {name.lower() for name in names}:
            return lambda requested, names=names: str(requested).strip().lower() in {
                name.lower() for name in names
            }
    return lambda requested: str(requested).strip().lower() == normalized


def official_grid_factor_rows() -> list[dict[str, Any]]:
    """Return primary-source 2023 electricity-factor rows for the registry.

    Values are converted from the Ministry of Ecology and Environment's
    published tCO2/MWh table to the registry's numerically equivalent
    kgCO2/kWh unit.  Scope is annual, location-based average electricity;
    these rows do not replace the frozen synthetic demo defaults.
    """
    source = {
        "source_class": "O",
        "source_id": "MEE-2026-01-05-2023-electricity-factor",
        "source_title": "生态环境部关于发布2023年度电力平均二氧化碳排放因子的公告",
        "source_url": "https://www.mee.gov.cn/xxgk2018/xxgk/xxgk01/202512/t20251231_1139517.html",
        "source_file_sha256": "",
        "year": 2023,
        "temporal_resolution": "annual",
        "method": "MEE published average electricity CO2 emission factor; location-based",
        "gas_basis": "CO2",
        "unit": "kgCO2/kWh",
        "uncertainty_pct": "",
        "approval_status": "official-source-reference",
    }
    values = [
        ("mee-elec-2023-national", "全国", 0.5306),
        ("mee-elec-2023-central-china", "华中区域", 0.5271),
        ("mee-elec-2023-hubei", "湖北省", 0.4044),
    ]
    rows = []
    for factor_id, geography, value in values:
        rows.append(
            {
                **source,
                "factor_id": factor_id,
                "factor_version": "2023.1",
                "activity": f"grid_import_{factor_id.removeprefix('mee-elec-2023-')}",
                "value": value,
                "geography": geography,
                "applicability": "2023 annual location-based average electricity factor; replace demo grid factor after scope review",
            }
        )
    return rows


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
