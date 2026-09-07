import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import gridrescue.mrv as mrv
from gridrescue.pipeline import run_pipeline


@pytest.fixture(scope="module")
def mrv_case(tmp_path_factory):
    project_root = Path(__file__).resolve().parents[1]
    result = run_pipeline("暴雨内涝")
    written = mrv.write_mrv_bundle(
        result,
        tmp_path_factory.mktemp("mrv") / "bundles",
        project_root=project_root,
    )
    return result, written


def _copy_bundle(mrv_case, tmp_path, name):
    _result, written = mrv_case
    target = tmp_path / name
    shutil.copytree(written["bundle"], target)
    return target


def test_factor_registry_record_hashes_are_canonical():
    registry = mrv.default_factor_registry()

    assert set(registry["activity"]) == {
        "grid_import",
        "diesel_generation",
        "crew_vehicle",
        "grid_import_national",
        "grid_import_central-china",
        "grid_import_hubei",
    }
    for row in registry.to_dict(orient="records"):
        assert row["record_hash"] == mrv._record_hash(row)
        assert row["record_hash"].startswith("sha256:")


def test_static_factor_registry_matches_runtime():
    path = Path(__file__).resolve().parents[1] / "data" / "factor_registry.csv"
    static = pd.read_csv(path, keep_default_na=False, dtype={"factor_version": str})
    static = mrv._canonicalize_factor_registry(static)
    runtime = mrv.default_factor_registry()

    pd.testing.assert_frame_equal(static, runtime, check_dtype=False)
    for row in static.to_dict(orient="records"):
        assert row["record_hash"] == mrv._record_hash(row)


def test_activity_and_inventory_equations_hold(mrv_case):
    _result, written = mrv_case
    bundle = written["bundle"]
    activities = pd.read_csv(bundle / "outputs" / "activity_energy_hourly.csv")
    inventory = pd.read_csv(bundle / "outputs" / "emission_inventory_hourly.csv")

    assert np.allclose(
        activities["energy_kwh"],
        activities["power_kw"] * activities["time_step_h"],
        atol=1e-9,
    )
    assert (activities[["power_kw", "energy_kwh"]].to_numpy(float) >= -1e-9).all()
    assert np.allclose(
        inventory["emission_value"],
        inventory["activity_value"] * inventory["factor_value"],
        atol=1e-9,
    )


def test_carbon_breakdown_reconciles_to_inventory(mrv_case):
    result, written = mrv_case
    inventory = pd.read_csv(
        written["bundle"] / "outputs" / "emission_inventory_hourly.csv"
    )
    reconciliation = pd.read_csv(
        written["bundle"] / "outputs" / "carbon_reconciliation.csv"
    ).set_index("strategy_id")

    for strategy, strategy_result in result.strategies.items():
        slug = mrv.STRATEGY_SLUGS[strategy]
        rows = inventory.loc[inventory["strategy_id"] == slug]
        carbon = strategy_result.carbon
        by_boundary = rows.groupby("boundary_module")["emission_value"].sum()

        assert np.isclose(by_boundary["grid_scope2_location"], carbon.grid_kg, atol=1e-6)
        assert np.isclose(by_boundary["diesel_scope1"], carbon.diesel_kg, atol=1e-6)
        assert np.isclose(by_boundary["crew_estimated"], carbon.crew_kg, atol=1e-6)
        assert np.isclose(rows["emission_value"].sum(), carbon.total_operational_kg, atol=1e-6)
        assert bool(reconciliation.loc[slug, "reconciled"])
        assert abs(float(reconciliation.loc[slug, "difference_kgCO2"])) <= 1e-5


def test_action_sequence_and_hash_chain_match_manifest(mrv_case):
    _result, written = mrv_case
    bundle = written["bundle"]
    actions = pd.read_csv(bundle / "outputs" / "actions.csv", keep_default_na=False)
    manifest = json.loads((bundle / "run_manifest.json").read_text(encoding="utf-8"))
    terminal_hashes = {
        row["strategy_id"]: row["action_ledger_terminal_hash"]
        for row in manifest["strategies"]
    }

    assert mrv._verify_action_chain(actions, written["run_id"]) == []
    for slug, group in actions.groupby("strategy_id"):
        ordered = group.sort_values("sequence_no").to_dict(orient="records")
        assert [int(row["sequence_no"]) for row in ordered] == list(
            range(1, len(ordered) + 1)
        )
        expected_prev = f"GENESIS:{written['run_id']}:{slug}"
        for row in ordered:
            assert row["prev_hash"] == expected_prev
            assert row["record_hash"] == mrv._record_hash(row)
            expected_prev = row["record_hash"]
        assert terminal_hashes[slug] == expected_prev


def test_action_ledger_tracks_safe_tie_open_transitions(mrv_case):
    _result, written = mrv_case
    actions = pd.read_csv(
        written["bundle"] / "outputs" / "actions.csv",
        keep_default_na=False,
    )

    for slug in ("eens", "carbon_resilient"):
        opened = actions.loc[
            (actions["strategy_id"] == slug) & (actions["action_type"] == "open_tie"),
            ["hour", "target_id"],
        ]
        assert [tuple(map(int, row)) for row in opened.to_numpy()] == [
            (7, 33),
            (13, 37),
            (23, 34),
        ]
        topology = pd.read_csv(
            written["bundle"] / "outputs" / f"topology_state_{slug}.csv",
            keep_default_na=False,
        )
        assert topology.iloc[-1]["closed_tie_ids_json"] == "[]"


def test_written_bundle_verifies_normally(mrv_case):
    _result, written = mrv_case

    verification = mrv.verify_mrv_bundle(written["bundle"])

    assert written["verification"]["verified"] is True
    assert verification["verified"] is True
    assert verification["errors"] == []
    assert verification["checked_files"] >= 11


def test_tampered_dispatch_activity_fails_verification(mrv_case, tmp_path):
    bundle = _copy_bundle(mrv_case, tmp_path, "tampered-activity")
    path = bundle / "outputs" / "activity_energy_hourly.csv"
    activities = pd.read_csv(path)
    activities.loc[0, "power_kw"] = float(activities.loc[0, "power_kw"]) + 1.0
    activities.to_csv(path, index=False)

    verification = mrv.verify_mrv_bundle(bundle)

    assert verification["verified"] is False
    assert any("activity_energy_hourly.csv" in error for error in verification["errors"])
    assert "activity power/energy equation failed" in verification["errors"]


def test_tampered_action_chain_fails_verification(mrv_case, tmp_path):
    bundle = _copy_bundle(mrv_case, tmp_path, "tampered-actions")
    path = bundle / "outputs" / "actions.csv"
    actions = pd.read_csv(path, keep_default_na=False)
    actions.loc[1, "prev_hash"] = "sha256:" + "0" * 64
    actions.to_csv(path, index=False)

    verification = mrv.verify_mrv_bundle(bundle)

    assert verification["verified"] is False
    assert any("actions.csv" in error for error in verification["errors"])
    assert any("action prev_hash mismatch" in error for error in verification["errors"])
    assert any("action record_hash mismatch" in error for error in verification["errors"])


def test_rechained_actions_still_fail_terminal_hash_check(mrv_case, tmp_path):
    bundle = _copy_bundle(mrv_case, tmp_path, "rechained-actions")
    path = bundle / "outputs" / "actions.csv"
    actions = pd.read_csv(path, keep_default_na=False)
    slug = "eens"
    group_index = actions.index[actions["strategy_id"] == slug]
    actions.loc[group_index[0], "display_text"] = "tampered-but-rechained"
    previous = f"GENESIS:{json.loads((bundle / 'run_manifest.json').read_text(encoding='utf-8'))['run_id']}:{slug}"
    for index in group_index:
        row = actions.loc[index].to_dict()
        actions.loc[index, "prev_hash"] = previous
        row["prev_hash"] = previous
        actions.loc[index, "record_hash"] = mrv._record_hash(row)
        previous = str(actions.loc[index, "record_hash"])
    actions.to_csv(path, index=False)

    verification = mrv.verify_mrv_bundle(bundle)

    assert verification["verified"] is False
    assert any("manifest action terminal hash mismatch" in error for error in verification["errors"])
    assert any("seal action terminal hash mismatch" in error for error in verification["errors"])


def test_claim_gate_marks_current_candidate_as_not_same_service(mrv_case):
    _result, written = mrv_case
    gates = json.loads(
        (written["bundle"] / "outputs" / "claim_gates.json").read_text(
            encoding="utf-8"
        )
    )
    comparison = gates["comparison"]

    assert all(gate["inventory_eligible"] for gate in gates["strategies"].values())
    assert comparison["critical_service_pass"] is True
    assert comparison["normal_budget_pass"] is True
    assert comparison["controlled_tradeoff_pass"] is True
    assert comparison["same_service_pass"] is False
    assert comparison["same_service_reduction_claim_allowed"] is False
    assert comparison["claim_status"] == "controlled_service_budget_inventory_difference"


def test_missing_indexed_file_fails_verification(mrv_case, tmp_path):
    bundle = _copy_bundle(mrv_case, tmp_path, "missing-input")
    missing = bundle / "inputs" / "scenario.json"
    missing.unlink()

    verification = mrv.verify_mrv_bundle(bundle)

    assert verification["verified"] is False
    assert "missing file: inputs/scenario.json" in verification["errors"]


def test_missing_manifest_returns_structured_failure(mrv_case, tmp_path):
    bundle = _copy_bundle(mrv_case, tmp_path, "missing-manifest")
    (bundle / "run_manifest.json").unlink()

    verification = mrv.verify_mrv_bundle(bundle)

    assert verification["verified"] is False
    assert verification["run_id"] == "unknown"
    assert "missing required file: run_manifest.json" in verification["errors"]


def test_non_hourly_activity_export_fails_fast(mrv_case):
    result, written = mrv_case

    with pytest.raises(ValueError, match="supports only time_step_h=1.0"):
        mrv._activity_rows(written["run_id"], result, time_step_h=0.5)
