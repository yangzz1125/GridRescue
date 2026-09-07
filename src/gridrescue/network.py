from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import numpy as np
import pandas as pd

from .case33_data import BASE_KV, BASE_MVA, BRANCHES, BUS_LOADS, SOURCE_NAME, SOURCE_SHA256


@dataclass(frozen=True)
class GridModel:
    nodes: pd.DataFrame
    branches: pd.DataFrame
    root_node: int = 0
    base_mva: float = BASE_MVA
    base_kv: float = BASE_KV
    source_name: str = SOURCE_NAME
    source_sha256: str = SOURCE_SHA256
    capacity_assumption: str = "GridRescue engineering thermal limits v0.2; MATPOWER rateA/B/C are unspecified"

    @property
    def base_branch_ids(self) -> tuple[int, ...]:
        return tuple(int(x) for x in self.branches.loc[~self.branches["is_tie"], "branch_id"])

    @property
    def tie_branch_ids(self) -> tuple[int, ...]:
        return tuple(int(x) for x in self.branches.loc[self.branches["is_tie"], "branch_id"])


def _thermal_limit_kva(branch_id: int, is_tie: bool) -> float:
    """Return explicit engineering assumptions absent from case33bw."""

    if is_tie:
        return 1800.0
    if branch_id <= 2:
        return 5200.0
    if branch_id <= 5:
        return 3800.0
    if branch_id <= 17:
        return 2200.0
    return 1600.0


def build_ieee33(seed: int = 2026) -> GridModel:
    """Build the canonical MATPOWER case33bw with project-specific DERs.

    ``seed`` is retained for API compatibility.  The electrical network is
    deterministic and comes from the bundled, checksummed MATPOWER case.
    """

    del seed
    node_ids = np.arange(33)
    base_load = np.array([row[1] for row in BUS_LOADS], dtype=float)
    reactive_load = np.array([row[2] for row in BUS_LOADS], dtype=float)
    critical_level = np.ones(33, dtype=int)
    critical_level[[2, 5, 13, 17, 24, 29]] = 3
    critical_level[[7, 11, 20, 27, 31]] = 2
    pv_capacity = np.zeros(33)
    pv_capacity[[10, 17, 24, 29, 32]] = [180, 260, 220, 310, 170]
    storage_power = np.zeros(33)
    storage_energy = np.zeros(33)
    storage_power[[13, 29]] = [120, 160]
    storage_energy[[13, 29]] = [390, 510]
    diesel_capacity = np.zeros(33)
    diesel_capacity[[17, 29]] = [220, 300]
    node_type = np.full(33, "普通负荷", dtype=object)
    node_type[0] = "上级电网"
    node_type[[2, 17]] = "医院/应急"
    node_type[[5, 24]] = "通信/数据"
    node_type[[13, 29]] = "综合能源站"

    nodes = pd.DataFrame(
        {
            "node_id": node_ids,
            "label": [f"N{i + 1:02d}" for i in node_ids],
            "base_load_kw": base_load,
            "reactive_load_kvar": reactive_load,
            "critical_level": critical_level,
            "pv_capacity_kw": pv_capacity,
            "storage_power_kw": storage_power,
            "storage_energy_kwh": storage_energy,
            "diesel_capacity_kw": diesel_capacity,
            "node_type": node_type,
        }
    ).set_index("node_id")

    branch_rows = []
    z_base_ohm = (BASE_KV * 1e3) ** 2 / (BASE_MVA * 1e6)
    for branch_id, (from_bus, to_bus, r_ohm, x_ohm, normally_closed) in enumerate(BRANCHES, start=1):
        is_tie = not normally_closed
        capacity_kva = _thermal_limit_kva(branch_id, is_tie)
        power_factor_assumption = 0.95
        branch_rows.append(
            {
                "branch_id": branch_id,
                "from_node": from_bus - 1,
                "to_node": to_bus - 1,
                "is_tie": is_tie,
                "normally_closed": normally_closed,
                "capacity_kw": capacity_kva * power_factor_assumption,
                "capacity_kva": capacity_kva,
                "power_factor_assumption": power_factor_assumption,
                "capacity_source": "engineering_assumption_v0.2",
                "resistance_ohm": r_ohm,
                "reactance_ohm": x_ohm,
                "resistance_pu": r_ohm / z_base_ohm,
                "reactance_pu": x_ohm / z_base_ohm,
            }
        )
    branches = pd.DataFrame(branch_rows).set_index("branch_id", drop=False)
    return GridModel(nodes=nodes.round(6), branches=branches.round(8), root_node=0)


def graph_from_state(
    model: GridModel,
    open_branch_ids: set[int] | frozenset[int] = frozenset(),
    closed_tie_ids: set[int] | frozenset[int] = frozenset(),
) -> nx.Graph:
    graph = nx.Graph()
    for node_id, row in model.nodes.iterrows():
        graph.add_node(int(node_id), **row.to_dict())
    for branch_id, row in model.branches.iterrows():
        branch_id = int(branch_id)
        if branch_id in open_branch_ids:
            continue
        should_close = bool(row["normally_closed"]) or branch_id in closed_tie_ids
        if should_close:
            graph.add_edge(
                int(row["from_node"]),
                int(row["to_node"]),
                branch_id=branch_id,
                capacity_kw=float(row["capacity_kw"]),
                capacity_kva=float(row["capacity_kva"]),
                resistance_pu=float(row["resistance_pu"]),
                reactance_pu=float(row["reactance_pu"]),
                is_tie=bool(row["is_tie"]),
            )
    return graph


def root_component(graph: nx.Graph, root_node: int = 0) -> set[int]:
    if root_node not in graph:
        return set()
    return set(nx.node_connected_component(graph, root_node))


def islands(graph: nx.Graph, root_node: int = 0) -> list[set[int]]:
    root = root_component(graph, root_node)
    return [set(component) for component in nx.connected_components(graph) if not set(component).issubset(root)]


def is_radial(graph: nx.Graph) -> bool:
    return nx.is_forest(graph)
