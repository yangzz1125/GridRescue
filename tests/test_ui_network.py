import pickle
from pathlib import Path

from gridrescue.restoration import state_at_hour
from ui_network import POSITIONS, branch_route, build_network_figure, split_route

ROOT = Path(__file__).resolve().parents[1]


def test_schematic_preserves_topology_facilities_and_hourly_changes():
    with (ROOT / "artifacts/competition2026/baseline_current/flood/pipeline.pkl").open("rb") as handle:
        result = pickle.load(handle)
    model = result.model
    assert set(POSITIONS) == set(model.nodes.index)
    assert len(set(POSITIONS.values())) == 33
    for row in model.branches.itertuples():
        route = branch_route(row)
        assert route[0] == POSITIONS[row.from_node]
        assert route[-1] == POSITIONS[row.to_node]
        for a, b in zip(route, route[1:]):
            assert a[0] == b[0] or a[1] == b[1]
            for node, p in POSITIONS.items():
                if node not in (row.from_node, row.to_node):
                    assert not (a[0] == b[0] == p[0] and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))
                    assert not (a[1] == b[1] == p[1] and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]))
        cut, center = split_route(route)
        assert cut[0] == route[0] and cut[-1] == route[-1]
        assert None in cut and center not in (route[0], route[-1])
    strategy = "碳韧协同恢复"
    for hour in (0, 4, 7, 23):
        figure = build_network_figure(result, strategy, hour)
        nodes = [trace for trace in figure.data if trace.meta and "node_id" in trace.meta]
        assert len(nodes) == 33
        assert {trace.customdata[0][0] for trace in nodes} == set(model.nodes.index)
        assert not any(trace.text[0] for trace in nodes)
        assert len(figure.layout.images) == 7
        assert len(figure.layout.meta["routes"]) == 37
        state = state_at_hour(model, result.scenario, result.strategies[strategy].plan, hour)
        previous = state_at_hour(model, result.scenario, result.strategies[strategy].plan, max(0, hour - 1))
        assert figure.layout.meta["repaired"] == sorted(set(previous.failed_branch_ids) - set(state.failed_branch_ids))
        assert figure.layout.meta["closed"] == sorted(set(state.closed_tie_ids) - set(previous.closed_tie_ids))
        dispatch = result.strategies[strategy].dispatch.node_frame
        current = dispatch[dispatch.hour == hour].set_index("node_id")
        prior = dispatch[dispatch.hour == max(0, hour - 1)].set_index("node_id")
        restored = sorted(current.index[(current.served_load_kw > 1e-3) & (prior.served_load_kw <= 1e-3)])
        assert figure.layout.meta["restored"] == restored
        for trace in nodes:
            if trace.meta["node_id"] in restored and trace.meta["node_id"] != 2:
                assert trace.marker.line.color == "#f2c96a"
        for trace in figure.data:
            if trace.meta and trace.meta.get("branch_id") in figure.layout.meta["repaired"] + figure.layout.meta["closed"]:
                assert trace.line.color == "#f2c96a"
    numbered = build_network_figure(result, strategy, 4, show_numbers=True)
    assert sum(bool(trace.text and trace.text[0]) for trace in numbered.data) == 26
