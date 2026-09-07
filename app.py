from __future__ import annotations

import hashlib
import io
import json
import os
import pickle
import sys
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from ui import setup_ui, render_brand, render_heading, render_metrics, render_strategy_comparison, STRATEGY_COLORS

ROOT = Path(__file__).resolve().parent
EVIDENCE_FREEZE_DATE = "2026-08-22"
sys.path.insert(0, str(ROOT / "src"))

from gridrescue.care import default_care_tasks, evaluate_care_tasks  # noqa: E402
from gridrescue.facts import FACTS  # noqa: E402
from gridrescue.islands import build_island_passports  # noqa: E402
from gridrescue.mrv import STRATEGY_SLUGS, verify_mrv_bundle, _code_bundle_hash  # noqa: E402
from gridrescue.pareto import ParetoScanSpec, scan_pareto  # noqa: E402
from gridrescue.pipeline import run_pipeline, run_scenario  # noqa: E402
from gridrescue.public_data import load_public_scenario, PUBLIC  # noqa: E402
from gridrescue.powerflow import validate_dispatch  # noqa: E402
from gridrescue.restoration import STRATEGIES, state_at_hour  # noqa: E402
from gridrescue.risk import choose_strategy, summarize_risk  # noqa: E402
from gridrescue.scenarios import SCENARIOS  # noqa: E402
from ui_network import render_network  # noqa: E402


PUBLIC_CASES = {"武汉高温 · 2022-08-15": "wuhan_heat", "武汉降雨 · 2020-07-06": "wuhan_rain", "厦门大风 · 2016-09-15": "xiamen_wind"}
CODE_FINGERPRINT = hashlib.sha256(b"".join(p.read_bytes() for p in sorted((ROOT / "src").rglob("*.py")))).hexdigest()

setup_ui()

with st.sidebar:
    render_brand()
    scenario_name = st.selectbox("灾害场景", list(SCENARIOS) + list(PUBLIC_CASES))
    strategy = st.radio("恢复策略", STRATEGIES, index=2)
    st.divider()
    def step_hour(delta):
        st.session_state["restoration_hour"] = max(0, min(23, st.session_state.get("restoration_hour", 4) + delta))

    hour = st.slider("恢复进程 / 小时", 0, 23, 4, key="restoration_hour")
    previous_hour, next_hour = st.columns(2)
    previous_hour.button("", key="hour-previous", help="上一小时", icon=":material/chevron_left:", on_click=step_hour, args=(-1,), disabled=hour == 0, width="stretch")
    next_hour.button("", key="hour-next", help="下一小时", icon=":material/chevron_right:", on_click=step_hour, args=(1,), disabled=hour == 23, width="stretch")
    st.caption(f"T+{hour:02d}:00 / 24小时恢复窗口")
    st.markdown('<div class="sidebar-footer">MATPOWER case33bw<br>33 节点 · 32 支路 · 5 联络线<br>12.66 kV / 10 MVA</div>', unsafe_allow_html=True)
    with st.expander("数据与核算边界", icon=":material/info:"):
        st.caption("网络、故障与生命线任务含工程假设；碳清单仅核算购电、柴油与车辆。服务不等价时不主张严格减排。")


@st.cache_data(show_spinner="正在推演三种恢复策略……")
def cached_pipeline(name: str, code_fingerprint: str):
    public_key = PUBLIC_CASES.get(name)
    slug = public_key or {"暴雨内涝": "flood", "台风": "typhoon", "极端高温": "heat"}[name]
    directory = ROOT / "artifacts/competition2026" / ("public_replay" if public_key else "baseline_current") / slug
    cache, metadata = directory / "pipeline.pkl", directory / "cache_manifest.json"
    if os.getenv("GRIDRESCUE_FORCE_LIVE", "0") != "1" and cache.exists() and metadata.exists():
        info = json.loads(metadata.read_text(encoding="utf-8"))
        data = cache.read_bytes()
        if info.get("code_sha256") == code_fingerprint and info.get("cache_sha256") == hashlib.sha256(data).hexdigest():
            # Release-owned local caches only, never uploads or external paths.
            return pickle.loads(data)
    return run_scenario(load_public_scenario(public_key)) if public_key else run_pipeline(name)


@st.cache_data(show_spinner="正在计算同服务 ε-constraint Pareto 前沿……")
def cached_pareto(name: str):
    return scan_pareto(
        name,
        ParetoScanSpec(
            strategies=("最小失供恢复",),
            normal_allowance_fractions=(0.0, 0.04, 0.05, 0.06),
        ),
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def load_wave11_risk_report() -> dict[str, Any] | None:
    """Load the deterministic CVaR report without making the live demo wait."""
    path = Path(os.getenv("GRIDRESCUE_RISK_REPORT", str(ROOT / "artifacts" / "competition2026" / "risk_report.json")))
    try:
        report = _load_json_object(path)
        if not isinstance(report.get("summaries"), list) or "chosen_strategy" not in report:
            return None
        return report
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def load_wave11_mrv_sensitivity() -> dict[str, Any] | None:
    key = PUBLIC_CASES.get(scenario_name)
    slug = key or {"暴雨内涝": "flood", "台风": "typhoon", "极端高温": "heat"}[scenario_name]
    path = ROOT / "artifacts/competition2026" / ("public_replay" if key else "baseline") / slug / "sensitivity_report.json"
    if not path.exists():
        return None
    try:
        report = _load_json_object(path)
        rows = report.get("summaries")
        required = {"strategy_id", "baseline_kgco2", "q05_kgco2", "q95_kgco2", "winner_rate"}
        return report if isinstance(rows, list) and all(isinstance(row, dict) and required.issubset(row) for row in rows) else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _bundle_matches(bundle: Path, scenario: str, network_sha256: str) -> bool:
    try:
        manifest = _load_json_object(bundle / "run_manifest.json")
        return bool(
            manifest.get("scenario", {}).get("name") == scenario
            and str(manifest.get("network", {}).get("source_sha256", "")).upper()
            == network_sha256.upper()
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def resolve_mrv_bundle(
    artifact_root: Path,
    scenario: str,
    network_sha256: str,
    *,
    override: str | None = None,
) -> Path | None:
    if override:
        candidate = Path(override).expanduser().resolve()
        return candidate if candidate.is_dir() and _bundle_matches(candidate, scenario, network_sha256) else None

    candidates: list[tuple[int, str, str, Path]] = []
    if artifact_root.exists():
        for manifest_path in artifact_root.glob("**/run-*/run_manifest.json"):
            bundle = manifest_path.parent
            if not _bundle_matches(bundle, scenario, network_sha256):
                continue
            try:
                manifest = _load_json_object(manifest_path)
                created_at = str(manifest.get("created_at", ""))
            except (OSError, ValueError, json.JSONDecodeError):
                created_at = ""
            freeze_match = int(created_at.startswith(EVIDENCE_FREEZE_DATE))
            candidates.append((freeze_match, created_at, bundle.as_posix(), bundle))
    return max(candidates, key=lambda item: (item[0], item[1], item[2]))[3] if candidates else None


def summarize_factor_data_class(registry: pd.DataFrame) -> dict[str, str | int]:
    required = {"source_class", "method", "approval_status"}
    missing = required.difference(registry.columns)
    if missing or registry.empty:
        raise ValueError(f"factor registry missing fields: {sorted(missing)}")
    classes = sorted(set(registry["source_class"].astype(str)))
    methods = sorted(set(registry["method"].astype(str)))
    approvals = sorted(set(registry["approval_status"].astype(str)))
    return {
        "data_class": classes[0] if len(classes) == 1 else "MIXED: " + ",".join(classes),
        "factor_count": int(len(registry)),
        "methods": ", ".join(methods),
        "approvals": ", ".join(approvals),
    }


def load_mrv_ui_state(bundle_text: str) -> dict[str, Any]:
    bundle = Path(bundle_text)
    semantic_errors: list[str] = []
    try:
        manifest = _load_json_object(bundle / "run_manifest.json")
        seal = _load_json_object(bundle / "evidence" / "seal.json")
        stored = _load_json_object(bundle / "evidence" / "verification.json")
        gates = _load_json_object(bundle / "outputs" / "claim_gates.json")
        registry = pd.read_csv(bundle / "inputs" / "factor_registry.csv", keep_default_na=False)
        factor_summary = summarize_factor_data_class(registry)
        live = verify_mrv_bundle(bundle)
        run_ids = {
            str(manifest.get("run_id", "")),
            str(seal.get("run_id", "")),
            str(stored.get("run_id", "")),
            str(live.get("run_id", "")),
        }
        if len(run_ids) != 1 or "" in run_ids:
            semantic_errors.append("manifest/seal/verification run_id 不一致")
        if manifest.get("gates") != gates:
            semantic_errors.append("manifest gates 与 claim_gates.json 不一致")
    except Exception as exc:  # render evidence failure instead of crashing the app
        manifest, seal, stored, gates = {}, {}, {}, {}
        registry = pd.DataFrame()
        factor_summary = {"data_class": "UNKNOWN", "factor_count": 0, "methods": "", "approvals": ""}
        live = {"verified": False, "errors": [str(exc)], "checked_files": 0, "run_id": "unknown"}
        semantic_errors.append(f"MRV schema/load error: {exc}")
    display_verified = bool(
        manifest.get("status") == "sealed"
        and live.get("verified") is True
        and not live.get("errors")
        and not semantic_errors
    )
    return {
        "bundle_dir": str(bundle),
        "manifest": manifest,
        "seal": seal,
        "stored_verification": stored,
        "live_verification": live,
        "claim_gates": gates,
        "factor_registry": registry,
        "factor_summary": factor_summary,
        "semantic_errors": semantic_errors,
        "display_verified": display_verified,
    }


def build_mrv_bundle_zip(bundle_text: str) -> bytes:
    bundle = Path(bundle_text)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle).as_posix())
    return buffer.getvalue()


def render_mrv_evidence_panel(state: dict[str, Any] | None, strategy_name: str) -> None:
    st.subheader("MRV证据包实时复核")
    if state is None:
        st.info("当前场景没有匹配网络SHA-256的归档MRV证据包。")
        return

    manifest = state["manifest"]
    verification = state["live_verification"]
    gates = state["claim_gates"]
    comparison = gates.get("comparison", {})
    factor_summary = state["factor_summary"]
    claim_labels = {
        "same_service_inventory_reduction": "严格同服务清单降低",
        "controlled_service_budget_inventory_difference": "受控服务预算下的清单差异",
        "inventory_only": "仅排放清单",
    }
    raw_claim = str(comparison.get("claim_status", "unknown"))
    claim_label = claim_labels.get(raw_claim, f"UNKNOWN ({raw_claim})")
    same_service = comparison.get("same_service_pass") is True
    sealed = manifest.get("status") == "sealed"

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Seal状态", "SEALED" if sealed else "NOT SEALED")
    m2.metric("Verification", "PASS" if state["display_verified"] else "FAIL")
    m3.metric("已校验文件", str(int(verification.get("checked_files", 0))))
    m4.metric("Factor data class", str(factor_summary.get("data_class", "UNKNOWN")))
    m5.metric("Same-service gate", "通过" if same_service else "未通过")
    m6.metric("Claim status", claim_label)

    slug = STRATEGY_SLUGS[strategy_name]
    eligible = gates.get("strategies", {}).get(slug, {}).get("inventory_eligible") is True
    budget = 100 * float(comparison.get("normal_service_budget_fraction", 0.0))
    difference = float(comparison.get("inventory_difference_kgCO2", 0.0))
    st.caption(
        f"run_id={manifest.get('run_id', 'unknown')} · 策略清单资格={'Eligible' if eligible else 'Blocked'} · "
        f"普通服务预算={budget:.0f}% · 候选-参考清单差={difference:+.2f} kgCO2"
    )
    if state["display_verified"]:
        st.success("MRV证据包已通过现场只读复核。")
    else:
        st.error("MRV证据包复核失败；以下状态不进入正式主张。")
    if not same_service:
        st.warning("严格同服务门未通过；当前仅展示受控服务预算下的排放清单差异。")

    errors = list(verification.get("errors", [])) + list(state.get("semantic_errors", []))
    if errors:
        with st.expander("查看复核错误", expanded=True):
            for error in errors:
                st.code(str(error))
    with st.expander("因子与证据边界"):
        st.caption(
            f"{factor_summary.get('factor_count', 0)}个因子 · "
            f"method={factor_summary.get('methods', '')} · approval={factor_summary.get('approvals', '')}"
        )
        if not state["factor_registry"].empty:
            st.dataframe(state["factor_registry"], width="stretch", hide_index=True)
        st.write(gates.get("boundary_note", ""))
        st.write(state.get("seal", {}).get("meaning", ""))
        st.write(verification.get("meaning", ""))

    label = "下载MRV证据包ZIP" if state["display_verified"] else "下载待复核MRV证据包ZIP"
    st.download_button(
        label,
        build_mrv_bundle_zip(state["bundle_dir"]),
        file_name=f"GridRescue_{manifest.get('run_id', 'mrv')}.zip",
        mime="application/zip",
    )


public_input = load_public_scenario(PUBLIC_CASES[scenario_name]) if scenario_name in PUBLIC_CASES else None
result = cached_pipeline(scenario_name, CODE_FINGERPRINT)
if public_input is not None and result.scenario != public_input:
    st.error("缓存输入与当前公开数据不一致，拒绝使用。请强制现场复算。")
    st.stop()
selected = result.strategies[strategy]
metrics = selected.metrics
mrv_bundle_dir = resolve_mrv_bundle(
    ROOT / "artifacts" / "competition2026",
    result.scenario.name,
    result.model.source_sha256,
    override=os.getenv("GRIDRESCUE_MRV_BUNDLE"),
)
mrv_state = load_mrv_ui_state(str(mrv_bundle_dir)) if mrv_bundle_dir else None
if mrv_state is not None:
    matched = True
    for current_name, current_result in result.strategies.items():
        archived_path = mrv_bundle_dir / "outputs" / f"dispatch_{STRATEGY_SLUGS[current_name]}.csv"
        try:
            archived = pd.read_csv(archived_path).set_index("hour")
            current = current_result.dispatch.frame
            matched = matched and archived.index.equals(current.index) and set(current.columns).issubset(archived.columns)
            if matched:
                matched = bool(((archived[current.columns] - current).abs() <= 1e-4).all().all())
        except (OSError, ValueError, KeyError):
            matched = False
    mrv_state["current_result_match"] = matched and mrv_state["manifest"].get("code", {}).get("code_bundle_sha256") == _code_bundle_hash(ROOT)
    with st.sidebar:
        st.caption("证据对应当前推演" if mrv_state["current_result_match"] else "历史证据仅供归档查阅，不对应当前推演，不能用于当前推荐")

render_heading(scenario_name, strategy)
render_metrics(metrics)


def _gate_label(value: object) -> str:
    return "PASS" if value is True else "BLOCKED"


def render_decision_workbench() -> None:
    """Render the evaluator-first decision surface before the legacy tabs."""

    st.header("方案评估")
    st.caption("碳韧协同恢复 / 对照：最小失供恢复")
    if mrv_state is None:
        st.warning("当前灾种没有匹配冻结MRV证据；推荐卡仅展示现场推演，不进入正式主张。")
        comparison: dict[str, Any] = {}
        gate: dict[str, Any] = {}
        display_verified = False
    else:
        comparison = dict(mrv_state.get("claim_gates", {}).get("comparison", {}))
        gate = dict(
            mrv_state.get("claim_gates", {})
            .get("strategies", {})
            .get(STRATEGY_SLUGS.get("碳韧协同恢复", "carbon_resilient"), {})
        )
        display_verified = bool(mrv_state.get("display_verified") and mrv_state.get("current_result_match"))

    candidate_name = "碳韧协同恢复"
    reference_name = "最小失供恢复"
    claim_label = "受控服务预算下的清单差异"
    normal_budget = 100 * float(comparison.get("normal_service_budget_fraction", 0.08))
    candidate_metrics = result.strategies["碳韧协同恢复"].metrics
    reference_metrics = result.strategies["最小失供恢复"].metrics
    inventory_difference = float(comparison.get("inventory_difference_kgCO2", candidate_metrics.total_carbon_kg - reference_metrics.total_carbon_kg))
    candidate_inventory = float(comparison.get("candidate_inventory_kgCO2", candidate_metrics.total_carbon_kg))
    reference_inventory = float(comparison.get("reference_inventory_kgCO2", candidate_inventory - inventory_difference))

    h1, h4 = st.columns([1.4, 1])
    h1.metric("推荐候选", candidate_name)
    with st.container(key="inventory-difference"):
        st.metric("候选-参考清单差", f"{inventory_difference:+,.0f} kgCO2")
    st.metric("普通服务预算", f"{normal_budget:.0f}%")
    recommendation_pass = bool(display_verified and gate.get("inventory_eligible") is True
                               and gate.get("care_task_pass") is True
                               and gate.get("grid_physical_pass") is True
                               and comparison.get("controlled_tradeoff_pass") is True)
    # Streamlit updates widget state before rerunning, even for controls below this metric.
    mode = str(st.session_state.get("workbench_evidence_preset", "主推荐 · PASS"))
    qualification = "BLOCKED"
    if recommendation_pass and not mode.startswith("NO_GFM"):
        qualification = "CLAIM GATED" if mode.startswith("受控") else "PASS"
    h4.metric("推荐资格", qualification)

    st.divider()
    st.markdown("#### 当前推演证据")
    g1, g2, g3 = st.columns(3)
    with g1:
        st.metric("服务合同", _gate_label(gate.get("care_task_pass")))
    with g2:
        st.metric("物理校验", _gate_label(gate.get("grid_physical_pass")))
    with g3:
        st.metric("证据复算", "PASS" if display_verified else "BLOCKED")

    with st.expander("证据预设", icon=":material/tune:"):
        mode = st.radio(
            "证据预设",
            ("主推荐 · PASS", "受控预算候选 · CLAIM GATED", "NO_GFM反例 · BLOCKED"),
            key="workbench_evidence_preset",
            label_visibility="collapsed",
        )
    if mode.startswith("NO_GFM"):
        st.error("BLOCKED / NO_GFM 演示预设：孤岛缺少成网型电源条件，候选不进入推荐；保留失败原因与重放入口。")
        st.code("gate=G2\nreason=NO_GFM\nrecommendation=disabled", language="text")
    elif mode.startswith("受控"):
        st.warning(
            f"{reference_name} → {candidate_name}：same_service_pass=false。当前只可展示{claim_label}，"
            "不能写成严格同服务减排。"
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {"候选": candidate_name, "清单": candidate_inventory, "服务预算": f"{normal_budget:.0f}%", "资格": "受控"},
                    {"参考": reference_name, "清单": reference_inventory, "服务预算": "0%", "资格": "服务锚点"},
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        if recommendation_pass:
            st.success("主推荐通过三门校验 · 受控服务预算", icon=":material/check_circle:")
        else:
            st.error("推荐被阻断：服务、物理或证据资格未全部通过。", icon=":material/block:")
        st.caption("服务不等价时，只比较受控服务预算下的碳清单差异。")

    with st.expander("主张边界与证据入口", expanded=False):
        st.write(
            "当前气体边界为 CO2，单位为 kgCO2。基准场景为工程假设；公开案例使用年度官方电力因子，柴油和车辆仍含工程假设。"
        )
        st.write(f"claim_status={comparison.get('claim_status', 'unavailable')} · same_service_pass={comparison.get('same_service_pass', False)}")
        st.write("Seal只代表文件完整性与内部复算，不代表第三方核证。")


def render_statistics():
    st.subheader("尾部风险")
    st.caption("36 场景压力测试，与单场景结果分别评估")
    risk_report = load_wave11_risk_report()
    if risk_report:
        chosen = risk_report.get("chosen_strategy") or {}
        st.metric("风险优选策略", str(chosen.get("strategy", "无合格策略")))
        r2, r3 = st.columns(2)
        r2.metric("CVaR95", f"{float(chosen['cvar95']):,.0f} kWh" if chosen else "无合格策略")
        r3.metric("允许失败率", f"{100 * float(risk_report.get('failure_budget', 0)):.0f}%")
        with st.expander("尾部风险明细", icon=":material/analytics:"):
            summaries = risk_report.get("summaries", [])
            if summaries:
                labels = {"strategy": "恢复策略", "mean": "平均EENS", "p95": "P95", "cvar95": "CVaR95", "failure_rate": "失败率", "risk_score": "风险评分", "eligible": "推荐资格"}
                frame = pd.DataFrame(summaries)
                columns = [c for c in labels if c in frame]
                st.dataframe(frame[columns].rename(columns=labels), hide_index=True, width="stretch",
                             column_config={"失败率": st.column_config.NumberColumn(format="percent"),
                                            **{label: st.column_config.NumberColumn(format="%.1f") for label in ("平均EENS", "P95", "CVaR95", "风险评分")}})
            st.caption("失败点保留在分母；超过失败预算的策略不进入风险推荐。")
    else:
        st.info("尾部风险报告不可用：文件缺失、损坏或格式不完整。")
    sensitivity = load_wave11_mrv_sensitivity()
    if sensitivity:
        with st.expander("碳因子敏感性 · 500次抽样", icon=":material/show_chart:"):
            st.caption("固定活动清单，仅扰动因子。区间为工程范围假设，不是官方置信区间。")
            rows = sensitivity.get("summaries", [])
            if rows:
                frame = pd.DataFrame(rows)
                frame["strategy_id"] = frame["strategy_id"].replace({v: k for k, v in STRATEGY_SLUGS.items()})
                labels = {"strategy_id": "恢复策略", "baseline_kgco2": "基准 kgCO2", "q05_kgco2": "P05 kgCO2", "q95_kgco2": "P95 kgCO2", "winner_rate": "最低清单占比"}
                st.dataframe(frame[list(labels)].rename(columns=labels), hide_index=True, width="stretch",
                             column_config={"最低清单占比": st.column_config.NumberColumn(format="percent"),
                                            **{label: st.column_config.NumberColumn(format="%.1f") for label in ("基准 kgCO2", "P05 kgCO2", "P95 kgCO2")}})


def render_public_sources():
    if scenario_name not in PUBLIC_CASES:
        return
    provenance = json.loads(result.scenario.provenance_json)
    weather_source = provenance["weather"]
    with st.expander("公开数据来源与逐时输入", expanded=True, icon=":material/database:"):
        st.write("ERA5气象再分析 + 官方年度电力因子 + 公开测试馈线 + 合成故障。不是现场电网实测。")
        st.write(f"天气日期：{weather_source['date']} · 网格：{weather_source['actual_coordinates']} · 时区：Asia/Shanghai")
        st.write("电力因子：2023年全国年平均 0.5306 kgCO2/kWh；跨年度参考情景，不是历史事件排放重建。")
        st.link_button("气象原始来源", weather_source["url"], icon=":material/open_in_new:")
        st.link_button("官方因子来源", provenance["grid_factor"]["url"], icon=":material/open_in_new:")
        weather_frame = pd.DataFrame(json.loads((PUBLIC / weather_source['path']).read_text(encoding='utf-8'))['hourly'])
        st.dataframe(weather_frame, hide_index=True, width="stretch")
        st.download_button("下载气象CSV", weather_frame.to_csv(index=False).encode('utf-8-sig'), file_name=f"{PUBLIC_CASES[scenario_name]}_weather.csv", mime="text/csv", icon=":material/download:")


overview, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    [
        "决策总览",
        "恢复数字孪生",
        "三策略对照",
        "能源与碳流",
        "潮流校验",
        "MRV报告",
        "公平Pareto",
        "成岛护照",
        "生命线任务",
    ]
)


with overview:
    map_column, decision_column = st.columns([1.8, 1], gap="large")
    with map_column, st.container(key="overview-map"):
        st.subheader("配电网恢复现场")
        with st.container(key="network-workbench"):
            st.caption(f"{strategy} · T+{hour:02d}:00 · 33节点 / 5联络线")
            render_network(result, strategy, hour, key="overview-network")
        current_state = state_at_hour(result.model, result.scenario, selected.plan, hour)
        m1, m2, m3 = st.columns(3)
        m1.metric("活跃故障", len(current_state.failed_branch_ids))
        m2.metric("联络开关闭合", len(current_state.closed_tie_ids))
        m3.metric("非根孤岛", len(current_state.islands))
        st.caption("33节点 · 32常闭支路 · 5联络线")
    with decision_column, st.container(key="overview-decision"):
        render_decision_workbench()
    st.divider()
    st.subheader("三种恢复策略，服务与碳清单同时比较")
    st.caption("同一灾害输入 · 24小时累计值 · 失供量不同，不构成严格同服务减排证明")
    render_strategy_comparison(result.comparison, strategy)
    trend_column, risk_column = st.columns([1.8, 1], gap="large")
    with trend_column:
        st.subheader("24小时服务轨迹")
        st.caption("三策略逐时总失供功率 / kW")
        trend = pd.DataFrame({name: item.dispatch.frame["unserved_critical_kw"] + item.dispatch.frame["unserved_normal_kw"] for name, item in result.strategies.items()})
        fig = px.line(trend, labels={"index": "恢复小时", "value": "失供功率 / kW", "variable": "策略"})
        fig.update_traces(line_width=2)
        fig.update_layout(height=290, margin=dict(l=45, r=10, t=10, b=70),
                          legend=dict(title_text="", y=-.32, x=0), xaxis_title=None)
        st.plotly_chart(fig, width="stretch", theme=None, key="overview-trend", config={"displayModeBar": False})
    with risk_column:
        render_statistics()

with tab1:
    left, right = st.columns([1.45, 1])
    with left:
        render_network(result, strategy, hour, key="detail-network")
    with right:
        st.subheader("恢复动作时间线")
        actions = selected.plan.actions.copy()
        actions["状态"] = actions["hour"].apply(lambda value: "已完成" if value <= hour else "待执行")
        st.dataframe(actions, width="stretch", hide_index=True, height=400)
        st.write(result.scenario.description)

with tab2:
    st.subheader("策略对照")
    st.caption("相同灾害输入与时间边界；服务水平存在差异，不按碳排单独排名。")
    comparison = result.comparison.copy()
    render_strategy_comparison(comparison, strategy)
    carbon_column, service_column = st.columns(2)
    for column, metric, title, unit in (
        (carbon_column, "total_carbon_kg", "恢复碳清单", "kgCO2"),
        (service_column, "eens_kwh", "累计失供电量", "kWh"),
    ):
        with column:
            st.subheader(title)
            fig = px.bar(comparison, x=metric, y="strategy", color="strategy", orientation="h",
                         color_discrete_map=STRATEGY_COLORS, text_auto=",.0f",
                         labels={metric: unit, "strategy": ""})
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, height=280,
                              xaxis_range=[0, max(float(comparison[metric].max()), 1) * 1.25],
                              margin=dict(l=105, r=40, t=16, b=40), yaxis_automargin=True)
            st.plotly_chart(fig, width="stretch", theme=None)
    with st.expander("完整指标与数据下载"):
        st.dataframe(comparison, width="stretch", hide_index=True)
        st.download_button("下载策略对照", comparison.to_csv(index=False).encode("utf-8-sig"),
                           file_name="strategy_comparison.csv", mime="text/csv", icon=":material/download:")

with tab3:
    frame = selected.dispatch.frame
    st.subheader("恢复期间的能源供给")
    supply = frame[["grid_import_kw", "diesel_generation_kw", "battery_discharge_kw"]].rename(
        columns={"grid_import_kw": "上级电网", "diesel_generation_kw": "柴油机", "battery_discharge_kw": "储能放电"}
    )
    supply["光伏利用"] = frame["pv_available_kw"] - frame["renewable_curtailment_kw"]
    fig = px.area(supply, labels={"value": "供电功率 / kW", "index": "恢复小时", "variable": "来源"},
                  color_discrete_sequence=["#326bd6", "#c08b49", "#8a77b4", "#168365"])
    fig.update_layout(height=350, legend_title_text="", xaxis_title="恢复小时")
    st.plotly_chart(fig, width="stretch", theme=None)
    unmet_column, storage_column = st.columns(2)
    with unmet_column:
        st.subheader("未满足的负荷")
        unmet = frame[["unserved_critical_kw", "unserved_normal_kw"]].rename(
            columns={"unserved_critical_kw": "关键负荷", "unserved_normal_kw": "普通负荷"})
        fig = px.line(unmet, labels={"value": "失供功率 / kW", "index": "恢复小时"},
                      color_discrete_sequence=["#c75e54", "#9aa3ab"])
        fig.update_layout(height=290, legend_title_text="", xaxis_title="恢复小时")
        st.plotly_chart(fig, width="stretch", theme=None)
    with storage_column:
        st.subheader("储能剩余电量")
        fig = px.area(frame, y="battery_soc_kwh", labels={"battery_soc_kwh": "储能电量 / kWh", "index": "恢复小时"},
                      color_discrete_sequence=["#8a77b4"])
        fig.update_layout(height=290, xaxis_title="恢复小时")
        st.plotly_chart(fig, width="stretch", theme=None)

with tab4:
    validation = result.validations[strategy]
    v1, v2, v3, v4, v5 = st.columns(5)
    v1.metric("最大支路负载率", f"{validation.hourly['max_branch_loading_pct'].max():.1f}%")
    v2.metric("最低节点电压", f"{validation.hourly['min_voltage_pu'].min():.3f} pu")
    v3.metric("24h估算线损", f"{validation.hourly['estimated_loss_kw'].sum():.1f} kWh")
    v4.metric("物理不可行小时", f"{int((~validation.hourly['is_feasible']).sum())}")
    v5.metric("孤岛功率缺口", f"{validation.hourly['unserved_balance_kw'].sum():.1f} kWh")
    voltage_column, loading_column = st.columns(2)
    for column, metric, title, unit, limit in (
        (voltage_column, "min_voltage_pu", "最低节点电压", "pu", .95),
        (loading_column, "max_branch_loading_pct", "最大支路负载率", "%", 100),
    ):
        with column:
            st.subheader(title)
            fig = px.line(validation.hourly, y=metric, labels={metric: unit, "index": "恢复小时"})
            fig.add_hline(y=limit, line_dash="dash", line_color="#c75e54",
                          annotation_text=f"工程限值 {limit:g} {unit}", annotation_position="top left")
            fig.update_layout(height=300, xaxis_title="恢复小时")
            st.plotly_chart(fig, width="stretch", theme=None)
    st.caption(
        "采用MATPOWER case33bw的逐节点P/Q与逐支路R/X执行径向前推回代。"
        "无成网电源或资源越限的孤岛直接标记为不可行，不注入虚拟电源；线路热限额为独立工程假设。"
    )
    st.dataframe(validation.hourly, width="stretch")

with tab5:
    render_public_sources()
    render_mrv_evidence_panel(mrv_state, strategy)
    st.divider()
    st.markdown(selected.report)
    st.caption(
        f"电网数据来源：{result.model.source_name}；原文件SHA-256：{result.model.source_sha256}。"
        f"支路热限额：{result.model.capacity_assumption}。"
    )
    st.download_button("下载MRV报告", selected.report, file_name=f"GridRescue_{scenario_name}_{strategy}.md")
    st.download_button(
        "下载逐时推演CSV",
        selected.dispatch.frame.to_csv(index_label="hour").encode("utf-8-sig"),
        file_name=f"GridRescue_{scenario_name}_{strategy}.csv",
        mime="text/csv",
    )


with tab6:
    st.subheader("同服务 ε-constraint 碳—韧性前沿")
    st.write(
        "先按医院、其他关键负荷、普通负荷的词典序求出物理服务锚点，再只允许普通负荷在"
        "明确的 ε 范围内让步，求最低恢复阶段碳排。每个候选重新执行 P/Q 潮流、孤岛平衡、"
        "电压与热限反馈；求解失败或物理失败的点保留在证据表中。"
    )
    st.caption(
        "扫描固定使用“最小失供恢复”的修复顺序和联络线方案，避免拓扑差异冒充低碳收益。"
        "0% 点是物理验证后的最小普通失供服务锚点。"
    )
    run_key = f"pareto_result::{scenario_name}"
    if scenario_name in PUBLIC_CASES:
        st.info("公开气象案例的严格Pareto尚未运行；下列按钮禁用，不替换为合成案例结果。")
    if st.button("运行4点物理Pareto扫描", type="primary", key=f"run-pareto-{scenario_name}", disabled=scenario_name in PUBLIC_CASES):
        st.session_state[run_key] = cached_pareto(scenario_name)

    pareto_result = st.session_state.get(run_key)
    if pareto_result is None:
        st.info("点击按钮后计算 0%、4%、5%、6% 四个普通负荷让步点；首次运行约需几十秒。")
    else:
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("扫描点", len(pareto_result.points))
        p2.metric("非支配点", len(pareto_result.frontier))
        p3.metric("失败点", len(pareto_result.failures))
        p4.metric(
            "物理通过率",
            f"{100 * pareto_result.points['physical_pass'].fillna(False).mean():.0f}%",
        )
        if "care_contract_pass" in pareto_result.points:
            st.caption(
                "生命线硬合同通过率："
                f"{100 * pareto_result.points['care_contract_pass'].fillna(False).mean():.0f}%；"
                "任务定义在每个锚点与候选点保持不变。"
            )
        if not pareto_result.frontier.empty:
            frontier = pareto_result.frontier.sort_values("normal_eens_kwh").copy()
            frontier["普通负荷让步"] = frontier["normal_allowance_fraction"].map(
                lambda value: f"{100 * float(value):.0f}%"
            )
            fig = px.line(
                frontier,
                x="normal_eens_kwh",
                y="total_carbon_kg",
                markers=True,
                text="普通负荷让步",
                hover_data=[
                    "hospital_eens_kwh",
                    "other_essential_eens_kwh",
                    "physical_feasible_hours",
                    "min_voltage_pu",
                    "max_branch_loading_pct",
                ],
                labels={
                    "normal_eens_kwh": "普通负荷 EENS / kWh",
                    "total_carbon_kg": "恢复阶段碳排 / kgCO2",
                },
                title="同一医院与关键服务合同下的可执行 Pareto 前沿",
            )
            fig.update_traces(textposition="top center")
            st.plotly_chart(fig, width="stretch")
            display_columns = [
                "normal_allowance_fraction",
                "normal_eens_kwh",
                "total_carbon_kg",
                "hospital_eens_kwh",
                "other_essential_eens_kwh",
                "critical_recovery_pct",
                "physical_feasible_hours",
                "min_voltage_pu",
                "max_branch_loading_pct",
                "run_id",
            ]
            st.dataframe(frontier[display_columns], width="stretch", hide_index=True)
            st.download_button(
                "下载Pareto前沿CSV",
                frontier.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"GridRescue_{scenario_name}_pareto_frontier.csv",
                mime="text/csv",
            )
        if not pareto_result.failures.empty:
            with st.expander(f"查看 {len(pareto_result.failures)} 个失败/淘汰点"):
                st.dataframe(pareto_result.failures, width="stretch", hide_index=True)
        st.download_button(
            "下载全部扫描证据CSV",
            pareto_result.points.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"GridRescue_{scenario_name}_pareto_all_points.csv",
            mime="text/csv",
        )


with tab8:
    st.subheader("医院生命线 CareTask")
    care_tasks = default_care_tasks()
    care_evaluation = evaluate_care_tasks(
        care_tasks,
        selected,
        result.validations[strategy],
    )
    completed_count = int(care_evaluation["task_complete"].sum())
    tier1 = care_evaluation[care_evaluation["tier"] == 1]
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("任务完成率", f"{100 * completed_count / max(len(care_evaluation), 1):.0f}%")
    l2.metric("一级任务", f"{int(tier1['task_complete'].sum())}/{len(tier1)}")
    l3.metric("最小任务电压", f"{care_evaluation['minimum_voltage_pu'].min():.3f} pu")
    l4.metric(
        "最长连续达标",
        f"{int(care_evaluation['longest_qualified_duration_h'].min())} h",
    )
    st.caption(
        "任务功率、时窗、deadline和电压阈值均为 E 类合成赛事模板；"
        "用于验证方法与证据链，不代表真实医院测量值或临床运行标准。"
    )
    display = care_evaluation[
        [
            "task_id",
            "name",
            "tier",
            "node_id",
            "start_hour",
            "end_hour",
            "deadline_hour",
            "min_kw",
            "maximum_coincident_required_kw",
            "minimum_served_kw",
            "minimum_voltage_pu",
            "longest_qualified_duration_h",
            "task_complete",
            "failure_reason_codes",
        ]
    ].copy()
    st.dataframe(display, width="stretch", hide_index=True)
    st.download_button(
        "下载生命线任务证据CSV",
        care_evaluation.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"GridRescue_{scenario_name}_{strategy}_care_tasks.csv",
        mime="text/csv",
    )


with tab7:
    st.subheader("微网成岛能力护照")
    passport_strategy = st.selectbox(
        "护照策略",
        STRATEGIES,
        index=0,
        key="island-passport-strategy",
        help="传统恢复保留了更多非根孤岛，最适合展示成岛资格与阻断原因。",
    )
    passport_result = build_island_passports(
        result.model,
        result.scenario,
        result.strategies[passport_strategy],
        result.validations[passport_strategy],
    )
    if passport_result.hourly.empty:
        st.success("该策略当前24小时内没有非根孤岛，所有已供电分量均与上级电网连通。")
    else:
        current_passports = passport_result.hourly[
            passport_result.hourly["hour"] == hour
        ].copy()
        i1, i2, i3, i4 = st.columns(4)
        i1.metric("当前非根孤岛", len(current_passports))
        i2.metric(
            "BLOCKED",
            int((current_passports["passport_status"] == "BLOCKED").sum()),
        )
        i3.metric(
            "可带电/有条件",
            int((current_passports["passport_status"] != "BLOCKED").sum()),
        )
        known_margins = current_passports.loc[
            current_passports["passport_status"] != "BLOCKED", "weakest_margin_pct"
        ]
        i4.metric(
            "最小已知裕度",
            f"{known_margins.min():.1f}%" if not known_margins.empty else "—",
        )
        st.caption(
            "当前GFM与黑启动资格由模型中的柴油/BESS容量推断，证据等级为 assumed_from_model；"
            "燃料持续时长和现场投运试验尚未提供，因此护照不会标成 VERIFIED。"
        )
        passport_columns = [
            "island_episode_id",
            "component_key",
            "passport_status",
            "gfm_status",
            "black_start_status",
            "service_load_kw",
            "critical_service_pct",
            "p_reserve_kw",
            "q_reserve_kvar",
            "soc_pct",
            "min_voltage_pu",
            "max_loading_pct",
            "weakest_constraint",
            "weakest_margin_pct",
            "blocked_reason_codes",
        ]
        st.dataframe(
            current_passports[passport_columns],
            width="stretch",
            hide_index=True,
        )
        timeline = passport_result.hourly.copy()
        fig = px.line(
            timeline,
            x="hour",
            y="weakest_margin_pct",
            color="island_episode_id",
            markers=True,
            hover_data=[
                "passport_status",
                "gfm_status",
                "weakest_constraint",
                "min_voltage_pu",
                "max_loading_pct",
            ],
            labels={
                "hour": "恢复小时",
                "weakest_margin_pct": "最薄弱已知裕度 / %",
                "island_episode_id": "孤岛episode",
            },
            title="岛×时间安全裕度（BLOCKED点固定显示为-100%）",
        )
        fig.add_hline(y=0, line_dash="dash", line_color="#ff4d4f")
        fig.add_hline(y=10, line_dash="dot", line_color="#f3a712")
        fig.add_hline(y=25, line_dash="dot", line_color="#37d39a")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(passport_result.episodes, width="stretch", hide_index=True)
        st.download_button(
            "下载逐时成岛护照CSV",
            passport_result.hourly.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"GridRescue_{scenario_name}_{passport_strategy}_island_passport.csv",
            mime="text/csv",
        )

