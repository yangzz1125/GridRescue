"""Presentation-only components; no simulation, evidence or eligibility logic."""
from html import escape
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st


def setup_ui():
    st.set_page_config(page_title="GridRescue · 碳韧智网", page_icon=":material/hub:", layout="wide", initial_sidebar_state="auto")
    css = (Path(__file__).resolve().parent / "ui/styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    pio.templates["gridrescue"] = go.layout.Template(layout=dict(
        font=dict(family="Microsoft YaHei, Arial, sans-serif", size=12, color="#33434a"),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        colorway=["#087e72", "#5986a0", "#bd6c4c", "#b19b55", "#8d78a4"],
        margin=dict(l=15, r=15, t=45, b=25),
        xaxis=dict(gridcolor="#edf1f1", zerolinecolor="#dfe6e7"),
        yaxis=dict(gridcolor="#edf1f1", zerolinecolor="#dfe6e7"),
        legend=dict(orientation="h", y=-.15, x=0, font=dict(size=11)),
    ))
    pio.templates.default = "gridrescue"


def render_brand():
    st.markdown('<div class="brand"><div class="brand-mark">GR</div><div><div class="brand-name">GridRescue</div><div class="brand-sub">碳韧智网 · 配电恢复决策</div></div></div>', unsafe_allow_html=True)


def render_heading(scenario, strategy):
    st.markdown('<div class="page-heading"><div><h1>配电网恢复工作台</h1><p>GridRescue 碳韧智网 / 应急保供与碳清单</p></div><div class="version-label">COMPETITION 2026<br>离线预案 · 24 h</div></div>'
                f'<div class="context-line"><span class="context-dot"></span><strong>{escape(scenario)}</strong><span>/</span><span>{escape(strategy)}</span></div>', unsafe_allow_html=True)


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
