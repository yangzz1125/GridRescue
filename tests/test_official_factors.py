from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from gridrescue.carbon import (
    DEFAULT_EMISSION_FACTORS,
    EmissionFactors,
    official_grid_factor_rows,
)
from gridrescue import mrv
from gridrescue.mrv_sensitivity import propagate_factor_uncertainty


def test_official_2023_rows_have_primary_source_provenance():
    rows = official_grid_factor_rows()
    by_geo = {row["geography"]: row for row in rows}
    assert {"全国", "华中区域", "湖北省"} == set(by_geo)
    assert np.isclose(by_geo["全国"]["value"], 0.5306)
    assert np.isclose(by_geo["华中区域"]["value"], 0.5271)
    assert np.isclose(by_geo["湖北省"]["value"], 0.4044)
    for row in rows:
        assert row["year"] == 2023
        assert row["unit"] == "kgCO2/kWh"
        assert row["source_class"] == "O"
        assert row["source_id"] == "MEE-2026-01-05-2023-electricity-factor"
        assert row["source_url"].startswith("https://www.mee.gov.cn/")
        assert "location-based" in row["applicability"]


def test_from_registry_selects_hubei_and_aliases():
    registry = mrv.default_factor_registry()
    factors = EmissionFactors.from_registry(registry, geography="Hubei", year=2023)
    assert np.isclose(factors.grid_base_kg_per_kwh, 0.4044)
    assert np.isclose(factors.curtailed_renewable_opportunity_kg_per_kwh, 0.4044)
    assert factors.grid_factor_id == "mee-elec-2023-hubei"
    assert factors.grid_geography == "湖北省"
    assert factors.grid_year == 2023
    assert factors.grid_source_class == "O"


def test_from_registry_accepts_csv_and_keeps_demo_defaults_unchanged(tmp_path: Path):
    path = tmp_path / "factor_registry.csv"
    static = pd.read_csv(
        Path(__file__).resolve().parents[1] / "data" / "factor_registry.csv",
        keep_default_na=False,
    )
    static.to_csv(path, index=False)
    factors = EmissionFactors.from_registry(path, geography="华中", year=2023)
    assert np.isclose(factors.grid_base_kg_per_kwh, 0.5271)
    # Existing callers that use the default object retain the frozen demo
    # values and therefore preserve historical bundle hashes.
    assert np.isclose(DEFAULT_EMISSION_FACTORS.grid_base_kg_per_kwh, 0.5366)
    assert np.isclose(DEFAULT_EMISSION_FACTORS.diesel_kg_per_kwh, 0.72)


def test_from_registry_reports_missing_or_ambiguous_factor():
    registry = mrv.default_factor_registry()
    with np.testing.assert_raises(ValueError):
        EmissionFactors.from_registry(registry, geography="不存在", year=2023)
    duplicate = pd.concat([registry, registry[registry["factor_id"] == "mee-elec-2023-hubei"]])
    with np.testing.assert_raises(ValueError):
        EmissionFactors.from_registry(duplicate, geography="湖北省", year=2023)


def test_official_factor_without_published_uncertainty_is_accepted_by_sensitivity():
    registry = mrv.default_factor_registry()
    inventory = pd.DataFrame(
        [{"strategy_id": "demo", "activity_value": 100.0, "factor_id": "mee-elec-2023-hubei"}]
    )
    draws, summaries = propagate_factor_uncertainty(inventory, registry, draws=8)
    assert len(draws) == 8
    assert len(summaries) == 1
    assert np.isclose(summaries[0].baseline_kgco2, 40.44)
    assert np.isclose(summaries[0].q05_kgco2, 40.44)
    assert np.isclose(summaries[0].q95_kgco2, 40.44)
