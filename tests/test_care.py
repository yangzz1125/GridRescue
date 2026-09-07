from dataclasses import replace

import pytest

from gridrescue.care import (
    CareTask,
    care_task_requirements,
    default_care_tasks,
    evaluate_care_tasks,
    load_hospital_load_profiles,
    write_care_tasks,
)
from gridrescue.pipeline import run_pipeline


@pytest.fixture(scope="module")
def flood_pipeline():
    return run_pipeline("暴雨内涝")


def test_default_care_tasks_complete_for_every_baseline_strategy(flood_pipeline):
    tasks = default_care_tasks()
    assert {task.data_class for task in tasks} == {"E_synthetic_task_template"}
    for strategy, result in flood_pipeline.strategies.items():
        evaluation = evaluate_care_tasks(
            tasks,
            result,
            flood_pipeline.validations[strategy],
        )
        assert len(evaluation) == 4
        assert evaluation["task_complete"].all()
        assert evaluation["dependency_pass"].all()
        assert evaluation["deadline_pass"].all()
        assert evaluation["duration_pass"].all()
        assert evaluation["minimum_voltage_pu"].min() >= 0.97


def test_hospital_load_profile_csv_is_traceable_and_parameterized():
    profiles = load_hospital_load_profiles("data/hospital_load_profiles.csv")
    assert len(profiles) == 4
    assert {task.data_class for task in profiles} == {"E_synthetic_engineering_prior"}
    assert all(task.source_id.startswith("PUB-") for task in profiles)
    assert all(task.source_url.startswith("https://") for task in profiles)
    assert all(task.assumption for task in profiles)
    assert sum(task.min_kw for task in profiles if task.node_id == 17) == 37.0


def test_hospital_load_profile_loader_rejects_missing_traceability(tmp_path):
    path = tmp_path / "bad_profiles.csv"
    path.write_text("task_id,name,min_kw\nX,x,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_hospital_load_profiles(path)


def test_overlapping_tasks_do_not_double_count_node_service(flood_pipeline):
    strategy = "最小失供恢复"
    original = flood_pipeline.strategies[strategy]
    node_frame = original.dispatch.node_frame.copy()
    mask = (node_frame["node_id"] == 17) & node_frame["hour"].between(0, 5)
    # 30 kW exceeds each individual 25/12 kW task, but does not cover their
    # 37 kW coincident additive requirement.
    node_frame.loc[mask, "served_critical_kw"] = 30.0
    modified = replace(original, dispatch=replace(original.dispatch, node_frame=node_frame))
    evaluation = evaluate_care_tasks(
        default_care_tasks(),
        modified,
        flood_pipeline.validations[strategy],
    )

    affected = evaluation[evaluation["node_id"] == 17]
    assert not affected["task_complete"].any()
    assert (affected["maximum_coincident_required_kw"] == 37.0).all()
    assert affected["failure_reason_codes"].str.contains("POWER").all()


def test_care_task_power_window_and_export_contract(flood_pipeline, tmp_path):
    strategy = "最小失供恢复"
    tasks = default_care_tasks()
    requirements = care_task_requirements(tasks)
    assert len(requirements) == 4
    assert sum(
        requirement.min_kw
        for requirement in requirements
        if requirement.node_id == 17 and requirement.start_hour == 0
    ) == 37.0

    evaluation = evaluate_care_tasks(
        tasks,
        flood_pipeline.strategies[strategy],
        flood_pipeline.validations[strategy],
    )
    paths = write_care_tasks(tasks, evaluation, tmp_path, "eens")
    assert set(paths) == {"definitions", "evaluation", "summary"}
    assert all(path.exists() for path in paths.values())


def test_task_voltage_gate_is_separate_from_grid_feasibility(flood_pipeline):
    strategy = "最小失供恢复"
    validation = flood_pipeline.validations[strategy]
    nodes = validation.nodes.copy()
    nodes.loc[(nodes["node_id"] == 2) & (nodes["hour"] == 0), "voltage_pu"] = 0.96
    modified_validation = replace(validation, nodes=nodes)
    evaluation = evaluate_care_tasks(
        default_care_tasks(),
        flood_pipeline.strategies[strategy],
        modified_validation,
    )

    icu = evaluation.set_index("task_id").loc["ICU_CONTINUITY"]
    assert not bool(icu["task_complete"])
    assert "VOLTAGE" in icu["failure_reason_codes"]
    assert flood_pipeline.validations[strategy].hourly["is_feasible"].all()


@pytest.mark.parametrize(
    "tasks, message",
    [
        (
            (
                CareTask("DUP", "a", 2, 1, 1.0, 0, 0, 0, 1),
                CareTask("DUP", "b", 2, 1, 1.0, 0, 0, 0, 1),
            ),
            "duplicate",
        ),
        ((CareTask("BAD", "bad", 2, 1, -1.0, 0, 0, 0, 1),), "min_kw"),
        (
            (CareTask("UNKNOWN", "bad dependency", 2, 1, 1.0, 0, 0, 0, 1, dependencies=("X",)),),
            "unknown dependencies",
        ),
        (
            (
                CareTask("A", "a", 2, 1, 1.0, 0, 0, 0, 1, dependencies=("B",)),
                CareTask("B", "b", 2, 1, 1.0, 0, 0, 0, 1, dependencies=("A",)),
            ),
            "cycle",
        ),
    ],
)
def test_invalid_care_task_definitions_fail_fast(tasks, message):
    with pytest.raises(ValueError, match=message):
        care_task_requirements(tasks)
