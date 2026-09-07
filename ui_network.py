"""Case33 single-line presentation; does not modify topology or dispatch data."""
from base64 import b64encode
from functools import lru_cache
from html import escape
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from gridrescue.restoration import state_at_hour

BACKGROUND = "#202927"
FACILITIES = {
    "上级电网": "utility-pole",
    "医院/应急": "hospital",
    "通信/数据": "radio-tower",
    "综合能源站": "battery-charging",
}
# Fixed electrical schematic coordinates, not geographic locations.
POSITIONS = dict(enumerate([(x, 0) for x in (0, 2, 4, 5.5, 7, 9, 11, 12.5, 14, 15.5, 17, 18.5, 20, 22, 24, 25.5, 27, 29)]))
POSITIONS.update({node: (2 + (node - 18) * 2, 4) for node in range(18, 22)})
POSITIONS.update({22: (4, -4), 23: (6, -4), 24: (9, -4)})
POSITIONS.update({node: (9 + (node - 25) * 2, 8) for node in range(25, 33)})


@lru_cache(maxsize=4)
def facility_icon(name):
    svg = (Path(__file__).parent / "ui/icons" / f"{name}.svg").read_text(encoding="utf-8")
    return "data:image/svg+xml;base64," + b64encode(svg.replace('stroke="currentColor"', 'stroke="#e8f4ee"').encode()).decode()


def branch_route(row):
    left, right = POSITIONS[int(row.from_node)], POSITIONS[int(row.to_node)]
    # Each tie has its own corridor; endpoints remain the actual case33 buses.
    corridors = {
        33: [left, (6, 2.4), (12.5, 2.4), right],
        34: [left, (14, -2), (24, -2), right],
        35: [left, (18.5, 5.6), (8, 5.6), right],
        36: [left, (31, 0), (31, 8), right],
        37: [left, (12, -4), (12, 6.2), (15, 6.2), right],
    }
    if int(row.branch_id) in corridors:
        return corridors[int(row.branch_id)]
    if left[0] != right[0] and left[1] != right[1]:
        return [left, (left[0], right[1]), right]
    return [left, right]


def split_route(points, gap=.4):
    """Cut a visible switch/fault gap in the longest route segment."""
    lengths = [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:])]
    i = lengths.index(max(lengths))
    a, b = points[i:i + 2]
    center = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    dx, dy = (b[0] - a[0]) / lengths[i], (b[1] - a[1]) / lengths[i]
    before = (center[0] - dx * gap, center[1] - dy * gap)
    after = (center[0] + dx * gap, center[1] + dy * gap)
    return points[:i + 1] + [before, None, after] + points[i + 1:], center


def build_network_figure(result, strategy, hour, *, show_numbers=False, selected_node=2):
    model = result.model
    selected = result.strategies[strategy]
    state = state_at_hour(model, result.scenario, selected.plan, hour)
    prior = state_at_hour(model, result.scenario, selected.plan, hour - 1) if hour else state
    repaired = set(prior.failed_branch_ids) - set(state.failed_branch_ids)
    closed = set(state.closed_tie_ids) - set(prior.closed_tie_ids)
    dispatch = selected.dispatch.node_frame
    current = dispatch[dispatch.hour == hour].set_index("node_id")
    previous = dispatch[dispatch.hour == max(0, hour - 1)].set_index("node_id")
    restored = [int(node) for node in model.nodes.index if current.loc[node, "served_load_kw"] > 1e-3 and previous.loc[node, "served_load_kw"] <= 1e-3]
    fig = go.Figure()
    routes, branch_colors, legend_seen = {}, {}, set()
    for row in model.branches.itertuples():
        branch = int(row.branch_id)
        route = branch_route(row)
        routes[branch] = route
        failed = branch in state.failed_branch_ids
        open_tie = row.is_tie and branch not in state.closed_tie_ids
        changed = branch in repaired or branch in closed
        color = "#f2c96a" if changed else "#ff827a" if failed else "#52675d" if open_tie else "#72cbaa" if row.is_tie else "#718f80"
        branch_colors[branch] = color
        name = "本小时恢复/合闸" if changed else "故障断口" if failed else "联络线·断开" if open_tie else "联络线·闭合" if row.is_tie else "运行支路"
        center = None
        if failed or row.is_tie:
            cut, center = split_route(route)
            if failed or open_tie:
                route = cut
        fig.add_trace(go.Scatter(
            x=[p[0] if p else None for p in route], y=[p[1] if p else None for p in route],
            mode="lines", name=name, legendgroup=name, showlegend=name not in legend_seen,
            line=dict(color=color, width=3 if changed else 2 if not open_tie else 1, dash="dot" if open_tie else "solid"),
            hoverinfo="skip", meta={"branch_id": branch},
        ))
        legend_seen.add(name)
        if center:
            fig.add_annotation(x=center[0], y=center[1], text="×" if failed else "○/○" if open_tie else "●—●",
                               hovertext=f"支路 {branch} · N{row.from_node + 1:02d} — N{row.to_node + 1:02d} · {name}",
                               showarrow=False, font=dict(size=14 if failed else 11, color=color), bgcolor=BACKGROUND, borderpad=1)
    # Crossing bridges distinguish a line crossing from a connected bus.
    crossings = set()
    segments = [(bid, a, b) for bid, route in routes.items() for a, b in zip(route, route[1:])]
    for bid, a, b in segments:
        if a[1] != b[1]:
            continue
        for other, c, d in segments:
            if other == bid or c[0] != d[0]:
                continue
            x, y = c[0], a[1]
            if min(a[0], b[0]) < x < max(a[0], b[0]) and min(c[1], d[1]) < y < max(c[1], d[1]):
                crossings.add((x, y, other))
    for x, y, branch in crossings:
        color = branch_colors[branch]
        fig.add_shape(type="line", x0=x, x1=x, y0=y-.23, y1=y+.23, line=dict(color=BACKGROUND, width=6))
        fig.add_shape(type="path", path=f"M {x},{y-.23} Q {x+.5},{y} {x},{y+.23}", line=dict(color=color, width=1.5))
    for node, row in model.nodes.iterrows():
        x, y = POSITIONS[node]
        facility = row.node_type in FACILITIES
        supplied = node == model.root_node or current.loc[node, "served_load_kw"] > 1e-3
        color = "#71b89a" if supplied else "#edb85d"
        if row.critical_level >= 2 and not supplied:
            color = "#ff827a"
        if node in restored:
            color = "#f2c96a"
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text", name=f"N{node + 1:02d}", showlegend=False,
            meta={"node_id": int(node)}, customdata=[[int(node)]],
            text=[f"N{node + 1:02d}" if show_numbers and not facility else ""],
            textposition="top center" if int(x * 2) % 4 else "bottom center", textfont=dict(size=10, color="#a9bcb1"),
            marker=dict(size=32 if facility else 10 if row.critical_level >= 2 else 7,
                        symbol="square" if facility else "circle", color=BACKGROUND if facility else color,
                        line=dict(width=3 if node == selected_node else 1.5, color="#ffffff" if node == selected_node else color)),
            selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
            hovertemplate=f"N{node + 1:02d} · {escape(row.node_type)}<br>服务功率 {current.loc[node, 'served_load_kw']:.1f} kW<extra></extra>",
        ))
        if facility:
            fig.add_layout_image(source=facility_icon(FACILITIES[row.node_type]), x=x, y=y,
                                 xref="x", yref="y", sizex=.95, sizey=.75,
                                 xanchor="center", yanchor="middle", layer="above")
            resources = []
            if row.pv_capacity_kw > 0: resources.append("光伏")
            if row.storage_energy_kwh > 0: resources.append("储能")
            if row.diesel_capacity_kw > 0: resources.append("柴油")
            text = f"N{node + 1:02d} {escape(row.node_type)}"
            if resources: text += "<br>" + " · ".join(resources)
            fig.add_annotation(x=x, y=y-1, text=text, showarrow=False, yanchor="top",
                               font=dict(size=11, color="#dfebe4"), bgcolor=BACKGROUND, borderpad=3)
    fig.update_layout(
        height=480, margin=dict(l=40, r=28, t=28, b=55),
        paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        xaxis=dict(visible=False, range=[-1.8, 32], fixedrange=True),
        yaxis=dict(visible=False, range=[-6.7, 9.5], fixedrange=True),
        legend=dict(orientation="h", x=0, y=-.02, font=dict(size=10, color="#c2d0c7")),
        hoverlabel=dict(bgcolor="#fff", font_color="#22282c"), clickmode="event+select",
        hovermode="closest", dragmode=False, selectionrevision=f"{strategy}:{hour}:{selected_node}",
        meta={"routes": routes, "repaired": sorted(repaired), "closed": sorted(closed), "restored": restored},
    )
    return fig


def select_chart_node(chart_key, selection_key):
    points = st.session_state[chart_key].selection.points
    for point in reversed(points):
        data = point.get("customdata")
        if data and int(data[0]) in POSITIONS:
            st.session_state[selection_key] = int(data[0])
            break


def render_node_details(result, strategy, hour, node):
    model_row = result.model.nodes.loc[node]
    frame = result.strategies[strategy].dispatch.node_frame
    current = frame[(frame.hour == hour) & (frame.node_id == node)].iloc[0]
    voltages = result.validations[strategy].nodes
    voltage = voltages[(voltages.hour == hour) & (voltages.node_id == node)].iloc[0]
    st.markdown(f"**N{node + 1:02d} · {model_row.node_type}**")
    demand = float(current.critical_load_kw + current.normal_load_kw)
    a, b, c = st.columns(3)
    a.metric("节点需求", f"{demand:.1f} kW")
    b.metric("实际供电", f"{current.served_load_kw:.1f} kW")
    c.metric("节点电压", f"{voltage.voltage_pu:.3f} pu")
    resources = []
    if model_row.pv_capacity_kw: resources.append(f"光伏 {model_row.pv_capacity_kw:g} kW")
    if model_row.storage_energy_kwh: resources.append(f"储能 {model_row.storage_power_kw:g} kW / {model_row.storage_energy_kwh:g} kWh")
    if model_row.diesel_capacity_kw: resources.append(f"柴油 {model_row.diesel_capacity_kw:g} kW")
    st.caption(" · ".join(resources) if resources else "上级电网接入点" if node == result.model.root_node else "普通负荷节点" if model_row.critical_level == 1 else "关键服务节点")


def render_network(result, strategy, hour, *, key, expanded=False):
    selection_key = f"{key}-node"
    if selection_key not in st.session_state:
        st.session_state[selection_key] = 2
    toggle_column, button_column = st.columns([2, 1])
    show_numbers = toggle_column.toggle("全部节点编号", key=f"{key}-numbers")
    if not expanded and button_column.button("展开电网图", icon=":material/open_in_full:", key=f"{key}-expand"):
        st.session_state["expanded-network-node"] = st.session_state[selection_key]
        st.session_state["expanded-network-numbers"] = show_numbers
        expanded_network(result, strategy, hour)
    figure = build_network_figure(result, strategy, hour, show_numbers=show_numbers, selected_node=st.session_state[selection_key])
    with st.container(key=f"network-canvas-{key}"):
        st.plotly_chart(figure, width="stretch", theme=None, key=f"{key}-chart", selection_mode="points",
                        on_select=lambda: select_chart_node(f"{key}-chart", selection_key),
                        config={"displayModeBar": False, "scrollZoom": False})
    changed = figure.layout.meta
    items = [f"修复支路 {', '.join(map(str, changed['repaired']))}" if changed['repaired'] else "",
             f"合闸 {', '.join(map(str, changed['closed']))}" if changed['closed'] else "",
             "恢复供电 " + ", ".join(f"N{n+1:02d}" for n in changed['restored']) if changed['restored'] else ""]
    st.caption("本小时：" + "；".join(x for x in items if x) if any(items) else "本小时无新增修复或恢复供电")
    node = st.selectbox("查看节点", list(result.model.nodes.index), key=selection_key,
                        format_func=lambda n: f"N{n+1:02d} · {result.model.nodes.loc[n, 'node_type']}")
    render_node_details(result, strategy, hour, node)


@st.dialog("配电网单线图", width="large")
def expanded_network(result, strategy, hour):
    st.caption(f"{strategy} · T+{hour:02d}:00 · 电气示意，非地理位置")
    render_network(result, strategy, hour, key="expanded-network", expanded=True)
