from __future__ import annotations

"""Build README diagrams with embedded Chinese glyphs.

Matplotlib defaults on Windows commonly fall back to DejaVu Sans, which does
not contain the Chinese labels used by this project.  This builder selects a
known CJK font explicitly and converts SVG text to paths, so the diagrams keep
working on machines that do not have the original font installed.
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager, patches
import networkx as nx

from gridrescue.network import build_ieee33


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "assets" / "readme"


def cjk_font() -> font_manager.FontProperties:
    candidates = (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\Deng.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    )
    for path in candidates:
        if path.exists():
            return font_manager.FontProperties(fname=str(path))
    for family in ("Microsoft YaHei", "SimHei", "DengXian", "Noto Sans CJK SC"):
        try:
            path = font_manager.findfont(family, fallback_to_default=False)
        except ValueError:
            continue
        if path:
            return font_manager.FontProperties(fname=path)
    raise RuntimeError("No Chinese-capable font found. Install Microsoft YaHei, SimHei, or Noto Sans CJK SC.")


def configure_matplotlib(font: font_manager.FontProperties) -> None:
    plt.rcParams.update(
        {
            "font.family": font.get_name(),
            "font.sans-serif": [font.get_name(), "Microsoft YaHei", "SimHei"],
            "axes.unicode_minus": False,
            "svg.fonttype": "path",
            "savefig.facecolor": "white",
        }
    )


def _save(fig: plt.Figure, output: Path, stem: str) -> None:
    fig.savefig(output / f"{stem}.png", dpi=180, bbox_inches="tight")
    fig.savefig(output / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def _box(ax, x, y, w, h, text, font, color="#d9f3ff", fontsize=15) -> None:
    ax.add_patch(
        patches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.03",
            facecolor=color,
            edgecolor="#365461",
            linewidth=1.8,
        )
    )
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color="#102a33",
        fontproperties=font,
    )


def _arrow(ax, x1, y1, x2, y2) -> None:
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops={"arrowstyle": "-|>", "lw": 2.1, "color": "#3f5661", "shrinkA": 2, "shrinkB": 2},
    )


def build_architecture(output: Path, font: font_manager.FontProperties) -> None:
    fig, ax = plt.subplots(figsize=(14, 5.2))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    ax.set_facecolor("#f7fafc")
    ax.text(7, 4.85, "GridRescue 计算与证据闭环", ha="center", fontsize=24, weight="bold", color="#14323d", fontproperties=font)

    _box(ax, 0.4, 1.9, 1.8, 0.92, "灾害场景\n网络模型", font, fontsize=13)
    _box(ax, 2.8, 2.0, 1.8, 0.75, "故障与恢复", font)
    _box(ax, 5.2, 2.0, 1.8, 0.75, "联合调度", font)
    _box(ax, 7.6, 2.0, 1.8, 0.75, "P/Q 潮流", font)
    _box(ax, 10.0, 3.0, 1.7, 0.72, "Care 服务门", font, "#d9f7e8")
    _box(ax, 10.0, 1.9, 1.7, 0.92, "Physics\n物理门", font, "#fff1c7", fontsize=13)
    _box(ax, 10.0, 1.0, 1.7, 0.72, "MRV 证据门", font, "#ffe0e0")
    _box(ax, 12.2, 2.0, 1.5, 0.75, "主张 / 界面", font, "#e8ddff")

    _arrow(ax, 2.2, 2.36, 2.8, 2.38)
    _arrow(ax, 4.6, 2.38, 5.2, 2.38)
    _arrow(ax, 7.0, 2.38, 7.6, 2.38)
    _arrow(ax, 9.4, 2.38, 10.0, 3.36)
    _arrow(ax, 9.4, 2.38, 10.0, 2.36)
    _arrow(ax, 9.4, 2.38, 10.0, 1.36)
    _arrow(ax, 11.7, 3.36, 12.2, 2.38)
    _arrow(ax, 11.7, 2.36, 12.2, 2.38)
    _arrow(ax, 11.7, 1.36, 12.2, 2.38)
    _save(fig, output, "gridrescue_architecture")


def build_claim_gates(output: Path, font: font_manager.FontProperties) -> None:
    fig, ax = plt.subplots(figsize=(14, 5.2))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    ax.set_facecolor("#f7fafc")
    ax.text(7, 4.85, "三道门与主张资格", ha="center", fontsize=24, weight="bold", color="#14323d", fontproperties=font)

    _box(ax, 0.7, 2.0, 2.1, 0.75, "候选恢复策略", font)
    _box(ax, 3.7, 3.2, 2.1, 0.75, "CareTask 合同", font, "#d9f7e8")
    _box(ax, 3.7, 2.0, 2.1, 0.75, "Physics 校验", font, "#fff1c7")
    _box(ax, 3.7, 0.8, 2.1, 0.75, "MRV verifier", font, "#ffe0e0")
    _box(ax, 7.2, 3.0, 2.5, 0.75, "严格同服务主张", font, "#e8ddff")
    _box(ax, 7.2, 1.9, 2.5, 0.75, "受控服务预算差异", font, "#e8ddff")
    _box(ax, 7.2, 0.8, 2.5, 0.75, "仅清单展示", font, "#e8ddff")
    _box(ax, 10.7, 1.9, 2.6, 0.75, "Streamlit / ZIP 证据", font, "#d9f3ff")

    _arrow(ax, 2.8, 2.38, 3.7, 3.58)
    _arrow(ax, 2.8, 2.38, 3.7, 2.38)
    _arrow(ax, 2.8, 2.38, 3.7, 1.18)
    _arrow(ax, 5.8, 3.58, 7.2, 3.38)
    _arrow(ax, 5.8, 2.38, 7.2, 2.28)
    _arrow(ax, 5.8, 1.18, 7.2, 1.18)
    _arrow(ax, 9.7, 2.28, 10.7, 2.28)
    _save(fig, output, "claim_gates")


def build_streamlit_tabs(output: Path, font: font_manager.FontProperties) -> None:
    fig, ax = plt.subplots(figsize=(14, 5.2))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    ax.set_facecolor("#f7fafc")
    ax.text(7, 4.85, "Streamlit 评委工作台与八页交互", ha="center", fontsize=24, weight="bold", color="#14323d", fontproperties=font)
    _box(ax, 0.4, 2.05, 2.2, 0.82, "评委决策工作台", font, "#e8ddff")
    top = ["恢复数字孪生", "三策略对照", "能源与碳流", "潮流校验"]
    bottom = ["MRV 报告", "公平 Pareto", "成岛护照", "生命线任务"]
    xs = [3.1, 5.3, 7.5, 9.7]
    ax.plot([2.6, 2.9], [2.46, 2.46], color="#3f5661", linewidth=2.1)
    ax.plot([2.9, 2.9], [1.36, 3.46], color="#3f5661", linewidth=2.1)
    for x, label in zip(xs, top):
        _box(ax, x, 3.1, 1.8, 0.72, label, font)
        _arrow(ax, 2.9, 3.46, x, 3.46)
    for x, label in zip(xs, bottom):
        _box(ax, x, 1.0, 1.8, 0.72, label, font)
        _arrow(ax, 2.9, 1.36, x, 1.36)
    _save(fig, output, "streamlit_tabs")


def build_topology(output: Path, font: font_manager.FontProperties) -> None:
    model = build_ieee33()
    graph = nx.Graph()
    graph.add_nodes_from(int(node_id) for node_id in model.nodes.index)
    base_edges = []
    tie_edges = []
    for _, row in model.branches.iterrows():
        edge = (int(row["from_node"]), int(row["to_node"]))
        graph.add_edge(*edge)
        (tie_edges if bool(row["is_tie"]) else base_edges).append(edge)

    pos = nx.spring_layout(graph, seed=18, k=0.43, iterations=500)
    critical = [int(i) for i, row in model.nodes.iterrows() if int(row["critical_level"]) >= 2]
    normal = [int(i) for i in model.nodes.index if int(i) not in critical and int(i) != model.root_node]

    fig, ax = plt.subplots(figsize=(15, 8.6))
    nx.draw_networkx_edges(graph, pos, edgelist=base_edges, width=1.6, edge_color="#718096", ax=ax)
    nx.draw_networkx_edges(graph, pos, edgelist=tie_edges, width=2.2, edge_color="#20b2aa", style="dashed", ax=ax)
    nx.draw_networkx_nodes(graph, pos, nodelist=normal, node_color="#38c793", node_size=430, edgecolors="white", linewidths=1.2, ax=ax)
    nx.draw_networkx_nodes(graph, pos, nodelist=critical, node_color="#ef4444", node_size=530, edgecolors="white", linewidths=1.3, ax=ax)
    nx.draw_networkx_nodes(graph, pos, nodelist=[model.root_node], node_color="#f59e0b", node_size=650, edgecolors="white", linewidths=1.4, ax=ax)
    labels = {int(i): str(row["label"]) for i, row in model.nodes.iterrows()}
    nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8.5, font_color="#102a33", font_family=font.get_name(), ax=ax)

    legend = [
        plt.Line2D([0], [0], marker="o", color="w", label="上级电网", markerfacecolor="#f59e0b", markersize=11),
        plt.Line2D([0], [0], marker="o", color="w", label="关键负荷", markerfacecolor="#ef4444", markersize=11),
        plt.Line2D([0], [0], marker="o", color="w", label="普通/资源节点", markerfacecolor="#38c793", markersize=11),
        plt.Line2D([0], [0], color="#718096", lw=2, label="常闭支路"),
        plt.Line2D([0], [0], color="#20b2aa", lw=2.5, ls="--", label="常开联络线"),
    ]
    ax.legend(handles=legend, loc="upper left", prop=font, frameon=True, framealpha=0.96)
    ax.set_title("GridRescue · MATPOWER case33bw 33 节点拓扑", fontsize=22, pad=18, fontproperties=font)
    ax.text(
        0.01,
        0.01,
        "说明：网络电气参数来自 case33bw；关键负荷、DER 位置与热限额为项目工程标注。",
        transform=ax.transAxes,
        fontsize=11,
        color="#334155",
        fontproperties=font,
    )
    ax.axis("off")
    _save(fig, output, "case33bw_topology")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    font = cjk_font()
    configure_matplotlib(font)
    build_architecture(args.output, font)
    build_claim_gates(args.output, font)
    build_streamlit_tabs(args.output, font)
    build_topology(args.output, font)
    print(f"README visuals rebuilt with {font.get_name()}: {args.output}")


if __name__ == "__main__":
    main()
