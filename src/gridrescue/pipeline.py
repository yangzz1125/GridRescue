from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .dispatch import DispatchObjective, ServiceContract
from .metrics import comparison_table
from .network import GridModel, build_ieee33
from .powerflow import FlowValidation, validate_dispatch
from .restoration import STRATEGIES, StrategyResult, simulate_strategy
from .scenarios import DisasterScenario, get_scenario


@dataclass(frozen=True)
class PipelineResult:
    model: GridModel
    scenario: DisasterScenario
    strategies: dict[str, StrategyResult]
    validations: dict[str, FlowValidation]
    comparison: pd.DataFrame
    feedbacks: dict[str, PhysicalFeedback]


@dataclass(frozen=True)
class PhysicalFeedback:
    node_loss_kw: pd.Series
    node_q_loss_kvar: pd.Series
    component_served_caps_kw: dict[tuple[int, str], float]
    converged: bool
    iterations: int
    max_residual_kw: float


def _simulate_with_loss_feedback(
    model: GridModel,
    scenario: DisasterScenario,
    strategy: str,
    *,
    max_iterations: int = 8,
    tolerance_kw: float = 0.10,
    critical_unserved_limit_kwh: float | None = None,
    normal_unserved_limit_kwh: float | None = None,
    initial_feedback: PhysicalFeedback | None = None,
    update_component_caps: bool = True,
    service_contract: ServiceContract | None = None,
    dispatch_objective: DispatchObjective | None = None,
    strict_contract: bool = False,
) -> tuple[StrategyResult, FlowValidation, PhysicalFeedback]:
    loss_index = pd.MultiIndex.from_product([range(24), model.nodes.index], names=["hour", "node_id"])
    node_loss = (
        initial_feedback.node_loss_kw.reindex(loss_index, fill_value=0.0).copy()
        if initial_feedback is not None
        else pd.Series(0.0, index=loss_index, dtype=float)
    )
    node_q_loss = (
        initial_feedback.node_q_loss_kvar.reindex(loss_index, fill_value=0.0).copy()
        if initial_feedback is not None
        else pd.Series(0.0, index=loss_index, dtype=float)
    )
    component_caps: dict[tuple[int, str], float] = (
        dict(initial_feedback.component_served_caps_kw) if initial_feedback is not None else {}
    )
    effective_normal_limit = normal_unserved_limit_kwh
    result: StrategyResult | None = None
    validation: FlowValidation | None = None
    converged = False
    final_residual = float("inf")
    iterations = 0
    for iteration in range(1, max_iterations + 1):
        iterations = iteration
        try:
            result = simulate_strategy(
                model,
                scenario,
                strategy,
                node_loss_kw=node_loss,
                node_q_loss_kvar=node_q_loss,
                component_served_caps_kw=component_caps,
                critical_unserved_limit_kwh=critical_unserved_limit_kwh,
                normal_unserved_limit_kwh=effective_normal_limit,
                service_contract=service_contract,
                dispatch_objective=dispatch_objective,
            )
        except RuntimeError:
            if effective_normal_limit is not None and not strict_contract:
                # Preserve the critical-service fairness lock, but release the
                # optional normal-load budget when physical caps require it.
                effective_normal_limit = None
                continue
            raise
        validation = validate_dispatch(model, scenario, result.plan, result.dispatch)
        updated_loss = pd.Series(0.0, index=loss_index, dtype=float)
        updated_q_loss = pd.Series(0.0, index=loss_index, dtype=float)
        for row in validation.components.itertuples():
            if int(row.slack_node) >= 0:
                updated_loss.loc[(int(row.hour), int(row.slack_node))] = max(float(row.p_loss_kw), 0.0)
                updated_q_loss.loc[(int(row.hour), int(row.slack_node))] = max(float(row.q_loss_kvar), 0.0)

        caps_changed = False
        if update_component_caps and result.dispatch.node_frame is not None:
            served = (
                result.dispatch.node_frame.groupby(["hour", "component_key"])["served_load_kw"]
                .sum()
                .to_dict()
            )
            for row in validation.components.itertuples():
                scale = 1.0
                if float(row.max_loading_pct) > 100.0:
                    scale = min(scale, 0.99 * 100.0 / float(row.max_loading_pct))
                if 0.0 < float(row.min_voltage_pu) < 0.95:
                    denominator = max(1.05 - float(row.min_voltage_pu), 1e-6) if bool(row.is_root_component) else max(1.0 - float(row.min_voltage_pu), 1e-6)
                    numerator = 0.10 if bool(row.is_root_component) else 0.05
                    scale = min(scale, 0.99 * numerator / denominator)
                if scale < 0.999:
                    key = (int(row.hour), str(row.component_key))
                    proposed = max(float(served.get(key, 0.0)) * max(scale, 0.0), 0.0)
                    previous = component_caps.get(key, float("inf"))
                    if proposed + tolerance_kw < previous:
                        component_caps[key] = proposed
                        caps_changed = True

        loss_delta = float((updated_loss - node_loss).abs().max())
        q_loss_delta = float((updated_q_loss - node_q_loss).abs().max())
        final_residual = max(loss_delta, q_loss_delta)
        node_loss = updated_loss
        node_q_loss = updated_q_loss
        if final_residual <= tolerance_kw and not caps_changed and validation.hourly["is_feasible"].all():
            converged = True
            break
    assert result is not None and validation is not None
    return result, validation, PhysicalFeedback(
        node_loss,
        node_q_loss,
        dict(component_caps),
        converged,
        iterations,
        final_residual,
    )


def solve_strategy_with_feedback(
    model: GridModel,
    scenario: DisasterScenario,
    strategy: str,
    *,
    service_contract: ServiceContract | None = None,
    dispatch_objective: DispatchObjective | None = None,
    initial_feedback: PhysicalFeedback | None = None,
    max_iterations: int = 8,
    tolerance_kw: float = 0.10,
    strict_contract: bool = True,
) -> tuple[StrategyResult, FlowValidation, PhysicalFeedback]:
    """Public constrained candidate solver used by Pareto scans.

    Unlike the legacy carbon-strategy fallback, strict candidates preserve
    every service/carbon cap. An infeasible epsilon therefore remains an
    auditable failed point instead of being silently relaxed.
    """

    return _simulate_with_loss_feedback(
        model,
        scenario,
        strategy,
        max_iterations=max_iterations,
        tolerance_kw=tolerance_kw,
        initial_feedback=initial_feedback,
        update_component_caps=True,
        service_contract=service_contract,
        dispatch_objective=dispatch_objective,
        strict_contract=strict_contract,
    )


def run_pipeline(scenario_name: str = "暴雨内涝") -> PipelineResult:
    return run_scenario(get_scenario(scenario_name))


def run_scenario(scenario: DisasterScenario) -> PipelineResult:
    model = build_ieee33()
    solved: dict[str, tuple[StrategyResult, FlowValidation, PhysicalFeedback]] = {}
    solved["传统顺序恢复"] = _simulate_with_loss_feedback(model, scenario, "传统顺序恢复")
    solved["最小失供恢复"] = _simulate_with_loss_feedback(model, scenario, "最小失供恢复")
    service_reference = solved["最小失供恢复"][0].dispatch.frame
    critical_limit = float(service_reference["unserved_critical_kw"].sum()) + 1e-3
    normal_limit = (
        float(service_reference["unserved_normal_kw"].sum())
        + 0.08 * float(service_reference["normal_load_kw"].sum())
    )
    solved["碳韧协同恢复"] = _simulate_with_loss_feedback(
        model,
        scenario,
        "碳韧协同恢复",
        critical_unserved_limit_kwh=critical_limit,
        normal_unserved_limit_kwh=normal_limit,
        initial_feedback=solved["最小失供恢复"][2],
        update_component_caps=True,
    )
    results = {strategy: value[0] for strategy, value in solved.items()}
    validations = {strategy: value[1] for strategy, value in solved.items()}
    metrics = {strategy: result.metrics for strategy, result in results.items()}
    feedbacks = {strategy: value[2] for strategy, value in solved.items()}
    return PipelineResult(
        model,
        scenario,
        results,
        validations,
        comparison_table(metrics),
        feedbacks,
    )
