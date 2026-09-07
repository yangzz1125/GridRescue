from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import pandas as pd

from .network import GridModel, graph_from_state, islands, is_radial, root_component


@dataclass(frozen=True)
class FaultState:
    failed_branch_ids: frozenset[int]
    closed_tie_ids: frozenset[int]
    energized_nodes: frozenset[int]
    islands: tuple[frozenset[int], ...]


def evaluate_state(
    model: GridModel,
    failed_branch_ids: set[int] | frozenset[int],
    closed_tie_ids: set[int] | frozenset[int] = frozenset(),
) -> FaultState:
    failed = frozenset(int(x) for x in failed_branch_ids)
    ties = frozenset(int(x) for x in closed_tie_ids)
    graph = graph_from_state(model, failed, ties)
    if not is_radial(graph):
        raise ValueError("closed ties create a loop; restoration state must remain radial")
    return FaultState(
        failed_branch_ids=failed,
        closed_tie_ids=ties,
        energized_nodes=frozenset(root_component(graph, model.root_node)),
        islands=tuple(frozenset(x) for x in islands(graph, model.root_node)),
    )


def component_load_kw(model: GridModel, nodes: set[int] | frozenset[int]) -> float:
    if not nodes:
        return 0.0
    return float(model.nodes.loc[list(nodes), "base_load_kw"].sum())


def close_ties_greedily(
    model: GridModel,
    failed_branch_ids: set[int] | frozenset[int],
    score: str = "load",
) -> tuple[int, ...]:
    """Select loop-free tie closures that maximize restored weighted load."""

    chosen: list[int] = []
    current = evaluate_state(model, failed_branch_ids, chosen)
    candidates = list(model.tie_branch_ids)
    while candidates:
        best: tuple[float, int, FaultState] | None = None
        for tie_id in candidates:
            try:
                state = evaluate_state(model, failed_branch_ids, set(chosen) | {tie_id})
            except ValueError:
                continue
            newly = set(state.energized_nodes) - set(current.energized_nodes)
            if score == "critical":
                node_rows = model.nodes.loc[list(newly)] if newly else pd.DataFrame()
                gain = float((node_rows.get("base_load_kw", 0) * node_rows.get("critical_level", 0)).sum()) if newly else 0.0
                gain += float(node_rows.get("pv_capacity_kw", pd.Series(dtype=float)).sum()) * 0.25 if newly else 0.0
            else:
                gain = component_load_kw(model, newly)
            if best is None or gain > best[0]:
                best = (gain, tie_id, state)
        if best is None or best[0] <= 0:
            break
        chosen.append(best[1])
        current = best[2]
        candidates.remove(best[1])
    return tuple(chosen)


def branch_downstream_score(model: GridModel, branch_id: int, critical: bool = False) -> float:
    row = model.branches.loc[branch_id]
    graph = graph_from_state(model, {branch_id})
    disconnected = set(model.nodes.index) - root_component(graph, model.root_node)
    if not disconnected:
        return 0.0
    frame = model.nodes.loc[list(disconnected)]
    score = frame["base_load_kw"]
    if critical:
        score = score * frame["critical_level"] + 0.25 * frame["pv_capacity_kw"]
    return float(score.sum())

