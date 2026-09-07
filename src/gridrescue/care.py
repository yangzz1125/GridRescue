from __future__ import annotations

import json
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .dispatch import ServiceTaskRequirement
from .powerflow import FlowValidation
from .restoration import StrategyResult


@dataclass(frozen=True)
class CareTask:
    task_id: str
    name: str
    node_id: int
    tier: int
    min_kw: float
    start_hour: int
    end_hour: int
    deadline_hour: int
    min_duration_h: int
    voltage_min_pu: float = 0.95
    voltage_max_pu: float = 1.05
    dependencies: tuple[str, ...] = ()
    data_class: str = "E_synthetic_task_template"


def default_care_tasks() -> tuple[CareTask, ...]:
    """Return a transparent synthetic life-line task template.

    The values are scenario-design assumptions for competition validation,
    not clinical operating standards or measurements from a real hospital.
    """

    return (
        CareTask(
            "ICU_CONTINUITY",
            "ICU与急诊生命支持",
            node_id=2,
            tier=1,
            min_kw=28.0,
            start_hour=0,
            end_hour=23,
            deadline_hour=0,
            min_duration_h=24,
            voltage_min_pu=0.97,
        ),
        CareTask(
            "EMERGENCY_SURGERY",
            "应急手术窗口",
            node_id=17,
            tier=1,
            min_kw=25.0,
            start_hour=0,
            end_hour=5,
            deadline_hour=0,
            min_duration_h=6,
            voltage_min_pu=0.97,
        ),
        CareTask(
            "MEDICINE_COLD_CHAIN",
            "药品与血液冷链",
            node_id=17,
            tier=2,
            min_kw=12.0,
            start_hour=0,
            end_hour=23,
            deadline_hour=0,
            min_duration_h=24,
        ),
        CareTask(
            "EMERGENCY_COMMUNICATION",
            "应急通信与调度",
            node_id=5,
            tier=2,
            min_kw=20.0,
            start_hour=0,
            end_hour=23,
            deadline_hour=0,
            min_duration_h=24,
        ),
    )


def care_task_definition_hash(tasks: tuple[CareTask, ...]) -> str:
    payload = json.dumps(
        [asdict(task) for task in tasks],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_care_tasks(tasks: tuple[CareTask, ...]) -> tuple[CareTask, ...]:
    by_id: dict[str, CareTask] = {}
    for task in tasks:
        if not task.task_id.strip():
            raise ValueError("care task_id must be non-empty")
        if task.task_id in by_id:
            raise ValueError(f"duplicate care task_id: {task.task_id}")
        if task.tier < 1:
            raise ValueError(f"task {task.task_id!r} tier must be positive")
        if task.min_kw <= 0:
            raise ValueError(f"task {task.task_id!r} min_kw must be positive")
        if not 0 <= task.start_hour <= task.end_hour <= 23:
            raise ValueError(f"task {task.task_id!r} has invalid service window")
        if not task.start_hour <= task.deadline_hour <= task.end_hour:
            raise ValueError(f"task {task.task_id!r} deadline must be inside its window")
        window_h = task.end_hour - task.start_hour + 1
        if not 1 <= task.min_duration_h <= window_h:
            raise ValueError(f"task {task.task_id!r} has invalid min_duration_h")
        if not 0 < task.voltage_min_pu <= task.voltage_max_pu:
            raise ValueError(f"task {task.task_id!r} has invalid voltage band")
        by_id[task.task_id] = task

    for task in tasks:
        unknown = set(task.dependencies).difference(by_id)
        if unknown:
            raise ValueError(
                f"task {task.task_id!r} references unknown dependencies: {sorted(unknown)}"
            )
        if task.task_id in task.dependencies:
            raise ValueError(f"task {task.task_id!r} cannot depend on itself")

    ordered: list[CareTask] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            raise ValueError(f"care task dependency cycle includes {task_id!r}")
        visiting.add(task_id)
        for dependency in by_id[task_id].dependencies:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)
        ordered.append(by_id[task_id])

    for task in tasks:
        visit(task.task_id)
    return tuple(ordered)


def care_task_requirements(tasks: tuple[CareTask, ...]) -> tuple[ServiceTaskRequirement, ...]:
    ordered = validate_care_tasks(tasks)
    return tuple(
        ServiceTaskRequirement(
            task_id=task.task_id,
            node_id=task.node_id,
            start_hour=task.start_hour,
            end_hour=task.end_hour,
            min_kw=task.min_kw,
        )
        for task in ordered
    )


def _longest_true_run(values: list[bool]) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _first_qualifying_block(hours: list[int], values: list[bool], duration: int) -> tuple[int, int]:
    start_index: int | None = None
    for index, value in enumerate(values + [False]):
        if value and start_index is None:
            start_index = index
        elif not value and start_index is not None:
            if index - start_index >= duration:
                start_hour = hours[start_index]
                return start_hour, start_hour + duration - 1
            start_index = None
    return -1, -1


def evaluate_care_tasks(
    tasks: tuple[CareTask, ...],
    strategy_result: StrategyResult,
    validation: FlowValidation,
    *,
    tolerance_kw: float = 1e-3,
) -> pd.DataFrame:
    node_frame = strategy_result.dispatch.node_frame
    if node_frame is None:
        raise ValueError("care-task evaluation requires node-level dispatch evidence")
    ordered_tasks = validate_care_tasks(tasks)
    definition_hash = care_task_definition_hash(tasks)
    rows: list[dict[str, object]] = []
    completed: dict[str, bool] = {}
    completion_hours: dict[str, int] = {}
    for task in ordered_tasks:
        hours = list(range(task.start_hour, task.end_hour + 1))
        coincident_requirements = {
            hour: sum(
                other.min_kw
                for other in ordered_tasks
                if other.node_id == task.node_id
                and other.start_hour <= hour <= other.end_hour
            )
            for hour in hours
        }
        dispatch = node_frame[
            (node_frame["node_id"] == task.node_id)
            & node_frame["hour"].isin(hours)
        ][["hour", "served_critical_kw"]]
        flow = validation.nodes[
            (validation.nodes["node_id"] == task.node_id)
            & validation.nodes["hour"].isin(hours)
        ][["hour", "voltage_pu", "energized"]]
        evidence = pd.DataFrame({"hour": hours}).merge(
            dispatch, on="hour", how="left", indicator="dispatch_merge"
        ).merge(flow, on="hour", how="left", indicator="flow_merge")
        evidence["dispatch_missing"] = evidence["dispatch_merge"].ne("both")
        evidence["flow_missing"] = evidence["flow_merge"].ne("both")
        evidence["served_critical_kw"] = evidence["served_critical_kw"].fillna(0.0)
        evidence["voltage_pu"] = evidence["voltage_pu"].fillna(0.0)
        evidence["energized"] = evidence["energized"].fillna(False).astype(bool)
        evidence["coincident_required_kw"] = evidence["hour"].map(coincident_requirements)
        # Tasks sharing a node must not double-count the same critical-load
        # service.  Every active task is qualified only when the aggregate
        # coincident requirement is covered at that node and hour.
        evidence["power_pass"] = (
            evidence["served_critical_kw"] + tolerance_kw
            >= evidence["coincident_required_kw"]
        )
        evidence["voltage_pass"] = (
            evidence["energized"]
            & (evidence["voltage_pu"] >= task.voltage_min_pu - 1e-6)
            & (evidence["voltage_pu"] <= task.voltage_max_pu + 1e-6)
        )
        evidence["hour_pass"] = evidence["power_pass"] & evidence["voltage_pass"]
        pass_values = evidence["hour_pass"].tolist()
        first_pass, completion_hour = _first_qualifying_block(
            hours, pass_values, task.min_duration_h
        )
        longest = _longest_true_run(pass_values)
        dependency_ready_hour = max(
            (completion_hours.get(dependency, -1) for dependency in task.dependencies),
            default=-1,
        )
        dependency_pass = all(completed.get(dependency, False) for dependency in task.dependencies)
        if task.dependencies and first_pass >= 0:
            dependency_pass = dependency_pass and first_pass >= dependency_ready_hour
        deadline_pass = first_pass >= 0 and first_pass <= task.deadline_hour
        duration_pass = longest >= task.min_duration_h
        window_pass = bool(evidence["hour_pass"].all())
        task_complete = bool(dependency_pass and deadline_pass and duration_pass)
        reasons: list[str] = []
        if not dependency_pass:
            reasons.append("DEPENDENCY")
        if not deadline_pass:
            reasons.append("DEADLINE")
        if not duration_pass:
            reasons.append("DURATION")
        if not evidence["power_pass"].all():
            reasons.append("POWER")
        if not evidence["voltage_pass"].all():
            reasons.append("VOLTAGE")
        if evidence["dispatch_missing"].any():
            reasons.append("DISPATCH_MISSING")
        if evidence["flow_missing"].any():
            reasons.append("FLOW_MISSING")
        completed[task.task_id] = task_complete
        completion_hours[task.task_id] = completion_hour if task_complete else -1
        rows.append(
            {
                **asdict(task),
                "definition_sha256": definition_hash,
                "strategy": strategy_result.plan.strategy,
                "required_energy_kwh": task.min_kw * len(hours),
                "credited_energy_kwh": float(
                    np.where(evidence["power_pass"], task.min_kw, 0.0).sum()
                ),
                "maximum_coincident_required_kw": float(
                    evidence["coincident_required_kw"].max()
                ),
                "minimum_served_kw": float(evidence["served_critical_kw"].min()),
                "minimum_voltage_pu": float(evidence["voltage_pu"].min()),
                "first_qualified_hour": first_pass,
                "completion_hour": completion_hour,
                "dependency_ready_hour": dependency_ready_hour,
                "longest_qualified_duration_h": longest,
                "dependency_pass": dependency_pass,
                "deadline_pass": deadline_pass,
                "duration_pass": duration_pass,
                "window_pass": window_pass,
                "task_complete": task_complete,
                "failure_reason_codes": json.dumps(reasons),
            }
        )
    return pd.DataFrame(rows).round(6)


def write_care_tasks(
    tasks: tuple[CareTask, ...],
    evaluation: pd.DataFrame,
    output_dir: str | Path,
    slug: str,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    definition_path = output / "care_task_definitions.json"
    evaluation_path = output / f"care_task_evaluation_{slug}.csv"
    summary_path = output / f"care_task_summary_{slug}.json"
    ordered = validate_care_tasks(tasks)
    definition_hash = care_task_definition_hash(tasks)
    definition_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "definition_sha256": definition_hash,
                "tasks": [asdict(task) for task in ordered],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    evaluation.to_csv(evaluation_path, index=False)
    summary = {
        "schema_version": 1,
        "definition_sha256": definition_hash,
        "slug": slug,
        "task_count": len(evaluation),
        "completed_count": int(evaluation["task_complete"].sum()) if not evaluation.empty else 0,
        "tier1_completed": int(
            evaluation.loc[evaluation["tier"] == 1, "task_complete"].sum()
        )
        if not evaluation.empty
        else 0,
        "failed_task_ids": (
            evaluation.loc[~evaluation["task_complete"].astype(bool), "task_id"].tolist()
            if not evaluation.empty
            else []
        ),
        "data_boundary": (
            "CareTask values are an E-class synthetic scenario template; they are not real "
            "hospital measurements or clinical standards."
        ),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"definitions": definition_path, "evaluation": evaluation_path, "summary": summary_path}
