"""Presentation components; simulation and evidence remain in their owning modules."""
from html import escape
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

STRATEGY_COLORS = {"传统顺序恢复": "#87919a", "最小失供恢复": "#326bd6", "碳韧协同恢复": "#168365"}


def setup_ui():
    st.set_page_config(page_title="碳韧智网 | GridRescue", page_icon=":material/hub:", layout="wide", initial_sidebar_state="auto")
    css = (Path(__file__).resolve().parent / "ui/styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    pio.templates["gridrescue"] = go.layout.Template(layout=dict(
        font=dict(family="Microsoft YaHei, Arial, sans-serif", size=12, color="#454b50"),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        colorway=list(STRATEGY_COLORS.values()),
        margin=dict(l=48, r=20, t=24, b=65),
        xaxis=dict(gridcolor="#edf0f2", zerolinecolor="#dfe3e6"),
        yaxis=dict(gridcolor="#edf0f2", zerolinecolor="#dfe3e6"),
        legend=dict(orientation="h", y=-.28, x=0, font=dict(size=11)),
    ))
    pio.templates.default = "gridrescue"


def render_brand():
    st.markdown('<div class="brand"><strong>GridRescue<span>.</span></strong><span>碳韧智网</span></div>', unsafe_allow_html=True)


def render_heading(scenario, strategy):
    st.markdown('<header class="project-heading"><div><h1>碳韧智网 <span>GridRescue</span></h1>'
                '<p>极端天气下的配电网恢复与低碳保供</p></div>'
                '<div class="project-scope"><strong>33</strong><span>节点配电网<br>24 小时恢复推演</span></div></header>'
                f'<div class="scenario-context"><strong>{escape(scenario)}</strong><span>{escape(strategy)}</span>'
                '<span class="evidence-note">公开算例 · 工程仿真</span></div>', unsafe_allow_html=True)


def render_metrics(metrics):
    values = [
        ("关键负荷恢复", f"{metrics.critical_recovery_pct:.1f}", "%"),
        ("失供电量 EENS", f"{metrics.eens_kwh:,.0f}", "kWh"),
        ("恢复碳清单", f"{metrics.total_carbon_kg:,.0f}", "kgCO2"),
        ("柴油发电", f"{metrics.diesel_energy_kwh:,.0f}", "kWh"),
        ("新能源消纳", f"{metrics.renewable_consumed_kwh:,.0f}", "kWh"),
        ("开关 / 修复", str(metrics.switch_operations), "次"),
    ]
    items = ''.join(f'<div class="kpi"><div class="kpi-label">{escape(label)}</div><div class="kpi-value">{escape(value)}<span class="kpi-unit">{escape(unit)}</span></div></div>' for label, value, unit in values)
    st.markdown(f'<div class="kpi-strip">{items}</div>', unsafe_allow_html=True)


def render_strategy_comparison(comparison, selected):
    items = []
    for row in comparison.itertuples():
        active = ' selected' if row.strategy == selected else ''
        items.append(
            f'<article class="strategy-result{active}" style="--strategy-color:{STRATEGY_COLORS[row.strategy]}">'
            f'<header><h3>{escape(row.strategy)}</h3><span>{"当前展示" if active else "对照策略"}</span></header>'
            f'<div class="strategy-carbon">{row.total_carbon_kg:,.0f}<small>kgCO2</small></div>'
            '<p>恢复阶段碳清单</p><dl>'
            f'<div><dt>失供电量</dt><dd>{row.eens_kwh:,.0f}<small>kWh</small></dd></div>'
            f'<div><dt>关键负荷恢复</dt><dd>{row.critical_recovery_pct:.1f}<small>%</small></dd></div>'
            '</dl></article>'
        )
    st.markdown('<div class="strategy-results">' + ''.join(items) + '</div>', unsafe_allow_html=True)
