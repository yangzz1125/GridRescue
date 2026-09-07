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
        font=dict(family="Microsoft YaHei, Arial, sans-serif", size=12, color="#373b40"),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        colorway=["#787f88", "#2967a3", "#34816b", "#ae7048", "#82719a"],
        margin=dict(l=40, r=16, t=16, b=60),
        xaxis=dict(gridcolor="#eff0f2", zerolinecolor="#dfe1e5"),
        yaxis=dict(gridcolor="#eff0f2", zerolinecolor="#dfe1e5"),
        legend=dict(orientation="h", y=-.28, x=0, font=dict(size=11)),
    ))
    pio.templates.default = "gridrescue"


def render_brand():
    st.markdown('<div class="brand"><strong>GridRescue</strong><span>碳韧智网</span></div>', unsafe_allow_html=True)


def render_heading(scenario, strategy):
    st.markdown('<div class="page-heading"><h1>碳韧智网 <span>GridRescue</span></h1>'
                '<p class="project-subtitle">极端天气下的配电网恢复与低碳保供</p>'
                f'<p class="scenario-context">{escape(scenario)}<span class="context-separator">/</span>{escape(strategy)}</p></div>', unsafe_allow_html=True)


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
